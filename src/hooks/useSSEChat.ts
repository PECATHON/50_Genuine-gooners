/**
 * Custom hook for Server-Sent Events (SSE) chat integration with Python backend.
 * Handles real-time streaming, interruption, and state management.
 */

import { useState, useCallback, useRef } from "react";

export interface ChatMessage {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
  agentType?: "coordinator" | "flight" | "hotel" | "research";
  flightResults?: any[];
  hotelResults?: any[];
  isPartial?: boolean;
}

export interface AgentState {
  type: "coordinator" | "flight" | "hotel" | "research";
  status: "idle" | "active" | "complete";
  message?: string;
}

interface SSEEvent {
  type: string;
  [key: string]: any;
}

const PYTHON_BACKEND_URL = process.env.NEXT_PUBLIC_PYTHON_BACKEND_URL || "http://localhost:8000";

export function useSSEChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [agents, setAgents] = useState<AgentState[]>([
    { type: "coordinator", status: "idle" },
    { type: "flight", status: "idle" },
    { type: "hotel", status: "idle" },
    { type: "research", status: "idle" },
  ]);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const currentQueryIdRef = useRef<string | null>(null);
  const currentThreadIdRef = useRef<string | null>(null);
  const currentMessageBufferRef = useRef<string>("");
  const currentAgentRef = useRef<string>("");

  const updateAgentStatus = useCallback((
    type: AgentState["type"],
    status: AgentState["status"],
    message?: string
  ) => {
    setAgents((prev) =>
      prev.map((agent) =>
        agent.type === type ? { ...agent, status, message } : agent
      )
    );
  }, []);

  const resetAgents = useCallback(() => {
    setAgents([
      { type: "coordinator", status: "idle" },
      { type: "flight", status: "idle" },
      { type: "hotel", status: "idle" },
      { type: "research", status: "idle" },
    ]);
  }, []);

  const parseFlightResults = (content: string): any[] | null => {
    // 1) Try to extract JSON payload printed by Flight Agent (snippet or full)
    try {
      // Prefer a block that explicitly starts with {"items": ...}
      let raw: string | null = null;
      const idx = content.lastIndexOf('{"items"');
      if (idx !== -1) {
        let block = content.slice(idx).trim();
        // Trim to the last closing brace
        const lastBrace = block.lastIndexOf('}');
        if (lastBrace !== -1) block = block.slice(0, lastBrace + 1);
        raw = block;
      }
      // Fallback to regex search if direct slice not found
      if (!raw) {
        const allMatches = [...content.matchAll(/\{[\s\S]*\}/g)];
        for (let i = allMatches.length - 1; i >= 0; i--) {
          const txt = allMatches[i][0];
          if (txt.includes('"items"')) { raw = txt; break; }
        }
        if (!raw && allMatches.length) raw = allMatches[allMatches.length - 1][0];
      }
      if (raw) {
        const payload = JSON.parse(raw);
        const root = payload?.results ?? payload; // tool returns {status, query, results}
        const data = root?.data ?? root;
        const candidateLists: any[] = [];

        const addListsFrom = (obj: any) => {
          if (!obj || typeof obj !== "object") return;
          ["results", "itineraries", "itineraryList", "flights", "items"].forEach((k) => {
            const v = obj[k];
            if (Array.isArray(v) && v.length) candidateLists.push(v);
          });
        };

        addListsFrom(data);
        if (Array.isArray(data)) candidateLists.push(data);
        if (data && typeof data === "object") {
          Object.values(data).forEach((v) => {
            if (Array.isArray(v) && v.length) candidateLists.push(v);
          });
        }

        let list = candidateLists[0] || [];
        const stripSuffix = (s?: string) => {
          if (!s || typeof s !== "string") return s || "";
          return s.replace(/\.(AIRPORT|CITY)$/i, "");
        };
        const toCard = (obj: any) => {
          // map to Chat FlightCard props: { from, to, departure, arrival, duration, price, airline }
          let airline: string | undefined;
          let price: string | undefined;
          let departure: string | undefined;
          let arrival: string | undefined;
          let duration: string | undefined;
          let from: string | undefined;
          let to: string | undefined;

          if (obj && typeof obj === "object") {
            // price (support compact item shape from backend)
            const p = obj.price ?? obj.pricing;
            if (typeof p === "number") price = `$${Math.round(p)}`;
            else if (typeof p === "string") price = p;
            else if (p && typeof p === "object") {
              const amount = p.amount ?? p.total ?? p.units;
              const nanos = p.nanos ?? 0;
              let val: number | undefined = undefined;
              if (typeof amount === "number") val = amount;
              if (typeof amount === "string") val = parseFloat(amount);
              if (typeof val === "number") {
                const total = val + (typeof nanos === "number" ? nanos / 1e9 : 0);
                const cur = obj.currency || p.currency || p.currencyCode || "";
                price = `${Math.round(total)}${cur ? ` ${cur}` : ""}`;
              }
            }

            // segments/legs
            const segments = obj.segments || obj.legs || obj.itinerarySegments || [];
            if (Array.isArray(segments) && segments.length) {
              const first = segments[0] || {};
              const last = segments[segments.length - 1] || {};
              airline = first.carrier || first.airline || first.marketingCarrier || airline || obj.airline;
              departure = first.departureTime || first.departure || first.departureDateTime || obj.departTime || departure;
              arrival = last.arrivalTime || last.arrival || last.arrivalDateTime || obj.arriveTime || arrival;
              from = stripSuffix(first.origin || first.departureAirport || first.originCode || from);
              to = stripSuffix(last.destination || last.arrivalAirport || last.destinationCode || to);
            }

            // top-level fallbacks
            airline = airline || obj.airline;
            duration = obj.duration || obj.totalDuration || duration;
            departure = departure || obj.departTime;
            arrival = arrival || obj.arriveTime;
            // origin/destination fallbacks coming from backend compact items
            from = from || obj.from;
            to = to || obj.to;
          }

          // If no exact times, show codes so cards aren't empty
          const depOut = departure || stripSuffix(from) || "";
          const arrOut = arrival || stripSuffix(to) || "";

          return {
            from: stripSuffix(from) || "",
            to: stripSuffix(to) || "",
            departure: depOut,
            arrival: arrOut,
            duration: duration || "",
            price: price || "",
            airline: airline || "",
          };
        };

        let cards = list.slice(0, 10).map(toCard).filter((c: any) => Object.values(c).some(Boolean));
        if (cards.length) return cards;

        // Fallback: synthesize from aggregation.airlines
        const rootObj = data?.data && typeof data.data === "object" ? data.data : data;
        const airlines = rootObj?.aggregation?.airlines;
        if (Array.isArray(airlines) && airlines.length) {
          cards = airlines.slice(0, 10).map((al: any) => {
            const mp = al?.minPricePerAdult || al?.minPrice || {};
            const amount = mp?.units ?? mp?.amount;
            const currency = mp?.currencyCode || mp?.currency || "";
            const price = typeof amount === "number" ? `${Math.round(amount)}${currency ? ` ${currency}` : ""}` : "";
            return {
              from: "",
              to: "",
              departure: "",
              arrival: "",
              duration: "",
              price,
              airline: al?.name || al?.iataCode || "",
            };
          }).filter((c: any) => Object.values(c).some(Boolean));
          if (cards.length) return cards;
        }
      }
    } catch {
      // fall through
    }

    // 2) Legacy text parsing fallback
    try {
      const flightPattern = /(\d+)\.\s*([^-]+?)\s*-\s*\$(\d+)\s*\n\s*(\d{1,2}:\d{2}\s*[AP]M)\s*→\s*(\d{1,2}:\d{2}\s*[AP]M)\s*\(([^)]+)\)/g;
      const matches = [...content.matchAll(flightPattern)];
      if (matches.length === 0) return null;
      return matches.map((match) => ({
        airline: match[2].trim(),
        price: `$${match[3]}`,
        departure: match[4],
        arrival: match[5],
        duration: match[6],
        from: "",
        to: "",
      }));
    } catch {
      return null;
    }
  };

  const parseHotelResults = (content: string): any[] | null => {
    // Preferred: JSON with {"hotels": [...]}
    try {
      let raw: string | null = null;
      const idx = content.lastIndexOf('{"hotels"');
      if (idx !== -1) {
        let block = content.slice(idx).trim();
        const lastBrace = block.lastIndexOf('}');
        if (lastBrace !== -1) block = block.slice(0, lastBrace + 1);
        raw = block;
      }
      if (!raw) {
        const allMatches = [...content.matchAll(/\{[\s\S]*\}/g)];
        for (let i = allMatches.length - 1; i >= 0; i--) {
          const txt = allMatches[i][0];
          if (txt.includes('"hotels"')) { raw = txt; break; }
        }
      }
      if (raw) {
        const payload = JSON.parse(raw);
        const hotels = payload?.hotels;
        if (Array.isArray(hotels) && hotels.length) {
          return hotels.slice(0, 6).map((h: any) => {
            const amount = h?.price?.amount;
            const currency = h?.price?.currency || "";
            const price = typeof amount === "number" ? `${Math.round(amount)}${currency ? ` ${currency}` : ""}` : "";
            return {
              name: h?.name || "Hotel",
              location: h?.location || "",
              rating: typeof h?.rating === "number" ? h.rating : 0,
              price,
              amenities: Array.isArray(h?.amenities) ? h.amenities : [],
              imageUrl: h?.imageUrl,
            };
          });
        }
      }
    } catch {
      // fall through
    }

    // Fallback: legacy regex
    try {
      const hotelPattern = /(\d+)\.\s*([^-]+?)\s*-\s*\$(\d+)\/night\s*\n\s*Rating:\s*([\d.]+)⭐\s*\((\d+)\s*reviews\)/g;
      const matches = [...content.matchAll(hotelPattern)];
      if (matches.length === 0) return null;
      return matches.map(match => ({
        name: match[2].trim(),
        price: `$${match[3]}`,
        rating: parseFloat(match[4]),
        reviews_count: parseInt(match[5]),
        location: "",
        amenities: [],
      }));
    } catch {
      return null;
    }
  };

  const cancelCurrentQuery = useCallback(async () => {
    if (!currentQueryIdRef.current) return;

    try {
      await fetch(`${PYTHON_BACKEND_URL}/api/chat/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query_id: currentQueryIdRef.current,
          reason: "User requested cancellation",
        }),
      });

      // Close SSE connection
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      // Add interruption message
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          text: "⏸️ Query interrupted. Your partial results have been saved.",
          isUser: false,
          timestamp: new Date(),
          agentType: "coordinator",
          isPartial: true,
        },
      ]);

      setIsLoading(false);
      resetAgents();
    } catch (error) {
      console.error("Error cancelling query:", error);
    }
  }, [resetAgents]);

  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return;

    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: query,
      isUser: true,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    currentMessageBufferRef.current = "";
    currentAgentRef.current = "";

    try {
      // Use existing thread ID or create new one
      const threadId = currentThreadIdRef.current || `thread-${Date.now()}`;
      currentThreadIdRef.current = threadId;

      const response = await fetch(`${PYTHON_BACKEND_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, thread_id: threadId }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Get query ID from headers
      const queryId = response.headers.get("X-Query-ID");
      currentQueryIdRef.current = queryId;

      // Create EventSource from response body
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error("No response body");

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim() || !line.startsWith("data: ")) continue;

          try {
            const event: SSEEvent = JSON.parse(line.slice(6));
            
            switch (event.type) {
              case "start":
                console.log("Stream started:", event.query_id);
                break;

              case "agent_start":
                const agentType = event.agent.includes("coordinator") ? "coordinator" :
                                 event.agent.includes("flight") ? "flight" :
                                 event.agent.includes("hotel") ? "hotel" : "research";
                updateAgentStatus(agentType, "active", `${agentType} analyzing...`);
                currentAgentRef.current = agentType;
                break;

              case "agent_message":
                currentMessageBufferRef.current += event.content;
                const fullContent = currentMessageBufferRef.current;
                
                // Create or update assistant message
                setMessages((prev) => {
                  const lastMsg = prev[prev.length - 1];
                  const agentType = event.agent.includes("coordinator") ? "coordinator" :
                                   event.agent.includes("flight") ? "flight" :
                                   event.agent.includes("hotel") ? "hotel" : "research";
                  const flightResults = parseFlightResults(fullContent);
                  const hotelResults = parseHotelResults(fullContent);

                  const newMessage: ChatMessage = {
                    id: `${event.agent}-${Date.now()}`,
                    text: fullContent,
                    isUser: false,
                    timestamp: new Date(),
                    agentType: agentType as any,
                    flightResults: flightResults || undefined,
                    hotelResults: hotelResults || undefined,
                  };

                  // If last message is from same agent, update it; otherwise add new
                  if (!lastMsg.isUser && lastMsg.agentType === agentType) {
                    return [...prev.slice(0, -1), newMessage];
                  }
                  return [...prev, newMessage];
                });
                break;

              case "agent_complete":
                const completedAgent = event.agent.includes("coordinator") ? "coordinator" :
                                      event.agent.includes("flight") ? "flight" :
                                      event.agent.includes("hotel") ? "hotel" : "research";
                // On completion, parse the full buffer one more time to catch final JSON
                if (completedAgent === "flight" || completedAgent === "hotel") {
                  const finalContent = currentMessageBufferRef.current;
                  const finalFlights = parseFlightResults(finalContent);
                  const finalHotels = parseHotelResults(finalContent);
                  if ((finalFlights && finalFlights.length) || (finalHotels && finalHotels.length)) {
                    setMessages((prev) => {
                      const last = prev[prev.length - 1];
                      if (!last || last.isUser) return prev;
                      const updated = { ...last, text: finalContent, flightResults: finalFlights || last.flightResults, hotelResults: finalHotels || last.hotelResults };
                      return [...prev.slice(0, -1), updated];
                    });
                  }
                }
                updateAgentStatus(completedAgent, "complete");
                break;

              case "tool_start":
                console.log("Tool started:", event.tool);
                break;

              case "tool_complete":
                console.log("Tool completed:", event.tool);
                break;

              case "token":
                // Real-time token streaming (optional for smoother UX)
                currentMessageBufferRef.current += event.content;
                break;

              case "complete":
                console.log("Query completed");
                setIsLoading(false);
                setTimeout(resetAgents, 2000);
                currentQueryIdRef.current = null;
                break;

              case "interrupted":
                console.log("Query interrupted:", event.reason);
                setMessages((prev) => [
                  ...prev,
                  {
                    id: Date.now().toString(),
                    text: `⏸️ ${event.reason || "Query interrupted"}`,
                    isUser: false,
                    timestamp: new Date(),
                    agentType: "coordinator",
                    isPartial: true,
                  },
                ]);
                setIsLoading(false);
                resetAgents();
                currentQueryIdRef.current = null;
                break;

              case "error":
                console.error("Stream error:", event.message);
                setMessages((prev) => [
                  ...prev,
                  {
                    id: Date.now().toString(),
                    text: `❌ Error: ${event.message}`,
                    isUser: false,
                    timestamp: new Date(),
                    agentType: "coordinator",
                  },
                ]);
                setIsLoading(false);
                resetAgents();
                break;
            }
          } catch (parseError) {
            console.error("Error parsing SSE event:", parseError);
          }
        }
      }
    } catch (error) {
      console.error("Error sending message:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          text: `❌ Connection error: ${error instanceof Error ? error.message : "Unknown error"}. Make sure Python backend is running at ${PYTHON_BACKEND_URL}`,
          isUser: false,
          timestamp: new Date(),
          agentType: "coordinator",
        },
      ]);
      setIsLoading(false);
      resetAgents();
    }
  }, [isLoading, updateAgentStatus, resetAgents]);

  return {
    messages,
    agents,
    isLoading,
    sendMessage,
    cancelQuery: cancelCurrentQuery,
    hasActiveQuery: !!currentQueryIdRef.current,
  };
}
