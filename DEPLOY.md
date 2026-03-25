# Deploy Guide (GitHub + Render)

## Why `127.0.0.1:8000` did not open
`127.0.0.1` is local-only. It works only when the API process is running on your own computer.

## Local run
```bash
python run_api.py
```
Open: `http://127.0.0.1:8000`

## Public deploy steps
1. Push this project to your GitHub repository.
2. Open Render dashboard and create a new Web Service from your GitHub repo.
3. Render will detect `render.yaml` and use:
   - Build: `pip install -r requirements.txt`
   - Start: `python run_api.py`
4. Wait for first deploy.
5. Open the Render URL and test:
   - `/health`
   - Ask from homepage chat UI.

## Notes
- This app currently uses local files under `data/`.
- For cloud deploy, commit `data/chunks/chunks.jsonl` so the service can answer after startup.
