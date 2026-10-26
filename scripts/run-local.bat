@echo off
REM Run CT-Viewer locally and open browser automatically

echo Starting CT-Viewer...
echo.

REM Start Streamlit and open browser
start "CT-Viewer" python -m streamlit run src\visualization\app.py --server.port 8501

REM Wait a moment for server to start, then open browser
timeout /t 3 /nobreak >nul
start http://localhost:8501

echo CT-Viewer should open in your browser at http://localhost:8501
echo.
echo Press any key to exit (server keeps running)...
pause >nul
