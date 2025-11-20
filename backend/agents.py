"""
Agent node implementations for the multi-agent travel planning system.
Each agent has specific responsibilities and can handle interruptions gracefully.
"""

from typing import Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from state import AgentState
import json
import time
import re
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging


# Load env early
load_dotenv()
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env.local", override=False)

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    temperature=0,
    streaming=True,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)


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
            HumanMessage(content=f"[Context] Previous conversation (last 2 turns): {state['messages'][-2:]}")
        )
    
    # Get routing decision from LLM
    response = await llm.ainvoke(messages)
    
    # Parse routing decision robustly
    raw_text = None
    if isinstance(response, str):
        raw_text = response
    elif hasattr(response, "content"):
        raw_text = response.content
    else:
        raw_text = str(response)

    intent = "general"
    details: dict[str, Any] = {}
    reasoning = ""

    parsed: Any = None
    if isinstance(raw_text, str):
        # Try to extract first JSON object from the text
        match = re.search(r"\{[\s\S]*\}", raw_text)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                parsed = None
    elif isinstance(raw_text, dict):
        parsed = raw_text

    if isinstance(parsed, dict):
        intent = parsed.get("intent", "general")
        details = parsed.get("details", {}) or {}
        reasoning = parsed.get("reasoning", "")
    else:
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

    # Aggregate parameters from entire conversation history
    human_texts = []
    for m in state.get("messages", []):
        try:
            if isinstance(m, HumanMessage):
                human_texts.append(m.content if hasattr(m, "content") else str(m))
        except Exception:
            continue
    # Include current query explicitly
    human_texts.append(state.get("user_query", ""))
    history_text = " \n".join([t for t in human_texts if isinstance(t, str)])

    # Patterns
    date_pattern = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
    explicit_id_pattern = re.compile(r"\b[A-Z]{3}\.(?:AIRPORT|CITY)\b")
    iata_pattern = re.compile(r"\b[A-Z]{3}\b")

    # Extract explicit fromId/toId tokens first
    explicit_ids = explicit_id_pattern.findall(history_text)
    from_id = explicit_ids[0] if len(explicit_ids) >= 1 else None
    to_id = explicit_ids[1] if len(explicit_ids) >= 2 else None

    # If missing, try to infer from "X to Y" phrasing with IATA codes
    if not (from_id and to_id):
        # Simple from/to pattern
        m_from_to = re.search(r"from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+)", history_text, flags=re.IGNORECASE)
        if m_from_to:
            cand_from = m_from_to.group(1).strip()
            cand_to = m_from_to.group(2).strip()
            # If looks like IATA
            if re.fullmatch(r"[A-Z]{3}", cand_from.upper()):
                from_id = cand_from.upper() + ".AIRPORT"
            if re.fullmatch(r"[A-Z]{3}", cand_to.upper()):
                to_id = cand_to.upper() + ".AIRPORT"

    # If still missing, use any standalone IATA codes (take first two order of appearance)
    if not (from_id and to_id):
        iatas = [tok for tok in iata_pattern.findall(history_text) if len(tok) == 3 and tok.isupper()]
        # Filter out common words accidentally in caps
        common = {"USA", "THE", "AND"}
        iatas = [x for x in iatas if x not in common]
        if not from_id and len(iatas) >= 1:
            from_id = iatas[0] + ".AIRPORT"
        if not to_id and len(iatas) >= 2:
            to_id = iatas[1] + ".AIRPORT"

    # Map common city names to CITY codes if present in text
    city_aliases = {
        "new york": "NYC.CITY",
        "mumbai": "BOM.AIRPORT",
        "bombay": "BOM.AIRPORT",
        "delhi": "DEL.AIRPORT",
        "new delhi": "DEL.AIRPORT",
        "london": "LON.CITY",
        "paris": "PAR.CITY",
    }
    lower_text = history_text.lower()
    for name, code in city_aliases.items():
        if name in lower_text:
            # If destination not set, prefer to assign to_id
            if not to_id:
                to_id = code
            elif not from_id:
                from_id = code

    # Extract date
    date_match = date_pattern.search(history_text)
    depart_date = date_match.group(0) if date_match else None

    # Assume reasonable defaults if still missing
    assumed = []
    if not from_id and to_id:
        from_id = "BOM.AIRPORT"
        assumed.append("fromId=BOM.AIRPORT")
    if not to_id and from_id:
        to_id = "DEL.AIRPORT"
        assumed.append("toId=DEL.AIRPORT")
    if not from_id and not to_id:
        from_id = "BOM.AIRPORT"
        to_id = "DEL.AIRPORT"
        assumed.append("fromId=BOM.AIRPORT, toId=DEL.AIRPORT")
    if not depart_date:
        depart_date = (datetime.utcnow() + timedelta(days=21)).strftime("%Y-%m-%d")
        assumed.append(f"departDate={depart_date}")
    
    # Call flight search tool with interruption check
    interruption_context = {
        "should_interrupt": state.get("should_interrupt", False),
        "partial_results": state.get("partial_results", {})
    }
    
    flight_results = await search_flights.ainvoke({
        "origin": from_id,
        "destination": to_id,
        "date": depart_date,
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
    
    # Handle tool errors explicitly so the user sees what's wrong
    if flight_results.get("status") == "error":
        err_msg = flight_results.get("message") or "Flight search error"
        code = flight_results.get("code")
        detail = f" (code {code})" if code else ""
        error_text = f"⚠️ Flight search failed{detail}: {err_msg}"
        return {
            **state,
            "current_agent": "flight_agent",
            "messages": state["messages"] + [AIMessage(content=error_text)],
            "status": "complete"
        }
    
    # Format results: try to extract top options from response schema, with safe fallbacks
    assumed_text = (" Assumed: " + ", ".join(assumed) + ".") if assumed else ""
    base_line = f"✈️ Searching live flights from {from_id} to {to_id} on {depart_date}." + assumed_text

    # Attempt to find itineraries/tickets
    results_payload = flight_results.get("results")

    # Log the full results payload (safely truncated) for debugging/inspection
    try:
        logger = logging.getLogger(__name__)
        payload_for_log = results_payload
        if not isinstance(payload_for_log, (str, bytes)):
            payload_for_log = json.dumps(payload_for_log, ensure_ascii=False, default=str)
        if isinstance(payload_for_log, bytes):
            payload_for_log = payload_for_log.decode(errors="ignore")
        if isinstance(payload_for_log, str) and len(payload_for_log) > 4000:
            payload_for_log = payload_for_log[:4000] + "... [truncated]"
        logger.info(f"Flight API raw results: {payload_for_log}")
    except Exception:
        pass
    top_lines: list[str] = []
    top_structured: list[dict[str, Any]] = []
    try:
        data_obj = results_payload if isinstance(results_payload, dict) else {}

        # 1) Aggregation summary if present
        agg = None
        root_obj = data_obj.get("data") if isinstance(data_obj.get("data"), dict) else data_obj
        if isinstance(root_obj, dict):
            agg = root_obj.get("aggregation")
        if isinstance(agg, dict):
            total = agg.get("totalCount") or agg.get("filteredTotalCount")
            stops_info = agg.get("stops") if isinstance(agg.get("stops"), list) else []
            if total:
                top_lines.append(f"Total options: {total}")
            for s in stops_info[:2]:
                try:
                    num = s.get("numberOfStops")
                    cnt = s.get("count")
                    mp = s.get("minPrice") or {}
                    cur = mp.get("currencyCode") or ""
                    units = mp.get("units")
                    nanos = mp.get("nanos") or 0
                    price_num = units + (nanos / 1e9 if isinstance(nanos, (int, float)) else 0)
                    cheap = s.get("cheapestAirline") or {}
                    cheap_name = cheap.get("name") or cheap.get("code")
                    label = "Non-stop" if num == 0 else ("1-stop" if num == 1 else f"{num}-stops")
                    if cnt and units is not None:
                        top_lines.append(f"{label}: {cnt} from {price_num:.0f} {cur} (e.g., {cheap_name})")
                except Exception:
                    continue
        # 2) Find list of options under common keys, including nested under data
        candidate_lists = []
        def add_lists_from(obj: dict):
            for key in ["results", "itineraries", "itineraryList", "flights", "items"]:
                val = obj.get(key)
                if isinstance(val, list) and val:
                    candidate_lists.append(val)
        if isinstance(data_obj, dict):
            add_lists_from(data_obj)
            d = data_obj.get("data")
            if isinstance(d, dict):
                add_lists_from(d)
            elif isinstance(d, list) and d:
                candidate_lists.append(d)
        # Fallback: scan any dict value that is a non-empty list
        if not candidate_lists:
            for v in data_obj.values():
                if isinstance(v, list) and v:
                    candidate_lists.append(v)
                    break

        options = candidate_lists[0] if candidate_lists else []
        # Build up to 10 structured options; also create up to 3 summary lines
        for opt in options[:10]:
            # Try various fields
            price = None
            currency = None
            airline = None
            depart_time = None
            arrive_time = None
            duration = None
            stops = None

            if isinstance(opt, dict):
                # price fields
                price = (
                    (opt.get("price") if isinstance(opt.get("price"), (int, float, str)) else None)
                    or (opt.get("price", {}).get("amount") if isinstance(opt.get("price"), dict) else None)
                    or (opt.get("pricing", {}).get("total") if isinstance(opt.get("pricing"), dict) else None)
                )
                currency = (
                    (opt.get("currency"))
                    or (opt.get("price", {}).get("currency") if isinstance(opt.get("price"), dict) else None)
                    or (opt.get("pricing", {}).get("currency") if isinstance(opt.get("pricing"), dict) else None)
                )
                # carrier/segments
                segments = (
                    opt.get("segments") or opt.get("legs") or opt.get("itinerarySegments")
                )
                if isinstance(segments, list) and segments:
                    first_seg = segments[0]
                    last_seg = segments[-1]
                    if isinstance(first_seg, dict):
                        airline = first_seg.get("carrier") or first_seg.get("airline") or first_seg.get("marketingCarrier") or airline
                        depart_time = first_seg.get("departureTime") or first_seg.get("departure") or first_seg.get("departureDateTime")
                    if isinstance(last_seg, dict):
                        arrive_time = last_seg.get("arrivalTime") or last_seg.get("arrival") or last_seg.get("arrivalDateTime")
                    stops = max(0, len(segments) - 1)
                # duration
                duration = opt.get("duration") or opt.get("totalDuration")

            # Accumulate a structured item for UI parsing
            top_structured.append({
                "airline": airline or "",
                "price": price if isinstance(price, (int, float, str)) else (
                    {"amount": price.get("amount") or price.get("units"), "currency": currency or price.get("currency") or price.get("currencyCode")}
                    if isinstance(price, dict) else None
                ),
                "currency": currency or "",
                "from": from_id,
                "to": to_id,
                "departTime": depart_time or "",
                "arriveTime": arrive_time or "",
                "duration": duration or "",
                "stops": stops if isinstance(stops, int) else None,
                "segments": opt.get("segments") if isinstance(opt, dict) else None,
            })

            # Also build a concise bullet line for readability (first 3 only)
            if len(top_lines) >= 3:
                continue
            line = "• "
            if airline:
                line += f"{airline} "
            if price:
                if currency:
                    line += f"{price} {currency}"
                else:
                    line += f"{price}"
            if depart_time or arrive_time:
                line += f" | {depart_time or ''} → {arrive_time or ''}"
            if duration:
                line += f" | {duration}"
            if stops is not None:
                line += f" | Stops: {stops}"

            # Only add if we got something meaningful
            if len(line) > 2:
                top_lines.append(line)
    except Exception:
        top_lines = []

    # If we still have no structured options, try synthesizing from airlines aggregation
    if not top_structured:
        try:
            root_obj = data_obj.get("data") if isinstance(data_obj.get("data"), dict) else data_obj
            agg_obj = root_obj.get("aggregation") if isinstance(root_obj, dict) else None
            airlines_list = agg_obj.get("airlines") if isinstance(agg_obj, dict) else None
            if isinstance(airlines_list, list) and airlines_list:
                for al in airlines_list[:10]:
                    if not isinstance(al, dict):
                        continue
                    name = al.get("name") or al.get("iataCode") or ""
                    mp = al.get("minPricePerAdult") or al.get("minPrice") or {}
                    price_obj = None
                    currency = None
                    if isinstance(mp, dict):
                        amount = mp.get("units") or mp.get("amount")
                        currency = mp.get("currencyCode") or mp.get("currency")
                        price_obj = {"amount": amount, "currency": currency}
                    top_structured.append({
                        "airline": name,
                        "airlineCode": al.get("iataCode"),
                        "logoUrl": al.get("logoUrl"),
                        "count": al.get("count"),
                        "price": price_obj,
                        "currency": currency or "",
                        "from": from_id,
                        "to": to_id,
                        "departTime": "",
                        "arriveTime": "",
                        "duration": "",
                        "stops": None,
                        "segments": None,
                    })
        except Exception:
            pass

    if top_lines:
        flight_summary = base_line + "\n\n" + "\n".join(top_lines)
    else:
        # Fallback: include a compact snippet from payload to show meaningful output
        try:
            payload_obj = None
            if isinstance(results_payload, dict):
                payload_obj = results_payload.get("data", results_payload)
            snippet = json.dumps(payload_obj, ensure_ascii=False) if payload_obj is not None else str(results_payload)
            if len(snippet) > 800:
                snippet = snippet[:800] + "..."
            flight_summary = base_line + ("\n\n" + snippet if snippet else "")
        except Exception:
            flight_summary = base_line

    # Append a compact JSON block of top options for the chat UI to parse into cards
    try:
        compact = {
            "items": top_structured[:10]
        }
        flight_summary = flight_summary + "\n\n" + json.dumps(compact, ensure_ascii=False)
    except Exception:
        pass
    
    # Update flight context
    state["flight_context"] = {
        "last_search": {
            "origin": from_id,
            "destination": to_id,
            "timestamp": time.time()
        },
        "results": flight_results
    }
    
    # Record completed tool call
    state["completed_tool_calls"].append({
        "tool": "search_flights",
        "agent": "flight_agent",
        "timestamp": time.time(),
        "results_count": None
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
