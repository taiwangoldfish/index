@echo off
cd /d "%~dp0"

".venv\Scripts\python.exe" "train_index_only.py" --data-root data\web_learning --skip-pipeline
if errorlevel 1 goto :end

".venv\Scripts\python.exe" "train_learning_profile.py" --data-root data\web_learning

:end
pause