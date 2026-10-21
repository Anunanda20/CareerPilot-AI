# CareerPilot AI

A local Flask resume analyzer with PDF text extraction, job-description skill matching, interview-question suggestions, analysis history stored in SQLite, downloadable PDF reports, and optional Gemini AI feedback.

## Easiest way to run on Windows

1. Extract the ZIP file to a normal folder (do not run it from inside the ZIP preview).
2. Open the extracted folder. You should see `app.py`, `requirements.txt`, `templates`, and `static`.
3. Double-click `START_CAREERPILOT.bat`.
4. Wait for the setup to finish. Keep the black terminal window open.
5. Open http://127.0.0.1:5000 in your browser.

Python must be installed and available from the Windows command `python`. If Windows asks for permission, allow it as appropriate for your own computer.

## Manual setup (alternative)

Open PowerShell in this folder and run each command separately:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Then visit http://127.0.0.1:5000.

## Project files

- `app.py` — Flask application, routes, resume analysis, SQLite history, optional Gemini feedback, PDF report generation.
- `templates/` — HTML pages for the analyzer, dashboard, history, history details, and error page.
- `static/style.css` — application styles.
- `requirements.txt` — Python dependencies.
- `.env.example` — example configuration for optional Gemini AI feedback.
- `START_CAREERPILOT.bat` — Windows setup and launch helper.
- `.gitignore` — files to keep out of version control.

## Optional Gemini AI feedback

Basic resume analysis works without a Gemini API key. To enable Gemini feedback, make a copy of `.env.example` named `.env`, add your own `GEMINI_API_KEY`, and restart the app. Never share your API key in screenshots or chats.

## Notes

- Upload a text-based PDF resume (maximum 5 MB) and paste the target job description.
- The match score is based on recognized skills shared between the resume and job description; it is a simple helper, not a hiring prediction.
- The local SQLite database `careerpilot.db` is created automatically when the app starts.
