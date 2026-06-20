@echo off
echo ==================================================
echo  InsureVerify - Setup (Windows)
echo ==================================================

echo.
echo [1/4] Setting up backend Python virtual environment...
cd backend
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
echo Backend dependencies installed.

echo.
echo [2/4] Checking for Ollama...
where ollama >nul 2>nul
if %ERRORLEVEL% == 0 (
    echo Ollama found. Pulling required models...
    ollama pull llava
    ollama pull llama3
) else (
    echo Ollama not found. InsureVerify will still run using classical CV fallbacks.
    echo For full VLM/LLM-powered analysis, install Ollama from https://ollama.com
    echo then run: ollama pull llava  and  ollama pull llama3
)

cd ..

echo.
echo [3/4] Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo.
echo [4/4] Setup complete.
echo ==================================================
echo To run the platform, open two terminals:
echo   Terminal 1: run_backend.bat
echo   Terminal 2: run_frontend.bat
echo Then open http://localhost:5173 in your browser.
echo ==================================================
pause
