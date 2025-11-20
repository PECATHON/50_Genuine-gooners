"use client";

import { motion } from "framer-motion";
import { Building2, MapPin, Star, DollarSign } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface HotelCardProps {
  name: string;
  location: string;
  rating: number;
  price: string;
  amenities: string[];
  imageUrl?: string;
  index?: number;
}

export function HotelCard({
  name,
  location,
  rating,
  price,
  amenities,
  imageUrl,
  index = 0,
}: HotelCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ scale: 1.02, y: -4 }}
      className="w-full"
    >
      <Card className="overflow-hidden bg-gradient-to-br from-purple-950/30 to-zinc-900/50 border-purple-500/20 hover:border-purple-500/40 transition-all duration-300">
        <CardContent className="p-0">
          {imageUrl && (
            <div className="relative h-40 w-full overflow-hidden">
              <img
                src={imageUrl}
                alt={name}
                className="h-full w-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-zinc-900 to-transparent" />
            </div>
          )}
          
          <div className="p-5">
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <Building2 className="h-4 w-4 text-purple-400" />
                  <h3 className="text-lg font-bold text-white">{name}</h3>
                </div>
                <div className="flex items-center gap-1.5 text-zinc-400 text-sm">
                  <MapPin className="h-3.5 w-3.5" />
                  <span>{location}</span>
                </div>
              </div>
              
              <div className="flex flex-col items-end">
                <div className="flex items-center gap-1 mb-1">
                  <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                  <span className="text-white font-semibold">{rating}</span>
                </div>
                <div className="flex items-center gap-1">
                  <DollarSign className="h-4 w-4 text-emerald-400" />
                  <span className="text-lg font-bold text-emerald-400">{price}</span>
                </div>
              </div>
            </div>
            
            <div className="flex flex-wrap gap-2">
              {amenities.map((amenity, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-300"
                >
                  {amenity}
                </span>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
