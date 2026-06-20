@echo off
cd backend
call venv\Scripts\activate.bat
uvicorn main:app --reload --port 8000
