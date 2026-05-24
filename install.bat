@echo off
echo ================================================
echo  Smart AI Service - Setup Script
echo ================================================
echo.

:: Check Python 3.11
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.11 not found. Trying python...
    python --version
    set PYTHON_CMD=python
) else (
    set PYTHON_CMD=py -3.11
)

:: Remove old venv/myenv if corrupt
if exist venv (
    echo Removing old venv...
    rmdir /s /q venv
)

:: Create fresh venv named 'myenv'
echo Creating virtual environment (myenv)...
%PYTHON_CMD% -m venv myenv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

call myenv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet

echo Installing packages...
pip install fastapi==0.111.1 --quiet
pip install "uvicorn[standard]==0.30.1" --quiet
pip install python-multipart==0.0.9 --quiet
pip install pillow==10.4.0 --quiet
pip install numpy==1.26.4 --quiet
pip install opencv-contrib-python==4.11.0.86 --quiet
pip install python-dotenv==1.0.1 --quiet
pip install requests==2.32.3 --quiet
pip install aiofiles==23.2.1 --quiet
pip install httpx==0.27.0 --quiet

echo Installing MediaPipe...
pip install mediapipe==0.10.33 --quiet
if errorlevel 1 (
    echo mediapipe 0.10.33 failed, trying 0.10.14...
    pip install mediapipe==0.10.14 --quiet
)
if errorlevel 1 (
    echo mediapipe 0.10.14 failed, trying latest available...
    pip install mediapipe --quiet
)

echo.
echo Verifying MediaPipe import...
python -c "import mediapipe; print('mediapipe', mediapipe.__version__)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: MediaPipe installed but failing to import.
    echo This typically means the Microsoft Visual C++ redistributable is missing.
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
    echo After installing the runtime, re-run install.bat or fix_mediapipe.bat.
)

echo.
echo ================================================
echo  Done! Starting service...
echo ================================================
python main.py
