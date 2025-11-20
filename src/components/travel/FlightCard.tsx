"use client";

import { motion } from "framer-motion";
import { Plane, Clock, DollarSign } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface FlightCardProps {
  from: string;
  to: string;
  departure: string;
  arrival: string;
  duration: string;
  price: string;
  airline: string;
  airlineCode?: string;
  logoUrl?: string;
  stops?: number | null;
  index?: number;
}

export function FlightCard({
  from,
  to,
  departure,
  arrival,
  duration,
  price,
  airline,
  airlineCode,
  logoUrl,
  stops,
  index = 0,
}: FlightCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ scale: 1.02, y: -4 }}
      className="w-full"
    >
      <Card className="overflow-hidden bg-gradient-to-br from-blue-950/30 to-zinc-900/50 border-blue-500/20 hover:border-blue-500/40 transition-all duration-300">
        <CardContent className="p-5">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                {logoUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={logoUrl} alt={airline} className="h-4 w-4 rounded-sm object-contain" />
                ) : null}
                <p className="text-xs text-zinc-500">
                  {airline}
                  {airlineCode ? <span className="ml-1 text-zinc-400">({airlineCode})</span> : null}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-white">{from}</span>
                <motion.div
                  animate={{ x: [0, 5, 0] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <Plane className="h-5 w-5 text-blue-400" />
                </motion.div>
                <span className="text-2xl font-bold text-white">{to}</span>
              </div>
            </div>
            <div className="flex flex-col items-end">
              <DollarSign className="h-4 w-4 text-emerald-400 mb-1" />
              <span className="text-2xl font-bold text-emerald-400">{price}</span>
            </div>
          </div>
          
          <div className="flex items-center justify-between text-sm">
            <div className="flex flex-col">
              <span className="text-zinc-500 text-xs mb-1">Departure</span>
              <span className="text-white font-medium">{departure}</span>
            </div>
            
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-800/50 border border-zinc-700/50">
              <Clock className="h-3.5 w-3.5 text-zinc-400" />
              <span className="text-xs text-zinc-300">
                {duration || (typeof stops === 'number' ? `${stops} stop${stops === 1 ? '' : 's'}` : '—')}
              </span>
            </div>
            
            <div className="flex flex-col items-end">
              <span className="text-zinc-500 text-xs mb-1">Arrival</span>
              <span className="text-white font-medium">{arrival}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
