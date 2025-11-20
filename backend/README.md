# Travel Planning Assistant - Python Backend

Multi-agent travel planning system built with LangGraph, FastAPI, and Server-Sent Events (SSE) streaming.

## 🎯 Features

- **Multi-Agent Architecture**: Coordinator, Flight Agent, Hotel Agent, and Research Agent
- **Request Interruption**: Gracefully cancel queries while preserving partial results
- **Real-time Streaming**: SSE-based streaming for live agent updates
- **State Management**: Conversation history and context persistence via LangGraph checkpointing
- **Context Transfer**: Seamless handoffs between agents with preserved state

## 🏗️ Architecture

### Agent Responsibilities

**Coordinator Agent**
- Analyzes user queries to detect intent (flight, hotel, general)
- Routes requests to appropriate specialist agents
- Manages agent handoffs and context switching
- **Inputs**: User query, conversation history
- **Outputs**: Routing decision, detected intents

**Flight Agent**
- Searches flights between origin and destination
- Formats flight results for display
- Handles flight-specific queries
- **Inputs**: Origin, destination, date, passengers
- **Outputs**: Flight search results with pricing and schedules

**Hotel Agent**
- Finds hotels in specified locations
- Provides hotel details with amenities and ratings
- **Inputs**: Location, check-in/out dates, guests
- **Outputs**: Hotel search results with pricing and amenities

**Research Agent**
- Handles general travel information queries
- Performs web searches for destination info
- **Inputs**: General travel query
- **Outputs**: Informative responses with sources

### Request Interruption Mechanism

1. **Detection**: New user query arrives while agent is processing
2. **Cancellation**: Frontend calls `/api/chat/cancel` endpoint
3. **Flag Setting**: `should_interrupt` flag set in state
4. **Agent Check**: Each agent checks flag at start and during execution
5. **Preservation**: Partial results saved in `partial_results` dict
6. **Continuation**: New query can resume with preserved context via thread_id

## 🚀 Setup

### Prerequisites

- Python 3.10 or higher
- pip or conda for package management
- OpenAI API key (required)
- Tavily API key (optional, for real-time web search)

### Installation

1. **Clone or navigate to backend directory**
```bash
cd backend
```

2. **Create virtual environment**
```bash
# Using venv
python -m venv venv

# Activate on macOS/Linux
source venv/bin/activate

# Activate on Windows
venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API keys
nano .env  # or use your preferred editor
```

**Required environment variables:**
```bash
OPENAI_API_KEY=sk-your-openai-api-key-here
```

**Optional environment variables:**
```bash
TAVILY_API_KEY=tvly-your-tavily-key  # For real-time web search
LANGCHAIN_TRACING_V2=true            # For debugging with LangSmith
LANGCHAIN_API_KEY=your-langsmith-key
```

### Getting API Keys

**OpenAI API Key** (Required)
1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Click "Create new secret key"
4. Copy the key and add to `.env` file

**Tavily API Key** (Optional - for enhanced web search)
1. Go to https://tavily.com
2. Sign up for free account (includes free tier)
3. Navigate to API keys section
4. Copy key and add to `.env` file

## 🏃 Running the Server

### Development Mode (with auto-reload)
```bash
python main.py
```

### Production Mode
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Server will start at: **http://localhost:8000**

### Verify Server is Running
```bash
curl http://localhost:8000/
```

Expected response:
```json
{
  "status": "ok",
  "service": "Travel Planning Assistant API",
  "version": "1.0.0",
  "active_queries": 0
}
```

## 📡 API Endpoints

### POST `/api/chat/stream`
Stream agent responses via Server-Sent Events.

**Request:**
```json
{
  "query": "Find flights from NYC to LAX",
  "thread_id": "optional-thread-id",
  "user_id": "optional-user-id"
}
```

**Response:** SSE stream with events:
- `start`: Query initiated
- `agent_start`: Agent began processing
- `agent_message`: Agent produced message
- `agent_complete`: Agent finished
- `tool_start`: Tool execution started
- `tool_complete`: Tool finished
- `token`: LLM token (real-time streaming)
- `complete`: Query completed
- `interrupted`: Query was cancelled
- `error`: Error occurred

### POST `/api/chat/cancel`
Cancel an active query.

**Request:**
```json
{
  "query_id": "query-uuid",
  "reason": "User requested cancellation"
}
```

**Response:**
```json
{
  "status": "interrupted",
  "query_id": "query-uuid",
  "reason": "User requested cancellation",
  "timestamp": 1234567890.123
}
```

### GET `/api/chat/status/{query_id}`
Check query status.

**Response:**
```json
{
  "query_id": "query-uuid",
  "status": "active|interrupted|completed",
  "is_active": true,
  "is_interrupted": false,
  "query_info": {...}
}
```

### POST `/api/chat/resume`
Resume conversation after interruption.

**Request:**
```json
{
  "query": "Also check hotels",
  "thread_id": "thread-uuid",
  "previous_query_id": "previous-query-uuid"
}
```

**Response:** SSE stream (same as `/api/chat/stream`)

### GET `/api/chat/history/{thread_id}`
Retrieve conversation history.

**Response:**
```json
{
  "thread_id": "thread-uuid",
  "messages": [...],
  "state": {
    "current_agent": "flight_agent",
    "detected_intents": ["flight"],
    "previous_agents": ["coordinator", "flight_agent"]
  }
}
```

## 🧪 Testing

### Test with curl

**1. Start a query**
```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Find flights from NYC to LAX"}'
```

**2. Cancel a query** (get query_id from headers)
```bash
curl -X POST http://localhost:8000/api/chat/cancel \
  -H "Content-Type: application/json" \
  -d '{"query_id": "your-query-id", "reason": "Testing cancellation"}'
```

**3. Check status**
```bash
curl http://localhost:8000/api/chat/status/your-query-id
```

### Test with Python
```python
import requests
import json

# Start query
response = requests.post(
    "http://localhost:8000/api/chat/stream",
    json={"query": "Find hotels in Paris"},
    stream=True
)

query_id = response.headers.get("X-Query-ID")

# Stream events
for line in response.iter_lines():
    if line.startswith(b"data: "):
        event = json.loads(line[6:])
        print(f"Event: {event['type']}")
        
        # Cancel after first agent
        if event["type"] == "agent_complete":
            requests.post(
                "http://localhost:8000/api/chat/cancel",
                json={"query_id": query_id, "reason": "Test"}
            )
            break
```

## 📂 File Structure

```
backend/
├── main.py              # FastAPI app with SSE endpoints
├── graph.py             # LangGraph multi-agent workflow
├── agents.py            # Agent node implementations
├── tools.py             # Tool definitions (flight, hotel, web search)
├── state.py             # State management schema
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── .env                 # Your API keys (create this)
└── README.md           # This file
```

## 🔧 Troubleshooting

### "Module not found" errors
Make sure virtual environment is activated and dependencies are installed:
```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### "OpenAI API key not found"
Check `.env` file exists and contains valid API key:
```bash
cat .env | grep OPENAI_API_KEY
```

### SSE connection issues
- Ensure CORS origins include your frontend URL
- Check firewall isn't blocking port 8000
- Verify frontend uses correct backend URL

### Agent not responding
- Check logs for errors: `tail -f backend.log`
- Verify LLM API key is valid
- Test health endpoint: `curl http://localhost:8000/api/health`

## 🐛 Debugging

Enable detailed logging:
```python
# In main.py, change log level
logging.basicConfig(level=logging.DEBUG)
```

Enable LangSmith tracing:
```bash
# In .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=travel-assistant
```

View traces at: https://smith.langchain.com

## 📝 Development Notes

### Adding New Agents

1. Create agent function in `agents.py`:
```python
async def new_agent(state: AgentState) -> dict[str, Any]:
    # Check interruption
    if state.get("should_interrupt", False):
        return {..., "status": "interrupted"}
    
    # Agent logic here
    return {..., "status": "complete"}
```

2. Add node to graph in `graph.py`:
```python
builder.add_node("new_agent", new_agent)
```

3. Update routing logic in `route_after_coordinator()`

### Adding New Tools

1. Define tool in `tools.py`:
```python
@tool
async def new_tool(param: str, interruption_check: Optional[dict] = None) -> dict:
    if interruption_check and interruption_check.get("should_interrupt"):
        return {"status": "interrupted"}
    
    # Tool logic
    return {"status": "success", "result": ...}
```

2. Import in agent and use:
```python
from tools import new_tool
result = await new_tool.ainvoke({...})
```

## 📚 Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Server-Sent Events Spec](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

## 📄 License

MIT License - See LICENSE file for details
