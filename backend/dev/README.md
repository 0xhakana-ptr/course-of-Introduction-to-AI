# Backend Dev Tools

This directory contains developer-only scripts.

These files are not imported by `backend.app` and are not part of the official
FastAPI runtime. Normal backend development should use:

```powershell
uv run uvicorn backend.app.main:app --reload --port 8000
```

Current tools:

- `mock_backend.py`: legacy manual message transport tester for frontend
  experiments. Do not use it as the real backend entrypoint.
