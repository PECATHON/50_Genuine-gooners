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
    try {
      // Extract flight data from coordinator/flight agent messages
      const flightPattern = /(\d+)\.\s*([^-]+?)\s*-\s*\$(\d+)\s*\n\s*(\d{1,2}:\d{2}\s*[AP]M)\s*→\s*(\d{1,2}:\d{2}\s*[AP]M)\s*\(([^)]+)\)/g;
      const matches = [...content.matchAll(flightPattern)];
      
      if (matches.length === 0) return null;

      return matches.map(match => ({
        airline: match[2].trim(),
        price: `$${match[3]}`,
        departure: match[4],
        arrival: match[5],
        duration: match[6],
        from: "NYC", // Default, should be extracted
        to: "LAX",
      }));
    } catch {
      return null;
    }
  };

  const parseHotelResults = (content: string): any[] | null => {
    try {
      const hotelPattern = /(\d+)\.\s*([^-]+?)\s*-\s*\$(\d+)\/night\s*\n\s*Rating:\s*([\d.]+)⭐\s*\((\d+)\s*reviews\)/g;
      const matches = [...content.matchAll(hotelPattern)];
      
      if (matches.length === 0) return null;

      return matches.map(match => ({
        name: match[2].trim(),
        price: `$${match[3]}`,
        rating: parseFloat(match[4]),
        reviews_count: parseInt(match[5]),
        location: "Los Angeles",
        amenities: ["Pool", "Gym", "Free WiFi"],
        imageUrl: "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80",
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
                
                // Create or update assistant message
                setMessages((prev) => {
                  const lastMsg = prev[prev.length - 1];
                  const agentType = event.agent.includes("coordinator") ? "coordinator" :
                                   event.agent.includes("flight") ? "flight" :
                                   event.agent.includes("hotel") ? "hotel" : "research";
                  
                  const flightResults = parseFlightResults(event.content);
                  const hotelResults = parseHotelResults(event.content);

                  const newMessage: ChatMessage = {
                    id: `${event.agent}-${Date.now()}`,
                    text: event.content,
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
