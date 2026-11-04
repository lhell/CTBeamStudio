@echo off
REM Run CTBeamStudio locally and open browser automatically

echo Starting CTBeamStudio...
echo.

REM Start Streamlit and open browser
start "CTBeamStudio" python -m streamlit run src\visualization\app.py --server.port 8501

REM Wait a moment for server to start, then open browser
timeout /t 3 /nobreak >nul
start http://localhost:8501

echo CTBeamStudio should open in your browser at http://localhost:8501
echo.
echo Press any key to exit (server keeps running)...
pause >nul
