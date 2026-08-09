# Expense Tracker

A small FastAPI expense and GST tracking application.

## Requirements

- Python 3.12+
- pip
- Docker (optional)
- Docker Compose (optional)

## Run locally with Python

1. Open a terminal in `d:\Dev\CodeMonkey\expense-tracker`
2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Start the application:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. Open in your browser:

- App: `http://localhost:8000`
- API docs: `http://localhost:8000/api/docs`

## Run with Docker Compose

From `d:\Dev\CodeMonkey\expense-tracker`:

```powershell
docker compose up --build
```

This starts the service on port `8000`.

Open in your browser:

- App: `http://localhost:8000`
- API docs: `http://localhost:8000/api/docs`

## Notes

- The Docker image uses `entrypoint.sh` to launch Uvicorn.
- If you run locally, the app stores SQLite data in `data/db.sqlite3`.
- If using Docker Compose, data is persisted in the `tracker_data` volume.
