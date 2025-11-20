# 🚀 Quick Start Guide

## Prerequisites
- Python 3.9 or higher
- OpenAI API key

## Setup (First Time Only)

### Option 1: Automatic Setup

**Linux/Mac:**
```bash
cd backend
chmod +x setup.sh
./setup.sh
```

**Windows:**
```bash
cd backend
setup.bat
```

### Option 2: Manual Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

## Configuration

Edit `backend/.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-key-here
```

## Start the Backend

```bash
cd backend
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

## Test the Backend

Open another terminal and test:
```bash
curl http://localhost:8000/health
```

Should return: `{"status":"healthy","agents":["coordinator","flight","hotel","research"]}`

## Troubleshooting

### Port 8000 already in use
```bash
# Kill the process using port 8000
# Linux/Mac:
lsof -ti:8000 | xargs kill -9
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Missing dependencies
```bash
pip install --upgrade -r requirements.txt
```

### OpenAI API errors
- Verify your API key is correct in `.env`
- Check your OpenAI account has credits
- Ensure there are no extra spaces in the key

## Ready to Use

Once running, the Next.js frontend at `http://localhost:3000/chat` will automatically connect!
