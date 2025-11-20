import { NextRequest, NextResponse } from "next/server";

// Simulated multi-agent system
export async function POST(request: NextRequest) {
  try {
    const { message, conversationHistory } = await request.json();

    // Coordinator agent analyzes the request
    const query = message.toLowerCase();
    const needsFlight = query.includes("flight") || query.includes("fly");
    const needsHotel = query.includes("hotel") || query.includes("stay");

    const response: any = {
      coordinatorResponse: "I'll help you with your travel plans!",
      agents: [],
    };

    // Activate Flight Agent if needed
    if (needsFlight) {
      response.agents.push({
        type: "flight",
        status: "searching",
        results: [
          {
            from: "NYC",
            to: "LAX",
            departure: "08:00 AM",
            arrival: "11:30 AM",
            duration: "5h 30m",
            price: "$299",
            airline: "Delta Airlines",
          },
          {
            from: "NYC",
            to: "LAX",
            departure: "02:15 PM",
            arrival: "05:45 PM",
            duration: "5h 30m",
            price: "$349",
            airline: "United Airlines",
          },
        ],
      });
    }

    // Activate Hotel Agent if needed
    if (needsHotel) {
      response.agents.push({
        type: "hotel",
        status: "searching",
        results: [
          {
            name: "The Grand Plaza",
            location: "Downtown Los Angeles",
            rating: 4.5,
            price: "$189",
            amenities: ["Pool", "Gym", "Free WiFi", "Breakfast"],
            imageUrl: "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80",
          },
          {
            name: "Coastal View Hotel",
            location: "Santa Monica",
            rating: 4.7,
            price: "$249",
            amenities: ["Beach Access", "Spa", "Restaurant", "Parking"],
            imageUrl: "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=800&q=80",
          },
        ],
      });
    }

    return NextResponse.json(response);
  } catch (error) {
    console.error("Chat API error:", error);
    return NextResponse.json(
      { error: "Failed to process request" },
      { status: 500 }
    );
  }
}
