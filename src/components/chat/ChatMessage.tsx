"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  timestamp?: Date;
  agentType?: "coordinator" | "flight" | "hotel";
}

export function ChatMessage({ message, isUser, timestamp, agentType }: ChatMessageProps) {
  const getAgentColor = () => {
    switch (agentType) {
      case "flight":
        return "from-blue-500/20 to-blue-600/10 border-blue-500/30";
      case "hotel":
        return "from-purple-500/20 to-purple-600/10 border-purple-500/30";
      case "coordinator":
        return "from-emerald-500/20 to-emerald-600/10 border-emerald-500/30";
      default:
        return "from-zinc-800/50 to-zinc-900/50 border-zinc-700/50";
    }
  };

  const getAgentLabel = () => {
    switch (agentType) {
      case "flight":
        return "Flight Agent";
      case "hotel":
        return "Hotel Agent";
      case "coordinator":
        return "Coordinator";
      default:
        return "Assistant";
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={cn(
        "flex w-full gap-3",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 backdrop-blur-sm",
          isUser
            ? "bg-gradient-to-br from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-900/20"
            : cn("bg-gradient-to-br border shadow-lg", getAgentColor())
        )}
      >
        {!isUser && agentType && (
          <div className="mb-1 flex items-center gap-2">
            <div className={cn(
              "h-2 w-2 rounded-full animate-pulse",
              agentType === "flight" ? "bg-blue-400" :
              agentType === "hotel" ? "bg-purple-400" :
              "bg-emerald-400"
            )} />
            <span className="text-xs font-medium text-zinc-400">
              {getAgentLabel()}
            </span>
          </div>
        )}
        <p className={cn(
          "text-sm leading-relaxed whitespace-pre-wrap",
          isUser ? "text-white" : "text-zinc-100"
        )}>
          {message}
        </p>
        {timestamp && (
          <div className={cn(
            "mt-1 text-xs",
            isUser ? "text-blue-100/70" : "text-zinc-500"
          )}>
            {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>
    </motion.div>
  );
}
