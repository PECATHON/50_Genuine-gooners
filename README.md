# AI-Powered Travel Planning Assistant (Multi-Agent)

A full-stack travel planning application built with **LangGraph multi-agent architecture**, featuring real-time streaming, request interruption handling, and seamless context preservation.

![Travel Assistant](https://img.shields.io/badge/Status-Production%20Ready-success)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple)

## 🎯 Key Features

### Multi-Agent Architecture (LangGraph)
- **Coordinator Agent**: Analyzes user intent and routes requests
- **Flight Agent**: Searches flights with real-time data
- **Hotel Agent**: Finds hotels and accommodations
- **Research Agent**: Provides general travel information via web search

### Request Interruption (Core Technical Challenge) ✨
- **Detection**: Recognizes when new queries arrive during processing
- **Cancellation**: Gracefully stops running operations with one click
- **Partial Result Preservation**: Saves progress before interruption
- **Continuation**: Resumes with preserved context and state

### Real-Time Communication
- **Server-Sent Events (SSE)**: Live streaming of agent actions
- **Status Updates**: Visual indicators for each active agent
- **Token Streaming**: Real-time LLM response display

### State Management
- **Conversation Persistence**: Maintains chat history across sessions
- **Context Transfer**: Seamless handoffs between agents
- **Thread-Based Storage**: Each conversation has unique state

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+ and npm/yarn/bun
- **Python** 3.10+ with pip
- **OpenAI API Key** (required)

### 1. Clone & Install

```bash
# Install frontend dependencies
npm install
# or
bun install

# Install backend dependencies
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

**Backend (.env)**
```bash
cd backend
cp .env.example .env
# Edit .env and add your OpenAI API key
```

Required:
```env
OPENAI_API_KEY=sk-your-openai-api-key
```

**Frontend (.env.local)** - Already configured
```env
NEXT_PUBLIC_PYTHON_BACKEND_URL=http://localhost:8000
```

### 3. Start Both Servers

**Terminal 1 - Python Backend**
```bash
cd backend
source venv/bin/activate
python main.py
```
Server starts at: http://localhost:8000

**Terminal 2 - Next.js Frontend**
```bash
npm run dev
# or
bun dev
```
Frontend starts at: http://localhost:3000

### 4. Open & Test

1. Navigate to http://localhost:3000
2. Click "Start Planning Your Trip"
3. Try queries like:
   - "Find flights from NYC to LAX"
   - "Hotels in Paris"
   - "Plan a trip to Tokyo"
4. Click **"Cancel Query"** while processing to test interruption

## 📋 Request Interruption Demo

### How It Works

1. **User sends query**: "Find flights from NYC to Tokyo"
2. **Coordinator routes** to Flight Agent
3. **Flight Agent starts** searching (shows spinner)
4. **User clicks "Cancel"**: Interruption signal sent
5. **Agent detects flag**: Stops gracefully, saves partial results
6. **UI updates**: Shows interruption message
7. **State preserved**: Next query resumes with context

## 🏗️ Architecture Overview

```
Frontend (Next.js) <--SSE Stream--> Backend (FastAPI + LangGraph)
     │                                        │
     │                                   StateGraph
     │                                        │
     │                          ┌─────────────┴─────────────┐
     │                          │                           │
  Chat UI              Coordinator Agent              Tools
     │                          │                           │
     │                 ┌────────┴────────┐          (search_flights,
     │                 │                 │           search_hotels,
  SSE Hook      Flight Agent      Hotel Agent        web_search)
     │                 │                 │
     │                 └─────────────────┘
     │                          │
 Cancel Button          State Management
                       (Checkpointing)
```

## 📂 Project Structure

```
travel-assistant/
├── backend/                 # Python FastAPI + LangGraph
│   ├── main.py             # FastAPI app with SSE endpoints
│   ├── graph.py            # LangGraph multi-agent workflow
│   ├── agents.py           # Agent implementations
│   ├── tools.py            # Search tools
│   ├── state.py            # State management schema
│   └── requirements.txt    # Python dependencies
├── src/
│   ├── app/
│   │   ├── page.tsx        # Landing page
│   │   └── chat/page.tsx   # Chat interface
│   ├── components/
│   │   ├── chat/           # Chat components
│   │   └── travel/         # Flight/hotel cards
│   └── hooks/
│       └── useSSEChat.ts   # SSE integration hook
└── .env.local              # Frontend config
```

## 🔧 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/stream` | POST | Stream agent responses via SSE |
| `/api/chat/cancel` | POST | Cancel active query |
| `/api/chat/status/:id` | GET | Get query status |
| `/api/chat/resume` | POST | Resume after interruption |
| `/api/health` | GET | Health check |

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # Should be 3.10+

# Reinstall dependencies
pip install -r requirements.txt

# Verify OpenAI API key
cat backend/.env | grep OPENAI_API_KEY
```

### Frontend connection error
```bash
# Verify backend is running
curl http://localhost:8000/api/health

# Should return: {"status": "healthy", ...}
```

### Interruption not working
- Click "Cancel Query" button in header while query is active
- Check browser console for errors
- Verify backend logs show interruption signal

## 📚 Documentation

- **Backend Details**: See `backend/README.md`
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **FastAPI Docs**: https://fastapi.tiangolo.com/

## 🎨 UI Features

- Dark theme with gradient backgrounds
- Fluid animations with Framer Motion
- Real-time agent status indicators
- Color-coded agents: Coordinator (Green), Flight (Blue), Hotel (Purple)
- Interruption controls with visual feedback

---

Built with ❤️ using LangGraph, FastAPI, Next.js, and Framer Motion