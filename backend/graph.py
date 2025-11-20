"""
LangGraph multi-agent graph construction.
Defines the workflow, routing logic, and state transitions.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from state import AgentState
from agents import coordinator_agent, flight_agent, hotel_agent, research_agent
from typing import Literal


def route_after_coordinator(state: AgentState) -> Literal["flight_agent", "hotel_agent", "research_agent"]:
    """
    Conditional routing logic after coordinator analysis.
    
    Routes to the appropriate specialist agent based on detected intent.
    """
    next_agent = state.get("next_agent", "research_agent")
    
    # Validate routing
    valid_agents = ["flight_agent", "hotel_agent", "research_agent"]
    if next_agent not in valid_agents:
        return "research_agent"
    
    return next_agent  # type: ignore


def should_continue(state: AgentState) -> Literal["coordinator", "end"]:
    """
    Determine if the conversation should continue or end.
    
    Continues if:
    - User has follow-up queries
    - Seamless handoff is needed (e.g., "also check hotels")
    
    Ends if:
    - Query is complete
    - Interruption occurred
    """
    if state.get("should_interrupt", False) or state.get("is_interrupted", False):
        return "end"
    
    if state.get("needs_continuation", False):
        return "coordinator"
    
    return "end"


def build_graph() -> StateGraph:
    """
    Build the complete multi-agent StateGraph.
    
    Graph structure:
    START → Coordinator → [Flight Agent | Hotel Agent | Research Agent] → END
    
    Features:
    - State persistence via MemorySaver checkpointer
    - Conditional routing based on intent
    - Support for interruptions at any node
    - Conversation history maintained across agents
    
    Returns:
        Compiled StateGraph ready for execution
    """
    
    # Initialize graph builder with AgentState
    builder = StateGraph(AgentState)
    
    # Add agent nodes
    builder.add_node("coordinator", coordinator_agent)
    builder.add_node("flight_agent", flight_agent)
    builder.add_node("hotel_agent", hotel_agent)
    builder.add_node("research_agent", research_agent)
    
    # Define edges and routing
    # START → Coordinator (always)
    builder.add_edge(START, "coordinator")
    
    # Coordinator → Specialist (conditional)
    builder.add_conditional_edges(
        "coordinator",
        route_after_coordinator,
        {
            "flight_agent": "flight_agent",
            "hotel_agent": "hotel_agent",
            "research_agent": "research_agent"
        }
    )
    
    # Specialist → END or back to Coordinator (for handoffs)
    builder.add_conditional_edges(
        "flight_agent",
        should_continue,
        {
            "coordinator": "coordinator",
            "end": END
        }
    )
    
    builder.add_conditional_edges(
        "hotel_agent",
        should_continue,
        {
            "coordinator": "coordinator",
            "end": END
        }
    )
    
    builder.add_conditional_edges(
        "research_agent",
        should_continue,
        {
            "coordinator": "coordinator",
            "end": END
        }
    )
    
    # Compile graph with checkpointer for state persistence
    checkpointer = MemorySaver()
    
    graph = builder.compile(
        checkpointer=checkpointer,
        # Enable interrupts for human-in-the-loop (optional)
        interrupt_before=[],  # Add node names to pause before execution
        interrupt_after=[]    # Add node names to pause after execution
    )
    
    return graph


# Global graph instance
travel_graph = build_graph()
