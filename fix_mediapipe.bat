@echo off
echo ================================================
echo  Installing MediaPipe into existing myenv
echo ================================================
echo.

if not exist myenv (
    echo ERROR: myenv not found. Run install.bat first.
    pause
    exit /b 1
)

call myenv\Scripts\activate.bat

echo Your Python version:
python --version
echo.

echo Trying mediapipe 0.10.14...
pip install mediapipe==0.10.14 --quiet 2>nul
if not errorlevel 1 goto :success

echo mediapipe 0.10.14 failed. Trying latest compatible...
pip install mediapipe --quiet 2>nul
if not errorlevel 1 goto :success

echo mediapipe pip install failed. Trying with --only-binary...
pip install mediapipe --only-binary=:all: --quiet 2>nul
if not errorlevel 1 goto :success

echo.
echo Could not install mediapipe automatically.
echo Manual fix: Open myenv terminal and run:
echo   pip install mediapipe==0.10.14
pause
exit /b 1

:success
echo.
echo ================================================
echo  MediaPipe installed! Verifying...
echo ================================================
python -c "import mediapipe; print('mediapipe version:', mediapipe.__version__)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: MediaPipe is installed but import failed.
    echo This often means that the Microsoft Visual C++ redistributable is missing.
    where.exe winget >nul 2>&1
    if not errorlevel 1 (
        echo Installing Visual C++ runtime via winget...
        winget install --id Microsoft.VCRedist.2022.x64 -e --accept-package-agreements --accept-source-agreements
        if errorlevel 1 (
            echo Alternate winget package attempt...
            winget install --id Microsoft.VC++2015-2022.Redist.x64 -e --accept-package-agreements --accept-source-agreements
        )
        if errorlevel 1 (
            echo Winget install failed. Please install the x64 Visual C++ Redistributable manually from:
            echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
        )
    ) else (
        echo winget not found. Please install the x64 Visual C++ Redistributable manually from:
        echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
    )
    echo Re-run fix_mediapipe.bat after installing the redistributable.
    pause
    exit /b 1
)
python -c "import mediapipe; print('mediapipe version:', mediapipe.__version__)"
echo.
echo Restart the AI service with: start.bat
pause
