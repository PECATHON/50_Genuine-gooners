@echo off
echo 🚀 Setting up Travel Assistant Backend...

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Check if .env exists
if not exist ".env" (
    echo ⚠️  No .env file found. Copying from .env.example...
    copy .env.example .env
    echo ⚠️  IMPORTANT: Edit .env and add your OPENAI_API_KEY!
    echo.
)

echo ✅ Setup complete!
echo.
echo Next steps:
echo 1. Edit backend\.env and add your OPENAI_API_KEY
echo 2. Run: python main.py
echo.
pause
