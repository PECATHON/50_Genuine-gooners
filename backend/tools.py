"""
Tools for agent use - flight search, hotel search, and web search.
Each tool supports interruption checking for graceful cancellation.
"""

from langchain_core.tools import tool
from typing import Optional, Any, Dict
import asyncio
import time
import os
import httpx


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

    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return {"status": "error", "message": "RAPIDAPI_KEY not set in environment"}

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

    headers = {
        "x-rapidapi-host": "booking-com15.p.rapidapi.com",
        "x-rapidapi-key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
            if resp.status_code >= 400:
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "message": data.get("message") if isinstance(data, dict) else "HTTP error",
                    "response": data,
                }
            return {
                "status": "success",
                "query": params,
                "results": data,
            }
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
    """
    Search hotels via Booking.com RapidAPI.

    Requires environment variable RAPIDAPI_KEY to be set.
    """
    # Interruption check
    if interruption_check and interruption_check.get("should_interrupt"):
        return {"status": "interrupted", "message": "Hotel search cancelled"}

    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return {"status": "error", "message": "RAPIDAPI_KEY not set in environment"}

    base_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotels"
    params = {
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

    headers = {
        "x-rapidapi-host": "booking-com15.p.rapidapi.com",
        "x-rapidapi-key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
            if resp.status_code >= 400:
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "message": data.get("message") if isinstance(data, dict) else "HTTP error",
                    "response": data,
                }
            return {
                "status": "success",
                "query": params,
                "results": data,
            }
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


# Export all tools as a list
ALL_TOOLS = [search_flights, search_hotels, booking_search_hotels, web_search]
