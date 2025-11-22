#!/bin/bash
...existing code...
echo "🚀 Setting up Travel Assistant Backend..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment (works on Linux/macOS and Git Bash on Windows)
echo "🔧 Activating virtual environment..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    # Git Bash / WSL friendly path for Windows venv
    source venv/Scripts/activate
else
    echo "⚠️  Could not find venv activate script. Activate manually:"
    echo "    (Git Bash) source venv/Scripts/activate"
    echo "    (PowerShell) .\\venv\\Scripts\\Activate.ps1"
fi

# Upgrade pip/build tools before installing
echo "⬆️  Upgrading pip, setuptools and wheel..."
python -m pip install --upgrade pip setuptools wheel

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env and add your OPENAI_API_KEY!"
    echo ""
fi

echo "✅ Setup complete!"
echo ""
echo "Notes:"
echo "- If pip tries to compile NumPy from source, you likely lack a matching wheel (common on 32-bit Python)."
echo "- Ensure you're using 64-bit Python or use conda to get prebuilt packages on Windows."
echo ""
echo "Next steps:"
echo "1. Edit backend/.env and add your OPENAI_API_KEY"
echo "2. Run: python main.py"
echo ""
...existing code...