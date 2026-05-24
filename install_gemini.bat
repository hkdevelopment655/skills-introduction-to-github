@echo off
echo Installing Gemini Python SDK...
call myenv\Scripts\activate.bat
pip install google-generativeai==0.8.3
pip install httpx==0.27.0
pip install pydantic==2.7.0
echo.
echo Testing Gemini connection...
python -c "import google.generativeai as g; print('✅ google-generativeai installed:', g.__version__)"
echo.
echo Done! Run: python main.py
pause
