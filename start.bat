@echo off
REM ============================================================
REM  ChurnGuard - Lanceur (API + Frontend en meme temps)
REM  Double-clique ce fichier : 2 fenetres s'ouvrent.
REM  Laisse-les ouvertes pendant l'utilisation.
REM ============================================================
cd /d "%~dp0"
echo Demarrage de l'API (port 8000)...
start "ChurnGuard API" cmd /k ".\venv\Scripts\python.exe -m uvicorn app.main:app --reload"
echo Demarrage du frontend (port 3000)...
start "ChurnGuard Frontend" cmd /k "cd frontend && npm run dev"
echo.
echo API      : http://127.0.0.1:8000/docs
echo Frontend : http://localhost:3000
pause
