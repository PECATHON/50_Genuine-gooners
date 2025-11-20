"""
FastAPI server with Server-Sent Events (SSE) streaming for multi-agent system.
Handles request interruption, cancellation, and state management.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import asyncio
import json
import uuid
import time
import logging
from contextlib import asynccontextmanager

from graph import travel_graph
from state import AgentState
from langchain_core.messages import HumanMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track active queries for interruption
active_queries: dict[str, dict] = {}
interruption_flags: dict[str, bool] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app."""
    logger.info("🚀 Starting Travel Planning Assistant API")
    yield
    logger.info("🛑 Shutting down Travel Planning Assistant API")


# Initialize FastAPI app
app = FastAPI(
    title="Travel Planning Assistant API",
    description="Multi-agent travel planning system with LangGraph and interruption handling",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ REQUEST/RESPONSE MODELS ============

class QueryRequest(BaseModel):
    """Request model for chat queries."""
    query: str
    thread_id: Optional[str] = None
    user_id: Optional[str] = None


class CancelRequest(BaseModel):
    """Request model for cancelling a query."""
    query_id: str
    reason: str = "User requested cancellation"


class ResumeRequest(BaseModel):
    """Request model for resuming after interruption."""
    query: str
    thread_id: str
    previous_query_id: Optional[str] = None


# ============ SSE EVENT GENERATOR ============

async def generate_sse_events(
    query_id: str,
    user_query: str,
    thread_id: str
) -> AsyncGenerator[str, None]:
    """
    Generate Server-Sent Events from LangGraph execution.
    
    Streams agent actions, tool calls, and results in real-time.
    Supports graceful interruption via interruption_flags.
    """
    try:
        logger.info(f"📨 Starting SSE stream for query: {query_id}")
        
        # Send initial status
        yield f"data: {json.dumps({'type': 'start', 'query_id': query_id, 'timestamp': time.time()})}\n\n"
        
        # Prepare initial state
        initial_state = {
            "messages": [HumanMessage(content=user_query)],
            "user_query": user_query,
            "query_id": query_id,
            "thread_id": thread_id,
            "should_interrupt": False,
            "is_interrupted": False,
            "status": "processing",
            "current_agent": "",
            "previous_agents": [],
            "agent_actions": [],
            "partial_results": {},
            "flight_context": {},
            "hotel_context": {},
            "coordinator_context": {},
            "detected_intents": [],
            "active_tool_calls": [],
            "completed_tool_calls": [],
            "needs_continuation": False
        }
        
        # Configuration for checkpointing
        config = {
            "configurable": {
                "thread_id": thread_id
            },
            "run_id": query_id
        }
        
        # Track query
        active_queries[query_id] = {
            "thread_id": thread_id,
            "query": user_query,
            "start_time": time.time(),
            "status": "active"
        }
        
        # Stream graph execution
        async for event in travel_graph.astream_events(
            initial_state,
            config,
            version="v2"
        ):
            # Check for interruption
            if interruption_flags.get(query_id, False):
                logger.info(f"⏸️ Query {query_id} interrupted")
                yield f"data: {json.dumps({'type': 'interrupted', 'reason': 'User cancelled', 'timestamp': time.time()})}\n\n"
                break
            
            event_type = event.get("event")
            event_data = event.get("data", {})
            event_name = event.get("name", "")
            
            # Handle different event types
            if event_type == "on_chain_start":
                # Agent started
                agent_name = event_name
                if any(x in agent_name for x in ["coordinator", "flight", "hotel", "research"]):
                    yield f"data: {json.dumps({'type': 'agent_start', 'agent': agent_name, 'timestamp': time.time()})}\n\n"
            
            elif event_type == "on_chain_end":
                # Agent completed
                agent_name = event_name
                if any(x in agent_name for x in ["coordinator", "flight", "hotel", "research"]):
                    output = event_data.get("output", {})
                    
                    # Extract messages if available
                    messages = output.get("messages", [])
                    if messages:
                        last_message = messages[-1]
                        content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                        
                        yield f"data: {json.dumps({'type': 'agent_message', 'agent': agent_name, 'content': content, 'timestamp': time.time()})}\n\n"
                    
                    # Send agent completion
                    yield f"data: {json.dumps({'type': 'agent_complete', 'agent': agent_name, 'timestamp': time.time()})}\n\n"
            
            elif event_type == "on_chat_model_stream":
                # LLM token streaming
                chunk = event_data.get("chunk", {})
                if hasattr(chunk, 'content'):
                    content = chunk.content
                    if content:
                        yield f"data: {json.dumps({'type': 'token', 'content': content, 'timestamp': time.time()})}\n\n"
            
            elif event_type == "on_tool_start":
                # Tool execution started
                tool_name = event_data.get("input", {}).get("tool", "") or event_name
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'timestamp': time.time()})}\n\n"
            
            elif event_type == "on_tool_end":
                # Tool execution completed
                tool_name = event_name
                output = event_data.get("output", {})
                yield f"data: {json.dumps({'type': 'tool_complete', 'tool': tool_name, 'timestamp': time.time()})}\n\n"
            
            # Yield control to event loop
            await asyncio.sleep(0)
        
        # Send completion event
        logger.info(f"✅ Query {query_id} completed")
        yield f"data: {json.dumps({'type': 'complete', 'query_id': query_id, 'timestamp': time.time()})}\n\n"
    
    except asyncio.CancelledError:
        logger.info(f"❌ Query {query_id} cancelled")
        yield f"data: {json.dumps({'type': 'cancelled', 'query_id': query_id, 'timestamp': time.time()})}\n\n"
    
    except Exception as e:
        logger.error(f"❌ Error in query {query_id}: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': time.time()})}\n\n"
    
    finally:
        # Cleanup
        active_queries.pop(query_id, None)
        interruption_flags.pop(query_id, None)
        logger.info(f"🧹 Cleaned up query {query_id}")


# ============ API ENDPOINTS ============

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Travel Planning Assistant API",
        "version": "1.0.0",
        "active_queries": len(active_queries)
    }


@app.post("/api/chat/stream")
async def stream_chat(request: QueryRequest):
    """
    Stream agent responses via Server-Sent Events.
    
    This endpoint:
    1. Generates a unique query ID
    2. Initializes the multi-agent graph
    3. Streams events in real-time
    4. Supports interruption via /api/chat/cancel
    """
    query_id = str(uuid.uuid4())
    thread_id = request.thread_id or str(uuid.uuid4())
    
    # Initialize interruption flag
    interruption_flags[query_id] = False
    
    logger.info(f"🔵 New query: {query_id} | Thread: {thread_id} | Query: {request.query[:50]}...")
    
    return StreamingResponse(
        generate_sse_events(query_id, request.query, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Query-ID": query_id,
            "X-Thread-ID": thread_id,
            "Access-Control-Expose-Headers": "X-Query-ID, X-Thread-ID"
        }
    )


@app.post("/api/chat/cancel")
async def cancel_query(request: CancelRequest):
    """
    Cancel an active query gracefully.
    
    Sets the interruption flag which is checked by agents during execution.
    Preserves partial results for context transfer.
    """
    query_id = request.query_id
    
    if query_id not in active_queries and query_id not in interruption_flags:
        raise HTTPException(
            status_code=404,
            detail=f"Query {query_id} not found or already completed"
        )
    
    # Set interruption flag
    interruption_flags[query_id] = True
    
    # Update query status
    if query_id in active_queries:
        active_queries[query_id]["status"] = "interrupted"
        active_queries[query_id]["interrupt_time"] = time.time()
        active_queries[query_id]["interrupt_reason"] = request.reason
    
    logger.info(f"⏸️ Interruption requested for query: {query_id} | Reason: {request.reason}")
    
    return {
        "status": "interrupted",
        "query_id": query_id,
        "reason": request.reason,
        "timestamp": time.time()
    }


@app.get("/api/chat/status/{query_id}")
async def get_query_status(query_id: str):
    """
    Get the current status of a query.
    
    Returns information about whether the query is active, interrupted, or completed.
    """
    query_info = active_queries.get(query_id)
    is_interrupted = interruption_flags.get(query_id, False)
    
    if not query_info and query_id not in interruption_flags:
        return {
            "query_id": query_id,
            "status": "not_found",
            "message": "Query not found or already completed"
        }
    
    return {
        "query_id": query_id,
        "status": query_info.get("status") if query_info else "completed",
        "is_active": query_id in active_queries,
        "is_interrupted": is_interrupted,
        "query_info": query_info
    }


@app.post("/api/chat/resume")
async def resume_query(request: ResumeRequest):
    """
    Resume conversation after interruption.
    
    Uses the thread_id to retrieve previous state from checkpointer
    and continues with the new query while preserving context.
    """
    query_id = str(uuid.uuid4())
    thread_id = request.thread_id
    
    logger.info(f"🔄 Resuming thread: {thread_id} | New query: {request.query[:50]}...")
    
    # Clear any previous interruption flags for this thread
    if request.previous_query_id:
        interruption_flags.pop(request.previous_query_id, None)
    
    interruption_flags[query_id] = False
    
    return StreamingResponse(
        generate_sse_events(query_id, request.query, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Query-ID": query_id,
            "X-Thread-ID": thread_id,
            "Access-Control-Expose-Headers": "X-Query-ID, X-Thread-ID"
        }
    )


@app.get("/api/chat/history/{thread_id}")
async def get_chat_history(thread_id: str):
    """
    Retrieve conversation history for a thread.
    
    Uses the checkpointer to get all messages and state for the thread.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = travel_graph.get_state(config)
        
        if not state_snapshot or not state_snapshot.values:
            return {
                "thread_id": thread_id,
                "messages": [],
                "status": "not_found"
            }
        
        state = state_snapshot.values
        messages = state.get("messages", [])
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.__class__.__name__,
                "content": msg.content if hasattr(msg, 'content') else str(msg),
                "timestamp": getattr(msg, 'timestamp', None)
            })
        
        return {
            "thread_id": thread_id,
            "messages": formatted_messages,
            "state": {
                "current_agent": state.get("current_agent"),
                "detected_intents": state.get("detected_intents"),
                "previous_agents": state.get("previous_agents"),
                "status": state.get("status")
            }
        }
    
    except Exception as e:
        logger.error(f"Error retrieving history for thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "active_queries": len(active_queries),
        "interruption_flags": len(interruption_flags),
        "graph_status": "initialized"
    }


# ============ ERROR HANDLERS ============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return {
        "error": "Internal server error",
        "message": str(exc),
        "timestamp": time.time()
    }


if __name__ == "__main__":
    import uvicorn
    import os
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"🚀 Starting server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
