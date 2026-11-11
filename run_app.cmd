@echo off
REM Start CTBeamStudio with the ct-viewer conda environment.
REM
REM Why this exists: parallelproj is only available on conda-forge, and the
REM app silently falls back to zero projections on a plain pip interpreter.
REM Starting through this script guarantees the env that has it.
REM
REM Override the conda location by setting CONDA_ROOT before running.

setlocal

if "%CONDA_ROOT%"=="" set "CONDA_ROOT=%USERPROFILE%\miniforge3"
if not exist "%CONDA_ROOT%\Scripts\conda.exe" set "CONDA_ROOT=%USERPROFILE%\miniconda3"
if not exist "%CONDA_ROOT%\Scripts\conda.exe" (
    echo ERROR: no conda installation found at "%CONDA_ROOT%".
    echo Install Miniforge from https://github.com/conda-forge/miniforge/releases/latest
    echo or set CONDA_ROOT to your conda install directory.
    exit /b 1
)

call "%CONDA_ROOT%\Scripts\activate.bat" ct-viewer
if errorlevel 1 (
    echo ERROR: conda env "ct-viewer" is missing.
    echo Run:  conda env create -f environment.yml
    exit /b 1
)

python -c "import parallelproj, torch" 2>nul
if errorlevel 1 (
    echo WARNING: parallelproj or torch is not importable in this env.
    echo Forward projection will return zeros.
    echo Fix with: conda install -c conda-forge parallelproj "libparallelproj=*=cpu*" "pytorch=*=cpu*"
)

echo Starting CTBeamStudio from %CD% ...
streamlit run src\visualization\app.py %*

endlocal
