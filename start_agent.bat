@echo off
cd /d "%~dp0"


start "Ollama Start" cmd /k "ollama serve"
timeout /t 2 /nobreak >nul

start "AI Agent" cmd /k ".venv\Scripts\python.exe -m streamlit run app.py"