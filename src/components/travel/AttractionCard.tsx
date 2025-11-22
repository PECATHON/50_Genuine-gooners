"use client";

import { motion } from "framer-motion";
import { MapPin, Star, Camera } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface AttractionCardProps {
  name: string;
  location: string;
  rating?: number;
  reviews?: number;
  price?: string;
  imageUrl?: string | null;
  index?: number;
}

export function AttractionCard({
  name,
  location,
  rating,
  reviews,
  price,
  imageUrl,
  index = 0,
}: AttractionCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ scale: 1.02, y: -4 }}
      className="w-full"
    >
      <Card className="overflow-hidden bg-gradient-to-br from-emerald-950/30 via-slate-900/40 to-zinc-900/60 border-emerald-500/25 hover:border-emerald-400/60 transition-all duration-300 shadow-lg shadow-emerald-900/20">
        <CardContent className="p-0">
          {imageUrl && (
            <div className="relative h-40 w-full overflow-hidden">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt={name}
                className="h-full w-full object-cover transform transition-transform duration-500 hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-900/40 to-transparent" />
              <div className="absolute top-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-zinc-900/80 px-2.5 py-1 text-xs text-zinc-100">
                <Camera className="h-3 w-3 text-emerald-300" />
                <span className="font-medium">Top sight</span>
              </div>
            </div>
          )}

          <div className="p-5">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/15 border border-emerald-500/40 text-[10px] font-semibold text-emerald-300">
                    POI
                  </span>
                  <h3 className="text-sm sm:text-base font-semibold text-white truncate" title={name}>
                    {name}
                  </h3>
                </div>
                <div className="flex items-center gap-1.5 text-zinc-400 text-xs sm:text-sm">
                  <MapPin className="h-3.5 w-3.5" />
                  <span className="truncate" title={location}>{location}</span>
                </div>
              </div>

              <div className="flex flex-col items-end gap-1">
                {typeof rating === "number" && rating > 0 && (
                  <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2 py-1 text-xs">
                    <Star className="h-3.5 w-3.5 fill-emerald-400 text-emerald-400" />
                    <span className="text-emerald-100 font-semibold">{rating.toFixed(1)}</span>
                    {typeof reviews === "number" && reviews > 0 && (
                      <span className="text-[10px] text-emerald-200/80">({reviews.toLocaleString()} reviews)</span>
                    )}
                  </div>
                )}
                {price && (
                  <span className="mt-1 inline-flex items-center rounded-full bg-zinc-900/70 border border-zinc-700/70 px-2 py-0.5 text-[11px] text-zinc-200">
                    from&nbsp;<span className="font-semibold text-emerald-300">{price}</span>
                  </span>
                )}
              </div>
            </div>

            <div className="mt-1 flex flex-wrap gap-1.5 text-[10px] text-zinc-300">
              <span className="px-2 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30">
                Perfect for first-time visitors
              </span>
              <span className="px-2 py-1 rounded-full bg-sky-500/10 border border-sky-500/30">
                Curated by Booking.com
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
