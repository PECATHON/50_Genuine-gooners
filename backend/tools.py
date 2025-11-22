"""
Tools for agent use - flight search, hotel search, and web search.
Each tool supports interruption checking for graceful cancellation.
"""

import os
import time
import json
import httpx
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import tool
from typing import Optional, Any, Dict, Tuple

# Load env so RAPIDAPI_KEY is available
load_dotenv()
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env.local", override=False)

# --- Lightweight in-memory cache (process-local) ---
_CACHE: dict[Tuple[str, str], Tuple[float, Any]] = {}
_TTL_SEC = 15 * 60  # 15 minutes

def _cache_get(key: Tuple[str, str]):
    now = time.time()
    item = _CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if now - ts > _TTL_SEC:
        _CACHE.pop(key, None)
        return None
    return val

def _cache_set(key: Tuple[str, str], value: Any):
    _CACHE[key] = (time.time(), value)

def _keys_from_env() -> list[str]:
    # Allow multiple keys separated by commas
    raw = os.getenv("RAPIDAPI_KEY", "").strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]

async def _rapidapi_get(url: str, params: dict) -> dict[str, Any]:
    keys = _keys_from_env()
    if not keys:
        return {"status": "error", "message": "RAPIDAPI_KEY not set in environment"}

    async with httpx.AsyncClient(timeout=30) as client:
        last_error: dict[str, Any] | None = None
        for key in keys:
            headers = {
                "x-rapidapi-host": "booking-com15.p.rapidapi.com",
                "x-rapidapi-key": key,
            }
            resp = await client.get(url, params=params, headers=headers)
            ct = resp.headers.get("content-type", "")
            data = resp.json() if ct.startswith("application/json") else {"raw": resp.text}
            if resp.status_code == 200:
                return {"status": "success", "data": data}
            # If 429 or auth/quota issue, try next key
            if resp.status_code in (401, 403, 429):
                last_error = {
                    "status": "error",
                    "code": resp.status_code,
                    "message": (data.get("message") if isinstance(data, dict) else "HTTP error"),
                    "response": data,
                }
                continue
            # Other errors: return immediately
            return {
                "status": "error",
                "code": resp.status_code,
                "message": (data.get("message") if isinstance(data, dict) else "HTTP error"),
                "response": data,
            }
        return last_error or {"status": "error", "message": "All RapidAPI keys failed"}

@tool
async def search_flights(
    origin: str,
    destination: str,
    date: Optional[str] = None,
    passengers: int = 1,
    returnDate: Optional[str] = None,
    stops: str = "none",
    pageNo: int = 1,
    children: Optional[str] = None,
    sort: str = "BEST",
    cabinClass: str = "ECONOMY",
    currency_code: str = "USD",
    interruption_check: Optional[dict] = None
) -> dict[str, Any]:
    """
    Search for flights via RapidAPI Booking.com flights endpoint.

    Note: 'origin' and 'destination' are treated as fromId/toId (e.g., 'BOM.AIRPORT').
    'date' maps to 'departDate'.
    """
    if interruption_check and interruption_check.get("should_interrupt"):
        return {"status": "interrupted", "message": "Flight search was cancelled"}

    # Cache key by main parameters
    cache_key = ("flights", f"{origin}|{destination}|{date}|{passengers}|{stops}|{pageNo}|{sort}|{cabinClass}|{currency_code}")
    cached = _cache_get(cache_key)
    if cached:
        return cached

    if not origin or not destination:
        return {"status": "error", "message": "origin (fromId) and destination (toId) are required"}
    if not date:
        return {"status": "error", "message": "date (departDate) is required in format YYYY-MM-DD"}

    base_url = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchFlights"
    params = {
        "fromId": origin,
        "toId": destination,
        "departDate": date,
        "stops": stops,
        "pageNo": pageNo,
        "adults": passengers,
        "sort": sort,
        "cabinClass": cabinClass,
        "currency_code": currency_code,
    }
    if returnDate:
        params["returnDate"] = returnDate
    if children:
        params["children"] = children

    try:
        res = await _rapidapi_get(base_url, params)
        if res.get("status") != "success":
            return res
        out = {"status": "success", "query": params, "results": res.get("data")}
        _cache_set(cache_key, out)
        return out
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Network error: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {e}"}

@tool
async def booking_search_destination(query: str) -> dict[str, Any]:
    """Search destination IDs for hotels via RapidAPI (hotels/searchDestination)."""
    base_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchDestination"
    params = {"query": query}

    try:
        cache_key = ("dest", query)
        cached = _cache_get(cache_key)
        if cached:
            return cached
        res = await _rapidapi_get(base_url, params)
        if res.get("status") != "success":
            return res
        out = {"status": "success", "results": res.get("data")}
        _cache_set(cache_key, out)
        return out
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Network error: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {e}"}

@tool
async def booking_search_hotels(
    dest_id: int,
    search_type: str,
    arrival_date: str,
    departure_date: str,
    adults: int = 1,
    children_age: Optional[str] = None,
    room_qty: int = 1,
    page_number: int = 1,
    price_min: int = 0,
    price_max: int = 0,
    sort_by: Optional[str] = None,
    categories_filter: Optional[str] = None,
    units: str = "metric",
    temperature_unit: str = "c",
    languagecode: str = "en-us",
    currency_code: str = "USD",
    location: Optional[str] = None,
    interruption_check: Optional[dict] = None
) -> Dict[str, Any]:
    """Search hotels via Booking.com RapidAPI (hotels/searchHotels)."""

    # Interruption check
    if interruption_check and interruption_check.get("should_interrupt"):
        return {"status": "interrupted", "message": "Hotel search cancelled"}

    base_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotels"
    params: Dict[str, Any] = {
        "dest_id": dest_id,
        "search_type": search_type,
        "arrival_date": arrival_date,
        "departure_date": departure_date,
        "adults": adults,
        "room_qty": room_qty,
        "page_number": page_number,
        "price_min": price_min,
        "price_max": price_max,
        "units": units,
        "temperature_unit": temperature_unit,
        "languagecode": languagecode,
        "currency_code": currency_code,
    }
    if children_age:
        params["children_age"] = children_age
    if sort_by:
        params["sort_by"] = sort_by
    if categories_filter:
        params["categories_filter"] = categories_filter
    if location:
        params["location"] = location

    try:
        cache_key = ("hotels", json.dumps(params, sort_keys=True))
        cached = _cache_get(cache_key)
        if cached:
            return cached

        res = await _rapidapi_get(base_url, params)
        if res.get("status") != "success":
            return res
        out: Dict[str, Any] = {
            "status": "success",
            "query": params,
            "results": res.get("data"),
        }
        _cache_set(cache_key, out)
        return out
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Network error: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {e}"}

@tool
async def booking_search_destination(query: str) -> dict[str, Any]:
    """Search destination IDs for hotels via RapidAPI (hotels/searchDestination)."""
    base_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchDestination"
    params = {"query": query}

    try:
        cache_key = ("dest", query)
        cached = _cache_get(cache_key)
        if cached:
            return cached
        res = await _rapidapi_get(base_url, params)
        if res.get("status") != "success":
            return res
        out = {"status": "success", "results": res.get("data")}
        _cache_set(cache_key, out)
        return out
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Network error: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {e}"}


@tool
async def search_hotels(
    location: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: int = 1,
    interruption_check: Optional[dict] = None
) -> dict[str, Any]:
    """
    Search for hotels in a given location.
    
    Args:
        location: City or area to search
        check_in: Check-in date (optional)
        check_out: Check-out date (optional)
        guests: Number of guests
        interruption_check: Dict with 'should_interrupt' flag for cancellation
    
    Returns:
        Hotel search results or interruption status
    """
    # Check for interruption
    if interruption_check and interruption_check.get("should_interrupt"):
        return {
            "status": "interrupted",
            "message": "Hotel search was cancelled",
            "partial_results": interruption_check.get("partial_results", {})
        }
    
    # Simulate API call
    await asyncio.sleep(0.5)
    
    # Check interruption mid-operation
    if interruption_check and interruption_check.get("should_interrupt"):
        return {
            "status": "interrupted",
            "message": "Hotel search was cancelled during operation",
            "partial_results": {"progress": "60%"}
        }
    
    # Mock hotel data
    hotels = [
        {
            "id": "H001",
            "name": "Grand Plaza Hotel",
            "location": location,
            "rating": 4.5,
            "reviews_count": 1243,
            "price_per_night": 189,
            "currency": "USD",
            "amenities": ["Pool", "Gym", "Free WiFi", "Breakfast Included", "Parking"],
            "room_type": "Deluxe King",
            "image_url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80",
            "distance_from_center": "0.5 miles"
        },
        {
            "id": "H002",
            "name": "Coastal View Resort",
            "location": location,
            "rating": 4.7,
            "reviews_count": 892,
            "price_per_night": 249,
            "currency": "USD",
            "amenities": ["Beach Access", "Spa", "Restaurant", "Bar", "Concierge"],
            "room_type": "Ocean View Suite",
            "image_url": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=800&q=80",
            "distance_from_center": "2.1 miles"
        },
        {
            "id": "H003",
            "name": "Downtown Business Inn",
            "location": location,
            "rating": 4.2,
            "reviews_count": 567,
            "price_per_night": 129,
            "currency": "USD",
            "amenities": ["Free WiFi", "Business Center", "Airport Shuttle", "Coffee"],
            "room_type": "Standard Queen",
            "image_url": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800&q=80",
            "distance_from_center": "0.2 miles"
        }
    ]
    
    return {
        "status": "success",
        "query": {
            "location": location,
            "check_in": check_in or "flexible",
            "check_out": check_out or "flexible",
            "guests": guests
        },
        "hotels": hotels,
        "count": len(hotels),
        "search_timestamp": time.time()
    }


@tool
async def web_search(
    query: str,
    max_results: int = 3,
    interruption_check: Optional[dict] = None
) -> dict[str, Any]:
    """
    Perform web search for general travel information.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        interruption_check: Dict with 'should_interrupt' flag for cancellation
    
    Returns:
        Web search results or interruption status
    """
    # Check for interruption
    if interruption_check and interruption_check.get("should_interrupt"):
        return {
            "status": "interrupted",
            "message": "Web search was cancelled"
        }
    
    # Simulate search
    await asyncio.sleep(0.3)
    
    # Mock search results
    results = [
        {
            "title": f"Travel Guide: {query}",
            "url": "https://example.com/travel-guide",
            "snippet": "Comprehensive travel information and tips for your destination...",
            "source": "TravelGuide.com"
        },
        {
            "title": f"Best Time to Visit - {query}",
            "url": "https://example.com/best-time",
            "snippet": "Find out the best season and weather conditions for your trip...",
            "source": "WeatherTravel.com"
        }
    ]
    
    return {
        "status": "success",
        "query": query,
        "results": results[:max_results],
        "count": len(results),
        "search_timestamp": time.time()
    }


@tool
async def search_attractions(
    location: str,
    interruption_check: Optional[dict] = None
) -> dict[str, Any]:
    """Search attractions for a city using Booking.com attractions API.

    Tries the real Booking attractions endpoints and falls back to sample data
    if the API call fails or returns no attractions, so the UI can always
    render cards for demos.
    """

    if interruption_check and interruption_check.get("should_interrupt"):
        return {
            "status": "interrupted",
            "message": "Attraction search was cancelled",
            "partial_results": interruption_check.get("partial_results", {}),
        }

    # Helper to build a few mock attractions (for fallback/demo)
    def _mock_attractions(city: str) -> dict[str, Any]:
        demo = [
            {
                "name": f"City Highlights Tour - {city}",
                "rating": 4.7,
                "reviews": 1200,
                "price": {"amount": 35, "currency": "USD"},
                "duration": "4h",
                "location": city,
                "imageUrl": None,
            },
            {
                "name": f"Old Town Walking Tour - {city}",
                "rating": 4.5,
                "reviews": 840,
                "price": {"amount": 20, "currency": "USD"},
                "duration": "3h",
                "location": city,
                "imageUrl": None,
            },
        ]
        return {
            "status": "success",
            "query": {"location": city},
            "results": {"data": {"attractions": demo}},
        }

    # First, try to resolve an attraction location ID via searchLocation
    base_loc = "https://booking-com15.p.rapidapi.com/api/v1/attraction/searchLocation"
    try:
        loc_res = await _rapidapi_get(base_loc, {"query": location})
        if loc_res.get("status") != "success":
            return _mock_attractions(location)
        loc_data = loc_res.get("data") or {}
        root = loc_data.get("data") if isinstance(loc_data, dict) else None

        # According to docs, id can be inside products or destinations
        candidates = None
        if isinstance(root, dict):
            candidates = root.get("products") or root.get("destinations")
        if candidates is None and isinstance(root, list):
            candidates = root
        if not isinstance(candidates, list) or not candidates:
            return _mock_attractions(location)

        first = candidates[0]
        loc_id = first.get("id") or first.get("ufi") or first.get("dest_id")
        if not loc_id:
            return _mock_attractions(location)

        # Now search attractions for that id
        base_attr = "https://booking-com15.p.rapidapi.com/api/v1/attraction/searchAttractions"
        params: Dict[str, Any] = {
            "id": loc_id,
            "sortBy": "trending",
            "page": 1,
            "currency_code": "INR",
            "languagecode": "en-us",
        }
        attr_res = await _rapidapi_get(base_attr, params)
        if attr_res.get("status") != "success":
            return _mock_attractions(location)

        out = {
            "status": "success",
            "query": params,
            "results": attr_res.get("data"),
        }
        return out
    except httpx.RequestError:
        return _mock_attractions(location)
    except Exception:
        return _mock_attractions(location)


@tool
async def get_attraction_details(
    attraction_id: str,
    interruption_check: Optional[dict] = None
) -> dict[str, Any]:
    """Get detailed information for a specific attraction.

    Wraps Booking.com `api/v1/attraction/getAttractionDetails`.
    """

    if interruption_check and interruption_check.get("should_interrupt"):
        return {
            "status": "interrupted",
            "message": "Attraction details fetch was cancelled",
            "partial_results": interruption_check.get("partial_results", {}),
        }

    base_url = "https://booking-com15.p.rapidapi.com/api/v1/attraction/getAttractionDetails"
    params = {
        "id": attraction_id,
        "currency_code": "INR",
        "languagecode": "en-us",
    }
    try:
        res = await _rapidapi_get(base_url, params)
        if res.get("status") != "success":
            return res
        return {
            "status": "success",
            "query": params,
            "results": res.get("data"),
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Network error: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {e}"}


# Export all tools as a list
ALL_TOOLS = [
    search_flights,
    search_hotels,
    booking_search_hotels,
    booking_search_destination,
    web_search,
    search_attractions,
    get_attraction_details,
]
