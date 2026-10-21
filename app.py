import os
import re
import json
import sqlite3
from io import BytesIO
from html import escape
from datetime import datetime

from click import prompt
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from pypdf import PdfReader
from dotenv import load_dotenv

try:
    from google import genai
except ImportError:
    genai = None

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm


# =========================================================
# CAREERPILOT AI CONFIGURATION
# =========================================================

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key-for-local-development")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "careerpilot.db")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

api_key = os.getenv("GEMINI_API_KEY", "").strip()
client = genai.Client(api_key=api_key) if api_key and genai else None


SKILLS = [
    "python", "java", "javascript", "typescript", "sql", "mysql", "flask",
    "django", "html", "css", "react", "machine learning", "data analysis",
    "pandas", "numpy", "git", "github", "api", "rest api", "selenium",
    "pytest", "automation testing", "manual testing", "software testing",
    "linux", "aws", "docker", "communication", "problem solving",
    "power bi", "excel", "c++", "c", "java", "node.js", "fastapi",
    "testing", "quality assurance", "qa", "playwright", "postman"
]


# =========================================================
# DATABASE
# =========================================================

def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                job_description TEXT NOT NULL,
                score INTEGER NOT NULL,
                matched_skills TEXT NOT NULL,
                missing_skills TEXT NOT NULL,
                suggestions TEXT NOT NULL,
                questions TEXT NOT NULL,
                ai_feedback TEXT NOT NULL
            )
        """)


def save_analysis(result, job_description, questions, ai_feedback):
    with get_db_connection() as connection:
        connection.execute("""
            INSERT INTO analysis_history (
                created_at, job_description, score, matched_skills,
                missing_skills, suggestions, questions, ai_feedback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            job_description,
            int(result.get("score", 0)),
            json.dumps(result.get("matched", [])),
            json.dumps(result.get("missing", [])),
            json.dumps(result.get("suggestions", [])),
            json.dumps(questions or []),
            ai_feedback or "AI feedback not available.",
        ))


def get_analysis_history():
    with get_db_connection() as connection:
        rows = connection.execute("""
            SELECT id, created_at, job_description, score, matched_skills,
                   missing_skills, suggestions, questions, ai_feedback
            FROM analysis_history
            ORDER BY id DESC
        """).fetchall()

    history_items = []
    for row in rows:
        item = dict(row)
        for field in ("matched_skills", "missing_skills", "suggestions", "questions"):
            try:
                item[field] = json.loads(item[field])
            except (TypeError, json.JSONDecodeError):
                item[field] = []
        history_items.append(item)
    return history_items


# Initialize database before the app handles requests.
init_db()


# =========================================================
# RESUME EXTRACTION AND ANALYSIS
# =========================================================

def extract_pdf_text(file_storage):
    reader = PdfReader(file_storage)
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def find_skills(text):
    text_lower = text.lower()
    found = []
    for skill in SKILLS:
        pattern = r"(?<!\w)" + re.escape(skill) + r"(?!\w)"
        if re.search(pattern, text_lower) and skill not in found:
            found.append(skill)
    return sorted(found)


def analyze_resume(resume_text, job_description):
    resume_skills = find_skills(resume_text)
    job_skills = find_skills(job_description)

    matched = [skill for skill in job_skills if skill in resume_skills]
    missing = [skill for skill in job_skills if skill not in resume_skills]
    score = round((len(matched) / len(job_skills)) * 100) if job_skills else 0

    suggestions = []
    if not job_skills:
        suggestions.append(
            "No recognized skills were detected in the job description. "
            "Try including more of its technical requirements."
        )
    if missing:
        suggestions.append(
            "Review these job-related skills and add them to your resume only "
            "if you genuinely have them: " + ", ".join(missing) + "."
        )
    if len(resume_text.split()) < 100:
        suggestions.append(
            "Your resume text looks short. Consider adding relevant projects, "
            "technical skills, education, and truthful achievements."
        )
    if not resume_skills:
        suggestions.append(
            "Make sure your resume clearly lists the technical skills you know."
        )
    if not suggestions:
        suggestions.append(
            "Tailor your project descriptions to this job and include specific "
            "results you can honestly explain during an interview."
        )

    return {
        "score": score,
        "resume_skills": resume_skills,
        "matched": matched,
        "missing": missing,
        "suggestions": suggestions,
        "job_skill_count": len(job_skills),
    }


def generate_questions(missing_skills):
    questions = [
        "Tell me about yourself and your most relevant project.",
        "Explain how you would solve a technical problem step by step.",
        "Describe a bug you encountered and how you would debug it.",
        "Why are you interested in this role?",
        "How do you learn a new technology?",
    ]
    for skill in missing_skills[:5]:
        questions.append(f"What is {skill}, and how would you use it in a project?")
    return questions


# =========================================================
# OPTIONAL GEMINI AI FEEDBACK
# =========================================================


def generate_ai_feedback(resume_text, job_description):
    if client is None:
        return (
            "AI feedback is not connected. Check your Gemini API key "
            "and restart the app."
        )

    prompt = f"""Analyze this resume for the target job.

Resume:
{resume_text}

Job description:
{job_description}

Provide constructive feedback on strengths, missing skills,
resume improvements, and interview preparation."""

    interaction = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt
    )
    feedback = interaction.output_text

    if not feedback:
        raise ValueError("The AI service returned an empty response.")

    return feedback



# =========================================================
# PDF REPORT
# =========================================================

def create_pdf_report(report):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, title="CareerPilot AI Analysis Report",
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("CareerPilot AI", styles["Title"]),
        Paragraph("Resume Analysis Report", styles["Heading2"]),
        Spacer(1, 12),
    ]

    for heading, value in report.items():
        block = [Paragraph(escape(str(heading)), styles["Heading3"])]
        if isinstance(value, (list, tuple)):
            content = "<br/>".join(escape(str(item)) for item in value) or "Not available"
        else:
            content = escape(str(value)).replace("\n", "<br/>") or "Not available"
        block.append(Paragraph(content, styles["BodyText"]))
        block.append(Spacer(1, 9))
        story.append(KeepTogether(block))

    document.build(story)
    buffer.seek(0)
    return buffer


# =========================================================
# ROUTES
# =========================================================

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    questions = []
    ai_feedback = None
    job_description = ""

    if request.method == "POST":
        resume = request.files.get("resume")
        job_description = request.form.get("job_description", "").strip()

        if not resume or not resume.filename:
            error = "Please choose your resume PDF."
        elif not resume.filename.lower().endswith(".pdf"):
            error = "Please upload a PDF file."
        elif not job_description:
            error = "Please paste the job description."
        else:
            try:
                resume_text = extract_pdf_text(resume)
                if not resume_text:
                    error = (
                        "No readable text was found. Please upload a text-based "
                        "PDF rather than a scanned image."
                    )
                else:
                    result = analyze_resume(resume_text, job_description)
                    questions = generate_questions(result["missing"])
                    try:
                        ai_feedback = generate_ai_feedback(resume_text, job_description)
                    except Exception:
                        app.logger.exception("Gemini request failed")
                        ai_feedback = (
                            "AI feedback could not be generated. Basic analysis "
                            "is still available. Check your API key, model access, "
                            "internet connection, and API usage limits."
                        )

                    try:
                        save_analysis(result, job_description, questions, ai_feedback)
                    except sqlite3.Error:
                        app.logger.exception("Could not save analysis history")
                        error = "Analysis completed, but history could not be saved. See terminal details."
            except Exception:
                app.logger.exception("Resume analysis failed")
                error = (
                    "We couldn't read this PDF. Try another valid, text-based PDF. "
                    "Check the terminal for the detailed error."
                )

    return render_template(
        "index.html",
        result=result,
        error=error,
        questions=questions,
        ai_feedback=ai_feedback,
        job_description=job_description,
    )


@app.route("/dashboard")
def dashboard():
    analyses = get_analysis_history()
    return render_template(
        "dashboard.html",
        total_analyses=len(analyses),
        latest_score=analyses[0]["score"] if analyses else None,
        recent_analyses=analyses[:5],
    )


@app.route("/history")
def history():
    return render_template("history.html", analyses=get_analysis_history())


@app.route("/history/<int:analysis_id>")
def history_detail(analysis_id):
    with get_db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM analysis_history WHERE id = ?", (analysis_id,)
        ).fetchone()

    if row is None:
        flash("That analysis could not be found.", "error")
        return redirect(url_for("history"))

    item = dict(row)
    for field in ("matched_skills", "missing_skills", "suggestions", "questions"):
        try:
            item[field] = json.loads(item[field])
        except (TypeError, json.JSONDecodeError):
            item[field] = []
    return render_template("history_detail.html", item=item)


@app.route("/download-report", methods=["POST"])
def download_report():
    score = request.form.get("score", "0")
    report = {
        "Match Score": f"{score}%",
        "Matched Skills": request.form.getlist("matched"),
        "Missing Skills": request.form.getlist("missing"),
        "Suggestions": request.form.getlist("suggestions"),
        "Interview Questions": request.form.getlist("questions"),
        "AI Feedback": request.form.get("ai_feedback", "Not available"),
    }
    try:
        pdf_file = create_pdf_report(report)
    except Exception:
        app.logger.exception("PDF report generation failed")
        flash("The PDF report could not be generated. Check the terminal.", "error")
        return redirect(url_for("index"))

    return send_file(
        pdf_file, mimetype="application/pdf", as_attachment=True,
        download_name="CareerPilot_AI_Report.pdf"
    )


@app.errorhandler(413)
def file_too_large(error):
    return render_template(
        "index.html",
        result=None,
        error="Your PDF is too large. Please upload a file under 5 MB.",
        questions=[],
        ai_feedback=None,
        job_description="",
    ), 413


@app.errorhandler(404)
def page_not_found(error):
    return render_template("simple_error.html", message="The page you requested was not found."), 404


if __name__ == "__main__":
    app.run(debug=True)
