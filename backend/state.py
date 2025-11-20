"""
State management for multi-agent travel planning system.
Handles conversation context, agent coordination, and interruption handling.
"""

from typing import Annotated, Optional, Any
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState
from langchain_core.messages import BaseMessage
import operator


class AgentState(MessagesState):
    """
    Complete multi-agent state with interruption handling.
    
    This state is shared across all agents and persists throughout the conversation.
    It supports:
    - Message history management
    - Agent coordination and routing
    - Request interruption and cancellation
    - Partial result preservation
    - Context transfer between agents
    """
    
    # Messages and conversation history (inherited from MessagesState)
    messages: Annotated[list[BaseMessage], operator.add]
    
    # Agent coordination
    current_agent: str = Field(default="coordinator", description="Currently active agent")
    next_agent: str = Field(default="", description="Agent to route to next")
    previous_agents: list[str] = Field(default_factory=list, description="History of agent activations")
    
    # User query metadata
    user_query: str = Field(default="", description="Current user query")
    original_query: str = Field(default="", description="Original query before interruption")
    query_id: str = Field(default="", description="Unique query identifier")
    thread_id: str = Field(default="", description="Conversation thread identifier")
    
    # Interruption handling - CRITICAL for request cancellation
    should_interrupt: bool = Field(default=False, description="Flag to trigger graceful interruption")
    is_interrupted: bool = Field(default=False, description="Whether current operation was interrupted")
    interrupt_reason: str = Field(default="", description="Reason for interruption")
    interrupt_timestamp: Optional[float] = Field(default=None, description="When interruption occurred")
    
    # Partial results preservation
    partial_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved partial results from interrupted operations"
    )
    
    # Agent-specific context (persists across interruptions)
    flight_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Flight search context and history"
    )
    hotel_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Hotel search context and history"
    )
    coordinator_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Coordinator routing context"
    )
    
    # Status tracking for streaming updates
    status: str = Field(default="processing", description="Current operation status")
    agent_actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Track all agent actions for debugging"
    )
    
    # Tool call tracking
    active_tool_calls: list[str] = Field(
        default_factory=list,
        description="Currently executing tools"
    )
    completed_tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
        description="History of completed tool calls"
    )
    
    # User intent analysis
    detected_intents: list[str] = Field(
        default_factory=list,
        description="Detected user intents (flight, hotel, general)"
    )
    
    # Continuation flag for seamless handoffs
    needs_continuation: bool = Field(
        default=False,
        description="Whether conversation needs continuation from previous context"
    )


class QueryMetadata(BaseModel):
    """Metadata for tracking individual queries."""
    query_id: str
    thread_id: str
    timestamp: float
    query_text: str
    detected_intents: list[str] = Field(default_factory=list)


class InterruptionContext(BaseModel):
    """Context preserved during interruption."""
    original_query: str
    interrupted_agent: str
    partial_results: dict[str, Any]
    timestamp: float
    reason: str
    preserved_state: dict[str, Any] = Field(default_factory=dict)
