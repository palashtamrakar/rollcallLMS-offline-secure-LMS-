@echo off
cd /d "%~dp0"
echo Starting Roll Call LMS. Connect the pendriveData drive if prompted.
if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" backend\storage_bootstrap.py
) else (
    py -3 backend\storage_bootstrap.py
)
