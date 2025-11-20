"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Plane, Building2, Sparkles, Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface AgentStatusProps {
  agents: {
    type: "coordinator" | "flight" | "hotel" | "research";
    status: "idle" | "active" | "complete";
    message?: string;
  }[];
}

export function AgentStatus({ agents }: AgentStatusProps) {
  const activeAgents = agents.filter(a => a.status !== "idle");

  if (activeAgents.length === 0) return null;

  const getIcon = (type: string) => {
    switch (type) {
      case "flight":
        return Plane;
      case "hotel":
        return Building2;
      case "research":
        return Search;
      default:
        return Sparkles;
    }
  };

  const getColor = (type: string) => {
    switch (type) {
      case "flight":
        return "text-blue-400 bg-blue-500/10 border-blue-500/30";
      case "hotel":
        return "text-purple-400 bg-purple-500/10 border-purple-500/30";
      case "research":
        return "text-cyan-400 bg-cyan-500/10 border-cyan-500/30";
      default:
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    }
  };

  const getLabel = (agent: typeof agents[0]) => {
    if (agent.message) return agent.message;
    
    const typeLabel = agent.type.charAt(0).toUpperCase() + agent.type.slice(1);
    if (agent.status === "complete") return `${typeLabel} ✓`;
    return `${typeLabel} working...`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="flex flex-wrap gap-2 mb-4"
    >
      <AnimatePresence mode="popLayout">
        {activeAgents.map((agent) => {
          const Icon = getIcon(agent.type);
          return (
            <motion.div
              key={agent.type}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.3 }}
              className={cn(
                "flex items-center gap-2 rounded-full border px-3 py-1.5 backdrop-blur-sm",
                getColor(agent.type)
              )}
            >
              {agent.status === "complete" ? (
                <Icon className="h-3.5 w-3.5" />
              ) : (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              )}
              <span className="text-xs font-medium">
                {getLabel(agent)}
              </span>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </motion.div>
  );
}