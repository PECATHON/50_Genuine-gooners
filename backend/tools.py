"""
Tools for agent use - flight search, hotel search, and web search.
Each tool supports interruption checking for graceful cancellation.
"""

from langchain_core.tools import tool
from typing import Optional, Any
import asyncio
import time


@tool
async def search_flights(
    origin: str,
    destination: str,
    date: Optional[str] = None,
    passengers: int = 1,
    interruption_check: Optional[dict] = None
) -> dict[str, Any]:
    """
    Search for flights between origin and destination.
    
    Args:
        origin: Departure city/airport code
        destination: Arrival city/airport code
        date: Travel date (optional)
        passengers: Number of passengers
        interruption_check: Dict with 'should_interrupt' flag for cancellation
    
    Returns:
        Flight search results or interruption status
    """
    # Check for interruption before starting search
    if interruption_check and interruption_check.get("should_interrupt"):
        return {
            "status": "interrupted",
            "message": "Flight search was cancelled",
            "partial_results": interruption_check.get("partial_results", {})
        }
    
    # Simulate API call with periodic interruption checks
    await asyncio.sleep(0.5)  # Simulate network delay
    
    # Check interruption mid-operation
    if interruption_check and interruption_check.get("should_interrupt"):
        return {
            "status": "interrupted",
            "message": "Flight search was cancelled during operation",
            "partial_results": {"progress": "50%"}
        }
    
    # Mock flight data (replace with real API calls)
    flights = [
        {
            "id": "FL001",
            "airline": "United Airlines",
            "flight_number": "UA1234",
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_time": "08:00 AM",
            "arrival_time": "11:30 AM",
            "duration": "5h 30m",
            "price": 450,
            "currency": "USD",
            "stops": 0,
            "aircraft": "Boeing 737",
            "available_seats": 45
        },
        {
            "id": "FL002",
            "airline": "Delta Airlines",
            "flight_number": "DL5678",
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_time": "02:15 PM",
            "arrival_time": "05:45 PM",
            "duration": "5h 30m",
            "price": 380,
            "currency": "USD",
            "stops": 0,
            "aircraft": "Airbus A320",
            "available_seats": 32
        },
        {
            "id": "FL003",
            "airline": "American Airlines",
            "flight_number": "AA9012",
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_time": "06:45 PM",
            "arrival_time": "10:15 PM",
            "duration": "5h 30m",
            "price": 520,
            "currency": "USD",
            "stops": 1,
            "aircraft": "Boeing 787",
            "available_seats": 18
        }
    ]
    
    return {
        "status": "success",
        "query": {
            "origin": origin,
            "destination": destination,
            "date": date or "flexible",
            "passengers": passengers
        },
        "flights": flights,
        "count": len(flights),
        "search_timestamp": time.time()
    }


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
ALL_TOOLS = [search_flights, search_hotels, web_search]
