"""
Agent node implementations for the multi-agent travel planning system.
Each agent has specific responsibilities and can handle interruptions gracefully.
"""

from typing import Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from state import AgentState
import json
import time


# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)


async def coordinator_agent(state: AgentState) -> dict[str, Any]:
    """
    Coordinator Agent: Main orchestrator that analyzes user intent and routes to specialists.
    
    Responsibilities:
    - Analyze user queries to detect intent (flight, hotel, general info)
    - Route requests to appropriate specialized agents
    - Handle seamless handoffs between agents
    - Manage interruption context
    
    Inputs: User query, conversation history
    Outputs: Routing decision, detected intents, coordinator message
    """
    
    # Check for interruption at entry
    if state.get("should_interrupt", False):
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True,
            "messages": state["messages"] + [
                AIMessage(content=f"⏸️ Coordination interrupted: {state.get('interrupt_reason', 'User cancellation')}")
            ]
        }
    
    # Record agent activation
    state["previous_agents"].append("coordinator")
    state["agent_actions"].append({
        "agent": "coordinator",
        "action": "analyzing_query",
        "timestamp": time.time()
    })
    
    # Build system prompt for intent detection
    system_prompt = """You are a travel planning coordinator. Analyze the user's query and determine:

1. What type of assistance they need:
   - FLIGHT: Finding flights, booking flights, flight prices, schedules
   - HOTEL: Finding hotels, accommodations, lodging, places to stay
   - GENERAL: Travel tips, destinations, weather, visa info, attractions
   - BOTH: When user needs both flights and hotels

2. Extract key details:
   - Origin/destination cities
   - Dates if mentioned
   - Number of people
   - Budget constraints
   - Preferences

Respond ONLY with valid JSON:
{
  "intent": "flight|hotel|general|both",
  "confidence": 0.0-1.0,
  "details": {
    "origin": "city",
    "destination": "city",
    "dates": "date range",
    "passengers": number,
    "notes": "any special requirements"
  },
  "reasoning": "brief explanation"
}"""
    
    # Prepare messages for LLM
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User query: {state['user_query']}")
    ]
    
    # Add conversation history for context-aware routing
    if len(state["messages"]) > 1:
        messages.append(
            SystemMessage(content=f"Previous conversation context: {state['messages'][-2:]}")
        )
    
    # Get routing decision from LLM
    response = await llm.ainvoke(messages)
    
    # Parse routing decision
    try:
        decision = json.loads(response.content)
        intent = decision.get("intent", "general")
        details = decision.get("details", {})
        reasoning = decision.get("reasoning", "")
    except json.JSONDecodeError:
        # Fallback to keyword-based routing
        query_lower = state["user_query"].lower()
        if any(word in query_lower for word in ["flight", "fly", "airline", "airport"]):
            intent = "flight"
        elif any(word in query_lower for word in ["hotel", "stay", "accommodation", "lodge"]):
            intent = "hotel"
        else:
            intent = "general"
        details = {}
        reasoning = "Keyword-based fallback routing"
    
    # Determine next agent
    next_agent_mapping = {
        "flight": "flight_agent",
        "hotel": "hotel_agent",
        "general": "research_agent",
        "both": "flight_agent"  # Start with flights, hotel will be chained
    }
    next_agent = next_agent_mapping.get(intent, "research_agent")
    
    # Build coordinator response
    coordinator_message = f"🎯 I understand you're looking for {intent} assistance. {reasoning}. Routing to specialist..."
    
    # Update state
    return {
        **state,
        "current_agent": "coordinator",
        "next_agent": next_agent,
        "detected_intents": [intent],
        "coordinator_context": {
            "last_routing": intent,
            "extracted_details": details,
            "timestamp": time.time()
        },
        "messages": state["messages"] + [AIMessage(content=coordinator_message)],
        "status": "routed"
    }


async def flight_agent(state: AgentState) -> dict[str, Any]:
    """
    Flight Agent: Specialized agent for flight searches and bookings.
    
    Responsibilities:
    - Search flights using search_flights tool
    - Parse and format flight results
    - Handle flight-specific queries
    - Preserve partial results if interrupted
    
    Inputs: Flight search parameters from user query
    Outputs: Flight search results, formatted for display
    """
    
    # Check for interruption
    if state.get("should_interrupt", False):
        # Preserve any partial results
        state["partial_results"]["flights"] = "Search interrupted before completion"
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True,
            "messages": state["messages"] + [
                AIMessage(content="✈️ Flight search was interrupted. Partial results saved.")
            ]
        }
    
    # Record agent activation
    state["previous_agents"].append("flight_agent")
    state["active_tool_calls"].append("search_flights")
    
    # Import tools here to avoid circular dependency
    from tools import search_flights
    
    # Extract flight parameters from query
    query = state["user_query"].lower()
    
    # Simple parameter extraction (in production, use NER/LLM extraction)
    origin = "NYC"  # Default
    destination = "LAX"  # Default
    
    # Try to extract cities
    if "from" in query and "to" in query:
        parts = query.split("from")[1].split("to")
        if len(parts) == 2:
            origin = parts[0].strip().split()[0].upper()
            destination = parts[1].strip().split()[0].upper()
    
    # Call flight search tool with interruption check
    interruption_context = {
        "should_interrupt": state.get("should_interrupt", False),
        "partial_results": state.get("partial_results", {})
    }
    
    flight_results = await search_flights.ainvoke({
        "origin": origin,
        "destination": destination,
        "interruption_check": interruption_context
    })
    
    # Check if search was interrupted
    if flight_results.get("status") == "interrupted":
        state["partial_results"]["flights"] = flight_results.get("partial_results", {})
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True
        }
    
    # Format results
    flights = flight_results.get("flights", [])
    flight_summary = f"✈️ Found {len(flights)} flights from {origin} to {destination}:\n\n"
    
    for i, flight in enumerate(flights[:3], 1):
        flight_summary += f"{i}. {flight['airline']} - ${flight['price']}\n"
        flight_summary += f"   {flight['departure_time']} → {flight['arrival_time']} ({flight['duration']})\n"
        flight_summary += f"   Stops: {flight['stops']}, Available seats: {flight['available_seats']}\n\n"
    
    # Update flight context
    state["flight_context"] = {
        "last_search": {
            "origin": origin,
            "destination": destination,
            "results_count": len(flights),
            "timestamp": time.time()
        },
        "results": flight_results
    }
    
    # Record completed tool call
    state["completed_tool_calls"].append({
        "tool": "search_flights",
        "agent": "flight_agent",
        "timestamp": time.time(),
        "results_count": len(flights)
    })
    
    return {
        **state,
        "current_agent": "flight_agent",
        "messages": state["messages"] + [AIMessage(content=flight_summary)],
        "status": "complete"
    }


async def hotel_agent(state: AgentState) -> dict[str, Any]:
    """
    Hotel Agent: Specialized agent for hotel searches and bookings.
    
    Responsibilities:
    - Search hotels using search_hotels tool
    - Parse and format hotel results
    - Handle hotel-specific queries
    - Preserve partial results if interrupted
    
    Inputs: Hotel search parameters from user query
    Outputs: Hotel search results, formatted for display
    """
    
    # Check for interruption
    if state.get("should_interrupt", False):
        state["partial_results"]["hotels"] = "Search interrupted before completion"
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True,
            "messages": state["messages"] + [
                AIMessage(content="🏨 Hotel search was interrupted. Partial results saved.")
            ]
        }
    
    # Record agent activation
    state["previous_agents"].append("hotel_agent")
    state["active_tool_calls"].append("search_hotels")
    
    from tools import search_hotels
    
    # Extract location from query
    query = state["user_query"].lower()
    location = "Los Angeles"  # Default
    
    # Simple extraction
    if "in" in query:
        parts = query.split("in")
        if len(parts) > 1:
            location = parts[1].strip().split()[0].title()
    
    # Call hotel search tool
    interruption_context = {
        "should_interrupt": state.get("should_interrupt", False),
        "partial_results": state.get("partial_results", {})
    }
    
    hotel_results = await search_hotels.ainvoke({
        "location": location,
        "interruption_check": interruption_context
    })
    
    # Check if interrupted
    if hotel_results.get("status") == "interrupted":
        state["partial_results"]["hotels"] = hotel_results.get("partial_results", {})
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True
        }
    
    # Format results
    hotels = hotel_results.get("hotels", [])
    hotel_summary = f"🏨 Found {len(hotels)} hotels in {location}:\n\n"
    
    for i, hotel in enumerate(hotels[:3], 1):
        hotel_summary += f"{i}. {hotel['name']} - ${hotel['price_per_night']}/night\n"
        hotel_summary += f"   Rating: {hotel['rating']}⭐ ({hotel['reviews_count']} reviews)\n"
        hotel_summary += f"   Amenities: {', '.join(hotel['amenities'][:3])}\n\n"
    
    # Update hotel context
    state["hotel_context"] = {
        "last_search": {
            "location": location,
            "results_count": len(hotels),
            "timestamp": time.time()
        },
        "results": hotel_results
    }
    
    state["completed_tool_calls"].append({
        "tool": "search_hotels",
        "agent": "hotel_agent",
        "timestamp": time.time(),
        "results_count": len(hotels)
    })
    
    return {
        **state,
        "current_agent": "hotel_agent",
        "messages": state["messages"] + [AIMessage(content=hotel_summary)],
        "status": "complete"
    }


async def research_agent(state: AgentState) -> dict[str, Any]:
    """
    Research Agent: Handles general travel information queries.
    
    Responsibilities:
    - Answer general travel questions
    - Provide destination information
    - Share travel tips and advice
    
    Inputs: General travel query
    Outputs: Informative response
    """
    
    if state.get("should_interrupt", False):
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True,
            "messages": state["messages"] + [
                AIMessage(content="🔍 Research was interrupted.")
            ]
        }
    
    state["previous_agents"].append("research_agent")
    
    from tools import web_search
    
    # Perform web search
    search_results = await web_search.ainvoke({
        "query": state["user_query"],
        "max_results": 3
    })
    
    if search_results.get("status") == "interrupted":
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True
        }
    
    # Format search results
    results = search_results.get("results", [])
    response = f"🔍 Here's what I found about your travel query:\n\n"
    
    for result in results:
        response += f"• {result['title']}\n  {result['snippet']}\n\n"
    
    return {
        **state,
        "current_agent": "research_agent",
        "messages": state["messages"] + [AIMessage(content=response)],
        "status": "complete"
    }
