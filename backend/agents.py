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
    - Analyze user queries to detect intent (flight, hotel, attractions, general info)
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
   - ATTRACTION: Sightseeing, attractions, things to do, places to visit
   - GENERAL: Travel tips, destinations, weather, visa info
   - BOTH: When user needs both flights and hotels

2. Extract key details:
   - Origin/destination cities
   - Dates if mentioned
   - Number of people
   - Budget constraints
   - Preferences

Respond ONLY with valid JSON:
{
  "intent": "flight|hotel|attraction|general|both",
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
    
    # Get routing decision from LLM with graceful fallback on errors
    try:
        # Verify Google API key is properly loaded
        import os
        google_api_key = os.getenv('GOOGLE_API_KEY')
        if not google_api_key or google_api_key == 'YOUR_GOOGLE_API_KEY':
            raise ValueError("GOOGLE_API_KEY is not properly set in environment variables")
            
        response = await llm.ainvoke(messages)
    except Exception as e:
        error_msg = f"⚠️ Coordinator model error: {str(e)[:200]}"
        if "API key" in str(e):
            error_msg = "⚠️ Google API key issue. Please check your GOOGLE_API_KEY in .env.local"
        
        # Log the error
        try:
            logger = logging.getLogger(__name__)
            logger.error(f"Coordinator LLM error: {str(e)}")
        except Exception:
            pass
            
        # Fallback to research agent with detailed message
        fallback_msg = (
            f"{error_msg}\n"
            "🔍 Falling back to research agent for your query..."
        )
        
        # If this is an API key error, suggest checking the key
        if "API key" in str(e):
            fallback_msg += "\n\nℹ️ Note: Please ensure you've:"
            fallback_msg += "\n1. Set a valid Google API key in .env.local"
            fallback_msg += "\n2. Restarted your backend server after updating the key"
            fallback_msg += "\n3. Enabled the Gemini API for your Google Cloud project"
        
        return {
            **state,
            "current_agent": "coordinator",
            "next_agent": "research_agent",
            "detected_intents": ["general"],
            "coordinator_context": {
                "last_routing": "general",
                "extracted_details": {},
                "timestamp": time.time(),
                "error": str(e),
            },
            "messages": state["messages"] + [AIMessage(content=fallback_msg)],
            "status": "routed",
        }

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
        elif any(word in query_lower for word in ["attraction", "things to do", "places to visit", "sightseeing"]):
            intent = "attraction"
        else:
            intent = "general"
        details = {}
        reasoning = "Keyword-based fallback routing"
    
    # Determine next agent
    next_agent_mapping = {
        "flight": "flight_agent",
        "hotel": "hotel_agent",
        "attraction": "attractions_agent",
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

    # Ensure current raw query is defined for parsing below
    raw_query = state.get("user_query", "")

    # Patterns
    date_pattern = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
    explicit_id_pattern = re.compile(r"\b[A-Z]{3}\.(?:AIRPORT|CITY)\b")
    iata_pattern = re.compile(r"\b[A-Z]{3}\b")

    # Extract explicit fromId/toId prioritizing the most recent user query
    from_id = None
    to_id = None
    # 1) Parse current raw_query first (highest priority)
    current_explicit = explicit_id_pattern.findall(raw_query)
    current_tokens = re.findall(r"\b[A-Z]{3}\.(?:AIRPORT|CITY)\b", raw_query)
    if len(current_tokens) >= 1:
        from_id = current_tokens[0]
    if len(current_tokens) >= 2:
        to_id = current_tokens[1]
    # Try simple 'X to Y' in current query for IATA codes
    if not (from_id and to_id):
        m_cur = re.search(r"from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+)", raw_query, flags=re.IGNORECASE)
        if m_cur:
            cf = m_cur.group(1).strip().upper()
            ct = m_cur.group(2).strip().upper()
            if re.fullmatch(r"[A-Z]{3}", cf):
                from_id = from_id or (cf + ".AIRPORT")
            if re.fullmatch(r"[A-Z]{3}", ct):
                to_id = to_id or (ct + ".AIRPORT")

    # 2) Fall back to conversation history if still missing
    if not (from_id and to_id):
        explicit_ids = explicit_id_pattern.findall(history_text)
        hist_tokens = re.findall(r"\b[A-Z]{3}\.(?:AIRPORT|CITY)\b", history_text)
        if not from_id and len(hist_tokens) >= 1:
            from_id = hist_tokens[0]
        if not to_id and len(hist_tokens) >= 2:
            to_id = hist_tokens[1]

    # If missing, try to infer from "X to Y" phrasing with IATA codes
    if not (from_id and to_id):
        # Simple from/to pattern in history
        m_from_to = re.search(r"from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+)", history_text, flags=re.IGNORECASE)
        if m_from_to:
            cand_from = m_from_to.group(1).strip()
            cand_to = m_from_to.group(2).strip()
            if re.fullmatch(r"[A-Z]{3}", cand_from.upper()) and not from_id:
                from_id = cand_from.upper() + ".AIRPORT"
            if re.fullmatch(r"[A-Z]{3}", cand_to.upper()) and not to_id:
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

    # Validate and set airport codes
    assumed = []
    
    # If we have IATA codes, ensure they're in the correct format
    if not from_id and 'from' in state:
        from_id = f"{state['from']}.AIRPORT"
    if not to_id and 'to' in state:
        to_id = f"{state['to']}.AIRPORT"
    
    # If still missing, try to extract from the query
    if not from_id or not to_id:
        # Try to extract airport codes from the query using regex
        query = state.get('query', '').lower()
        
        # Look for patterns like "from ABC to XYZ" or "ABC to XYZ"
        match = re.search(r'(?:from\s+)?([a-z]{3})\s+(?:to|2|\-)\s+([a-z]{3})', query)
        if match:
            if not from_id:
                from_id = f"{match.group(1).upper()}.AIRPORT"
            if not to_id:
                to_id = f"{match.group(2).upper()}.AIRPORT"
    
    # If still missing, use the first available code for the missing one
    if from_id and not to_id:
        to_id = f"{state.get('to', 'BOM')}.AIRPORT"
    elif to_id and not from_id:
        from_id = f"{state.get('from', 'BOM')}.AIRPORT"
    elif not from_id and not to_id:
        # If we still don't have both, use the ones from the query or default to BOM-DEL
        from_id = f"{state.get('from', 'BOM')}.AIRPORT"
        to_id = f"{state.get('to', 'DEL')}.AIRPORT"
        assumed.append(f"Using default route: {from_id} to {to_id}")
    
    # Log the final values
    if from_id and to_id:
        logging.info(f"Flight search: {from_id} -> {to_id} on {depart_date}")
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

    # Chain: find hotels at destination city and append compact hotels JSON
    hotels_compact: list[dict[str, Any]] = []
    try:
        # Import here to avoid circulars
        from tools import booking_search_destination, booking_search_hotels

        # Derive a destination query from to_id (strip suffix)
        dest_query = to_id.split(".")[0] if to_id else ""
        # Look up destination
        dest_res = await booking_search_destination.ainvoke({"query": dest_query})
        if dest_res.get("status") == "success":
            dest_payload = dest_res.get("results", {})
            data_field = dest_payload.get("data") if isinstance(dest_payload, dict) else None
            candidates = data_field if isinstance(data_field, list) else None
            if candidates and len(candidates) > 0:
                first = candidates[0]
                dest_id = first.get("dest_id") or first.get("id") or first.get("destination_id")
                search_type = first.get("search_type") or first.get("type") or "CITY"
                if dest_id:
                    # Compute hotel check-in/out from flight date as 2 nights
                    try:
                        ad = datetime.strptime(depart_date, "%Y-%m-%d")
                        arrival_date = ad.strftime("%Y-%m-%d")
                        departure_hotel = (ad + timedelta(days=2)).strftime("%Y-%m-%d")
                    except Exception:
                        arrival_date = depart_date
                        departure_hotel = depart_date

                    hotels_res = await booking_search_hotels.ainvoke({
                        "dest_id": int(dest_id) if str(dest_id).lstrip("-").isdigit() else dest_id,
                        "search_type": search_type,
                        "arrival_date": arrival_date,
                        "departure_date": departure_hotel,
                        "adults": 1,
                        "room_qty": 1,
                        "page_number": 1,
                        "units": "metric",
                        "temperature_unit": "c",
                        "languagecode": "en-us",
                        "currency_code": "USD",
                        "location": "US",
                    })
                    if hotels_res.get("status") == "success":
                        h_payload = hotels_res.get("results", {})
                        root = h_payload.get("data") if isinstance(h_payload, dict) else None
                        hotels_list = None
                        if isinstance(root, list):
                            hotels_list = root
                        elif isinstance(root, dict):
                            hotels_list = root.get("hotels") or root.get("result") or root.get("items") or root.get("list")
                        # Build compact hotels
                        if isinstance(hotels_list, list):
                            for h in hotels_list[:6]:
                                prop = h.get("property", {}) if isinstance(h, dict) else {}
                                name = prop.get("name") or h.get("name") or "Hotel"
                                rating = prop.get("reviewScore") or prop.get("review_score")
                                price_info = prop.get("priceBreakdown", {})
                                gross = price_info.get("grossPrice", {})
                                value = gross.get("value")
                                currency = gross.get("currency") or price_info.get("currency")
                                address = h.get("accessibilityLabel") or prop.get("address") or ""
                                image_url = None
                                photos = prop.get("photos") if isinstance(prop.get("photos"), list) else []
                                if photos:
                                    image_url = photos[0].get("url")
                                hotels_compact.append({
                                    "name": name,
                                    "rating": rating,
                                    "price": {"amount": value, "currency": currency} if value else None,
                                    "location": address,
                                    "imageUrl": image_url,
                                    "amenities": []
                                })
    except Exception:
        pass

    # Append a compact JSON block of top options for the chat UI to parse into cards
    try:
        compact = {
            "items": top_structured[:10],
            "hotels": hotels_compact[:6] if hotels_compact else []
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
    state["active_tool_calls"].append("booking_search_hotels")

    # Import tools lazily to avoid circulars
    from tools import booking_search_destination, booking_search_hotels

    # Extract rough location text from query
    query_text = state.get("user_query", "")
    q_lower = query_text.lower()
    location = None
    # Very simple "in X" heuristic first
    if " in " in q_lower:
        parts = q_lower.split(" in ", 1)
        if len(parts) > 1:
            location = parts[1].strip().split("\n")[0].strip()
    if not location:
        # Fallback: if coordinator details has destination, use that
        details = state.get("coordinator_context", {}).get("extracted_details", {}) or {}
        loc = details.get("destination") or details.get("origin")
        if isinstance(loc, str) and loc.strip():
            location = loc
    if not location:
        # Last resort: use whole query
        location = query_text.strip() or "Mumbai"

    # Interruption context
    interruption_context = {
        "should_interrupt": state.get("should_interrupt", False),
        "partial_results": state.get("partial_results", {}),
    }

    # 1) Resolve destination ID via Booking destination search
    dest_res = await booking_search_destination.ainvoke({"query": location})
    if dest_res.get("status") != "success":
        err = dest_res.get("message", "Destination lookup failed")
        error_text = f"⚠️ Hotel destination search failed: {err}"
        return {
            **state,
            "current_agent": "hotel_agent",
            "messages": state["messages"] + [AIMessage(content=error_text)],
            "status": "complete",
        }

    dest_payload = dest_res.get("results", {})
    data_field = dest_payload.get("data") if isinstance(dest_payload, dict) else None
    candidates = data_field if isinstance(data_field, list) else None
    if not candidates:
        msg = f"⚠️ No hotel destinations found for '{location}'. Try another city."
        return {
            **state,
            "current_agent": "hotel_agent",
            "messages": state["messages"] + [AIMessage(content=msg)],
            "status": "complete",
        }

    first = candidates[0]
    dest_id = first.get("dest_id") or first.get("id") or first.get("destination_id")
    search_type = first.get("search_type") or first.get("type") or "CITY"

    # Basic dates: 2 nights starting ~3 weeks from now
    try:
        base = datetime.utcnow() + timedelta(days=21)
        arrival_date = base.strftime("%Y-%m-%d")
        departure_date = (base + timedelta(days=2)).strftime("%Y-%m-%d")
    except Exception:
        arrival_date = datetime.utcnow().strftime("%Y-%m-%d")
        departure_date = arrival_date

    # 2) Call Booking hotels search
    hotels_res = await booking_search_hotels.ainvoke({
        "dest_id": int(dest_id) if str(dest_id).lstrip("-").isdigit() else dest_id,
        "search_type": search_type,
        "arrival_date": arrival_date,
        "departure_date": departure_date,
        "adults": 1,
        "room_qty": 1,
        "page_number": 1,
        "price_min": 0,
        "price_max": 0,
        "sort_by": "REVIEW_SCORE",
        "units": "metric",
        "temperature_unit": "c",
        "languagecode": "en-us",
        "currency_code": "USD",
        "interruption_check": interruption_context,
    })

    if hotels_res.get("status") == "interrupted":
        state["partial_results"]["hotels"] = hotels_res.get("partial_results", {})
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True,
        }

    if hotels_res.get("status") == "error":
        err_msg = hotels_res.get("message") or "Hotel search error"
        code = hotels_res.get("code")
        detail = f" (code {code})" if code else ""
        error_text = f"⚠️ Hotel search failed{detail}: {err_msg}"
        return {
            **state,
            "current_agent": "hotel_agent",
            "messages": state["messages"] + [AIMessage(content=error_text)],
            "status": "complete",
        }

    # Extract hotel list from Booking.com payload
    def _extract_hotel_list(payload: Any) -> Any:
        root_local = payload.get("data") if isinstance(payload, dict) else None
        hotels_local = None
        if isinstance(root_local, list):
            hotels_local = root_local
        elif isinstance(root_local, dict):
            hotels_local = (
                root_local.get("hotels")
                or root_local.get("result")
                or root_local.get("items")
                or root_local.get("list")
            )

            if hotels_local is None:
                for vv in root_local.values():
                    if isinstance(vv, list) and vv and isinstance(vv[0], dict):
                        hotels_local = vv
                        break

        if hotels_local is None and isinstance(payload, dict):
            for vv in payload.values():
                if isinstance(vv, list) and vv and isinstance(vv[0], dict):
                    hotels_local = vv
                    break
        return hotels_local

    results_payload = hotels_res.get("results")
    hotels_list = _extract_hotel_list(results_payload)

    # If first search came back with no hotels, retry once with relaxed params
    if isinstance(hotels_list, list) and not hotels_list:
        try:
            alt_base = datetime.utcnow() + timedelta(days=7)
            alt_arrival = alt_base.strftime("%Y-%m-%d")
            alt_departure = (alt_base + timedelta(days=2)).strftime("%Y-%m-%d")

            hotels_res_alt = await booking_search_hotels.ainvoke({
                "dest_id": int(dest_id) if str(dest_id).lstrip("-").isdigit() else dest_id,
                "search_type": search_type,
                "arrival_date": alt_arrival,
                "departure_date": alt_departure,
                "adults": 1,
                "room_qty": 1,
                "page_number": 1,
                "price_min": 0,
                "price_max": 0,
                "units": "metric",
                "temperature_unit": "c",
                "languagecode": "en-us",
                "currency_code": "USD",
            })
            if hotels_res_alt.get("status") == "success":
                results_payload = hotels_res_alt.get("results")
                hotels_list = _extract_hotel_list(results_payload)
                # Also adjust summary dates to the ones that actually produced results
                arrival_date = alt_arrival
                departure_date = alt_departure
        except Exception:
            pass

    hotels_compact: list[dict[str, Any]] = []
    if isinstance(hotels_list, list):
        for h in hotels_list[:10]:
            if not isinstance(h, dict):
                continue
            prop = h.get("property", {}) if isinstance(h.get("property"), dict) else h
            name = prop.get("name") or h.get("name") or "Hotel"
            rating = prop.get("reviewScore") or prop.get("review_score")
            price_info = prop.get("priceBreakdown", {}) if isinstance(prop.get("priceBreakdown"), dict) else {}
            gross = price_info.get("grossPrice", {}) if isinstance(price_info.get("grossPrice"), dict) else {}
            value = gross.get("value")
            currency = gross.get("currency") or price_info.get("currency")
            address = (
                h.get("accessibilityLabel")
                or prop.get("address")
                or prop.get("city")
                or ""
            )
            image_url = None
            photos = prop.get("photos") if isinstance(prop.get("photos"), list) else []
            if photos:
                image_url = photos[0].get("url")

            hotels_compact.append(
                {
                    "name": name,
                    "rating": rating,
                    "price": {"amount": value, "currency": currency} if value else None,
                    "location": address,
                    "imageUrl": image_url,
                    "amenities": [],
                }
            )

    count = len(hotels_compact)
    base_line = f"🏨 Searching hotels in {location.title() if isinstance(location, str) else location} for {arrival_date} to {departure_date}."
    if count:
        hotel_summary = base_line + f"\n\nFound {count} options."
    else:
        hotel_summary = base_line + "\n\nNo hotels found from Booking.com payload."

    # Append compact JSON for UI cards (similar shape to flight_agent)
    try:
        compact = {"items": [], "hotels": hotels_compact[:10]}
        hotel_summary = hotel_summary + "\n\n" + json.dumps(compact, ensure_ascii=False)
    except Exception:
        pass

    # Update hotel context
    state["hotel_context"] = {
        "last_search": {
            "location": location,
            "results_count": count,
            "timestamp": time.time(),
        },
        "results": hotels_res,
    }

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

    query_text = state.get("user_query", "")
    q_lower = query_text.lower()

    # If this is clearly an attractions query, answer using Booking.com attractions APIs
    if any(kw in q_lower for kw in ["attraction", "things to do", "places to visit", "sightseeing"]):
        from tools import search_attractions, get_attraction_details

        # Derive location from query or coordinator context
        location: str | None = None
        if " in " in q_lower:
            parts = q_lower.split(" in ", 1)
            if len(parts) > 1:
                location = parts[1].strip().split("\n")[0].strip()
        if not location:
            details = state.get("coordinator_context", {}).get("extracted_details", {}) or {}
            loc = details.get("destination") or details.get("origin")
            if isinstance(loc, str) and loc.strip():
                location = loc
        if not location:
            location = query_text.strip() or "Delhi"

        interruption_ctx = {
            "should_interrupt": state.get("should_interrupt", False),
            "partial_results": state.get("partial_results", {}),
        }

        attr_res = await search_attractions.ainvoke({
            "location": location,
            "interruption_check": interruption_ctx,
        })

        if attr_res.get("status") == "interrupted":
            return {
                **state,
                "status": "interrupted",
                "is_interrupted": True,
            }

        if attr_res.get("status") != "success":
            msg = attr_res.get("message") or "Attraction search error"
            fallback = f"⚠️ Could not fetch live attractions for {location}. {msg}"
            return {
                **state,
                "current_agent": "research_agent",
                "messages": state["messages"] + [AIMessage(content=fallback)],
                "status": "complete",
            }

        # Extract attraction list from search results
        results_payload = attr_res.get("results")
        root = results_payload.get("data") if isinstance(results_payload, dict) else None
        attractions_list = None
        if isinstance(root, list):
            attractions_list = root
        elif isinstance(root, dict):
            attractions_list = (
                root.get("attractions")
                or root.get("items")
                or root.get("results")
            )
            if attractions_list is None:
                for v in root.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        attractions_list = v
                        break

        if not isinstance(attractions_list, list) or not attractions_list:
            text = f"🎡 I couldn't find specific attractions for {location} from Booking.com."
            return {
                **state,
                "current_agent": "research_agent",
                "messages": state["messages"] + [AIMessage(content=text)],
                "status": "complete",
            }

        # For top few attractions, also fetch detailed info
        bullets: list[str] = []
        max_items = 5
        for a in attractions_list[:max_items]:
            if not isinstance(a, dict):
                continue
            # Basic fields from searchAttractions
            info = a.get("property") if isinstance(a.get("property"), dict) else a
            name = info.get("name") or a.get("title") or "Attraction"
            rating = info.get("reviewScore") or info.get("rating")
            reviews = info.get("reviewCount") or info.get("reviews")
            price_info = info.get("priceBreakdown", {}) if isinstance(info.get("priceBreakdown"), dict) else {}
            gross = price_info.get("grossPrice", {}) if isinstance(price_info.get("grossPrice"), dict) else {}
            value = gross.get("value")
            currency = gross.get("currency") or price_info.get("currency")

            # Try to get an ID for details
            attr_id = a.get("id") or info.get("id") or a.get("pinnedProductId")
            desc = ""
            duration = info.get("duration")

            if attr_id:
                try:
                    details_res = await get_attraction_details.ainvoke({
                        "attraction_id": attr_id,
                        "interruption_check": interruption_ctx,
                    })
                    if details_res.get("status") == "success":
                        det_payload = details_res.get("results")
                        det_root = det_payload.get("data") if isinstance(det_payload, dict) else det_payload
                        if isinstance(det_root, dict):
                            desc = det_root.get("description") or det_root.get("shortDescription") or desc
                            duration = det_root.get("duration") or duration
                except Exception:
                    pass

            line = f"• {name}"
            if rating:
                try:
                    line += f" | Rating: {float(rating):.1f}★"
                except Exception:
                    line += f" | Rating: {rating}★"
            if reviews:
                line += f" ({reviews} reviews)"
            if value is not None:
                cur = currency or "INR"
                try:
                    line += f" | From approx. {float(value):.0f} {cur}"
                except Exception:
                    line += f" | From approx. {value} {cur}"
            if duration:
                line += f" | Duration: {duration}"
            if desc:
                line += f"\n  {desc.strip()}"

            bullets.append(line)

        header = f"🎡 Here are some of the best attractions in {location} from Booking.com:\n\n"
        body = "\n\n".join(bullets) if bullets else "No detailed attractions could be listed."
        text = header + body

        return {
            **state,
            "current_agent": "research_agent",
            "messages": state["messages"] + [AIMessage(content=text)],
            "status": "complete",
        }

    # Non-attraction queries: keep existing web_search behavior
    from tools import web_search

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

async def attractions_agent(state: AgentState) -> dict[str, Any]:
    """Attractions Agent: lists popular attractions in a city.

    Uses the search_attractions tool (Booking attractions API with fallback)
    and returns a compact JSON block suitable for card rendering.
    """

    if state.get("should_interrupt", False):
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True,
            "messages": state["messages"] + [
                AIMessage(content="🎡 Attraction search was interrupted.")
            ],
        }

    state["previous_agents"].append("attractions_agent")

    from tools import search_attractions

    # Extract rough location text from query
    query_text = state.get("user_query", "")
    q_lower = query_text.lower()
    location = None
    if " in " in q_lower:
        parts = q_lower.split(" in ", 1)
        if len(parts) > 1:
            location = parts[1].strip().split("\n")[0].strip()
    if not location:
        details = state.get("coordinator_context", {}).get("extracted_details", {}) or {}
        loc = details.get("destination") or details.get("origin")
        if isinstance(loc, str) and loc.strip():
            location = loc
    if not location:
        location = query_text.strip() or "Mumbai"

    interruption_context = {
        "should_interrupt": state.get("should_interrupt", False),
        "partial_results": state.get("partial_results", {}),
    }

    tool_res = await search_attractions.ainvoke({
        "location": location,
        "interruption_check": interruption_context,
    })

    if tool_res.get("status") == "interrupted":
        return {
            **state,
            "status": "interrupted",
            "is_interrupted": True,
        }

    if tool_res.get("status") == "error":
        msg = tool_res.get("message") or "Attraction search error"
        return {
            **state,
            "current_agent": "attractions_agent",
            "messages": state["messages"] + [AIMessage(content=f"⚠️ Attraction search failed: {msg}")],
            "status": "complete",
        }

    results_payload = tool_res.get("results")
    root = results_payload.get("data") if isinstance(results_payload, dict) else None
    attractions_list = None
    if isinstance(root, list):
        attractions_list = root
    elif isinstance(root, dict):
        attractions_list = (
            root.get("attractions")
            or root.get("items")
            or root.get("results")
        )
        if attractions_list is None:
            for v in root.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    attractions_list = v
                    break

    compact: list[dict[str, Any]] = []
    if isinstance(attractions_list, list):
        for a in attractions_list[:10]:
            if not isinstance(a, dict):
                continue
            info = a.get("property") if isinstance(a.get("property"), dict) else a
            name = info.get("name") or a.get("title") or "Attraction"
            rating = info.get("reviewScore") or info.get("rating")
            reviews = info.get("reviewCount") or info.get("reviews")
            price_info = info.get("priceBreakdown", {}) if isinstance(info.get("priceBreakdown"), dict) else {}
            gross = price_info.get("grossPrice", {}) if isinstance(price_info.get("grossPrice"), dict) else {}
            value = gross.get("value")
            currency = gross.get("currency") or price_info.get("currency")
            image_url = None
            photos = info.get("photoUrls") if isinstance(info.get("photoUrls"), list) else []
            if photos:
                image_url = photos[0]

            compact.append(
                {
                    "name": name,
                    "rating": rating,
                    "reviews": reviews,
                    "price": {"amount": value, "currency": currency} if value else None,
                    "location": location,
                    "imageUrl": image_url,
                }
            )

    count = len(compact)
    base_line = f"🎡 Searching attractions in {location}."
    if count:
        summary = base_line + f"\n\nFound {count} options."
    else:
        summary = base_line + "\n\nNo attractions found from Booking.com payload; showing any available data."

    try:
        payload = {"items": [], "attractions": compact[:10]}
        summary = summary + "\n\n" + json.dumps(payload, ensure_ascii=False)
    except Exception:
        pass

    return {
        **state,
        "current_agent": "attractions_agent",
        "messages": state["messages"] + [AIMessage(content=summary)],
        "status": "complete",
    }
