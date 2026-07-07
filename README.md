<<<<<<< HEAD
# Radon Campaign Analyzer

Radon Campaign Analyzer is a minimal Django research prototype for organizing indoor radon monitoring campaigns and uploaded measurement files.

The current version supports:

- creating and listing monitoring campaigns
- viewing campaign details
- uploading CSV or Excel files to a campaign
- recording a placeholder analysis report
- keeping future analysis code isolated under `campaigns/services/`

Advanced machine learning and statistical analysis are intentionally out of scope for this scaffold. The project is structured so file parsing, quality checks, and modeling can later be added behind service modules without bloating the views.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open http://127.0.0.1:8000/.

## Tests

```bash
python manage.py test
```
>>>>>>> bfb2cab (Initial radon campaign analyzer app)
