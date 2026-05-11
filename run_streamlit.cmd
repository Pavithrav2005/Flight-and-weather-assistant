@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if exist "%PYTHON%" (
    "%PYTHON%" -m streamlit run "%ROOT%streamlit_app.py" %*
    exit /b %ERRORLEVEL%
)

echo Could not find "%PYTHON%".
echo Recreate the virtual environment with a locally installed Python, then run:
echo   python -m streamlit run streamlit_app.py
exit /b 1