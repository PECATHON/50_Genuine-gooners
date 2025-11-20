"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, ArrowLeft, StopCircle, AlertCircle } from "lucide-react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { AgentStatus } from "@/components/chat/AgentStatus";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { FlightCard } from "@/components/travel/FlightCard";
import { HotelCard } from "@/components/travel/HotelCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSSEChat } from "@/hooks/useSSEChat";
import Link from "next/link";

export default function ChatPage() {
  const { messages, agents, isLoading, sendMessage, cancelQuery, hasActiveQuery } = useSSEChat();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    await sendMessage(input);
    setInput("");
  };

  const handleCancel = () => {
    cancelQuery();
  };

  return (
    <div className="flex h-screen flex-col bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950">
      {/* Header */}
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-xl"
      >
        <div className="container mx-auto flex items-center justify-between px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="icon" className="rounded-full">
                <ArrowLeft className="h-5 w-5" />
              </Button>
            </Link>
            <div>
              <h1 className="text-xl font-bold text-white">Travel Assistant</h1>
              <p className="text-sm text-zinc-400">AI-Powered Multi-Agent System</p>
            </div>
          </div>
          
          {/* Cancel Button - shown when query is active */}
          <AnimatePresence>
            {hasActiveQuery && (
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.8, opacity: 0 }}
              >
                <Button
                  onClick={handleCancel}
                  variant="destructive"
                  size="sm"
                  className="gap-2 rounded-full"
                >
                  <StopCircle className="h-4 w-4" />
                  Cancel Query
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.header>

      {/* Connection Warning Banner */}
      {messages.length > 0 && messages[messages.length - 1].text.includes("Connection error") && (
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="bg-destructive/10 border-b border-destructive/20 px-4 py-3"
        >
          <div className="container mx-auto max-w-4xl flex items-center gap-3 text-sm text-destructive">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <div>
              <strong>Python Backend Not Connected</strong>
              <p className="text-xs mt-1 opacity-80">
                Start the Python backend: <code className="bg-zinc-900 px-2 py-0.5 rounded">cd backend && python main.py</code>
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="container mx-auto max-w-4xl px-4 py-6">
          <AnimatePresence mode="popLayout">
            {messages.length === 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex h-full flex-col items-center justify-center gap-6 text-center"
              >
                <motion.div
                  animate={{
                    scale: [1, 1.1, 1],
                    rotate: [0, 5, -5, 0],
                  }}
                  transition={{
                    duration: 4,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                  className="text-6xl"
                >
                  ✈️
                </motion.div>
                <div>
                  <h2 className="text-2xl font-bold text-white mb-2">
                    Start Your Journey
                  </h2>
                  <p className="text-zinc-400 max-w-md">
                    Ask me about flights, hotels, or complete travel packages. I'll
                    coordinate multiple agents to find the best options for you.
                  </p>
                  <p className="text-xs text-zinc-500 mt-3">
                    💡 You can interrupt any query at any time using the Cancel button
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 justify-center">
                  {[
                    "Find flights from NYC to LAX",
                    "Hotels in Paris",
                    "Plan a trip to Tokyo",
                  ].map((suggestion, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      onClick={() => setInput(suggestion)}
                      className="rounded-full border-zinc-700 hover:border-blue-500/50 hover:bg-blue-500/10"
                    >
                      {suggestion}
                    </Button>
                  ))}
                </div>
              </motion.div>
            )}

            {messages.map((message) => (
              <div key={message.id} className="mb-6">
                <ChatMessage
                  message={message.text}
                  isUser={message.isUser}
                  timestamp={message.timestamp}
                  agentType={message.agentType}
                />

                {message.flightResults && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="mt-4 space-y-3"
                  >
                    {message.flightResults.map((flight, i) => (
                      <FlightCard key={i} {...flight} index={i} />
                    ))}
                  </motion.div>
                )}

                {message.hotelResults && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="mt-4 space-y-3"
                  >
                    {message.hotelResults.map((hotel, i) => (
                      <HotelCard key={i} {...hotel} index={i} />
                    ))}
                  </motion.div>
                )}

                {message.isPartial && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="mt-2 flex items-center gap-2 text-xs text-amber-400"
                  >
                    <AlertCircle className="h-3 w-3" />
                    Partial result - query was interrupted
                  </motion.div>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="mb-6">
                <TypingIndicator />
              </div>
            )}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Agent Status Bar */}
      <AnimatePresence>
        {agents.some((a) => a.status !== "idle") && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            className="border-t border-zinc-800 bg-zinc-900/50 backdrop-blur-xl px-4 py-3"
          >
            <div className="container mx-auto max-w-4xl">
              <AgentStatus agents={agents} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input Area */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="border-t border-zinc-800 bg-zinc-900/80 backdrop-blur-xl"
      >
        <div className="container mx-auto max-w-4xl px-4 py-4">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about flights, hotels, or travel plans..."
              disabled={isLoading}
              className="flex-1 bg-zinc-800/50 border-zinc-700 focus:border-blue-500 focus:ring-blue-500/20"
            />
            <Button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="rounded-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 px-6"
            >
              <Send className="h-4 w-4" />
            </Button>
          </form>
          <p className="text-xs text-zinc-500 mt-2 text-center">
            Powered by LangGraph Multi-Agent System with Request Interruption
          </p>
        </div>
      </motion.div>
    </div>
  );
}