# Run CT-Viewer locally and open browser automatically

Write-Host "Starting CT-Viewer..." -ForegroundColor Green
Write-Host ""

# Start Streamlit in background
$streamlitJob = Start-Job -ScriptBlock {
    python -m streamlit run src/visualization/app.py --server.port 8501
} -ErrorAction Stop

# Wait for server to start
Start-Sleep -Seconds 4

# Open browser
Start-Process "http://localhost:8501"

Write-Host "CT-Viewer should open in your browser at http://localhost:8501" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server..." -ForegroundColor Yellow

# Keep script running and handle cleanup
try {
    $streamlitJob | Wait-Job -Timeout ([int]::MaxValue) | Out-Null
}
finally {
    Stop-Job -Job $streamlitJob -ErrorAction SilentlyContinue
    Remove-Job -Job $streamlitJob -Force -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "CT-Viewer stopped." -ForegroundColor Red
}
