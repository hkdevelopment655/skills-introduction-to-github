@echo off
echo Starting Smart AI Service...

:: Try myenv first, then venv, then plain python
if exist myenv\Scripts\activate.bat (
    echo Using myenv...
    call myenv\Scripts\activate.bat
    python main.py
    exit /b
)

if exist venv\Scripts\activate.bat (
    echo Using venv...
    call venv\Scripts\activate.bat
    python main.py
    exit /b
)

echo No virtual environment found. Trying system Python...
python main.py
