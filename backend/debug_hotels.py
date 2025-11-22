import asyncio
import json

from tools import booking_search_destination, booking_search_hotels


async def main():
    # 1) Resolve Delhi destination
    dest = await booking_search_destination.ainvoke({"query": "Delhi"})
    print("DEST_STATUS:", dest.get("status"))
    print("DEST_KEYS:", list(dest.keys()))
    print("DEST_SAMPLE:", json.dumps(dest, default=str)[:800])

    if dest.get("status") != "success":
        return

    results = dest.get("results", {})
    data = results.get("data") if isinstance(results, dict) else None
    if not isinstance(data, list) or not data:
        print("NO_DEST_LIST in data")
        return

    first = data[0]
    dest_id = first.get("dest_id") or first.get("id") or first.get("destination_id")
    search_type = first.get("search_type") or first.get("type") or "CITY"
    print("USING dest_id=", dest_id, "search_type=", search_type)

    # 2) Call hotels search for a fixed date range
    hotels = await booking_search_hotels.ainvoke({
        "dest_id": dest_id,
        "search_type": search_type,
        "arrival_date": "2025-12-13",
        "departure_date": "2025-12-15",
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
    })

    print("HOTELS_STATUS:", hotels.get("status"))
    print("HOTELS_KEYS:", list(hotels.keys()))

    res = hotels.get("results")
    print("RESULTS_TYPE:", type(res))
    if isinstance(res, dict):
        print("RESULTS_KEYS:", list(res.keys()))
    print("RESULTS_SNIPPET:", json.dumps(res, default=str)[:1600])


if __name__ == "__main__":
    asyncio.run(main())
