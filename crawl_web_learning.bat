@echo off
cd /d "%~dp0"

".venv\Scripts\python.exe" "run_pipeline.py" --source web --max-pages 30 --delay 0.5 --timeout 20 --data-root data\web_learning

pause