"use client";

import { motion } from "framer-motion";
import { Plane, Building2, Sparkles, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MorphingText } from "@/components/ui/MorphingText";
import { RetroGrid } from "@/components/ui/RetroGrid";
import { InteractiveHoverButton } from "@/components/ui/InteractiveHoverButton";

import Link from "next/link";

export default function Home() {
  const features = [
    {
      icon: Sparkles,
      title: "Intelligent Coordination",
      description:
        "Our coordinator agent understands your needs and routes requests efficiently.",
    },
    {
      icon: Plane,
      title: "Flight Search",
      description: "Real-time flight searches with the best prices and schedules.",
    },
    {
      icon: Building2,
      title: "Hotel Finder",
      description:
        "Curated hotel recommendations based on your preferences.",
    },
  ];

  return (
    <div className="min-h-screen bg-black text-white overflow-hidden">

      {/* Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="relative h-full w-full overflow-hidden">
          <RetroGrid
            opacity={0.9}
            lightLineColor="#39ff14"
            darkLineColor="#00c853"
          />
        </div>

        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.1, 0.2, 0.1] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500 rounded-full blur-[100px]"
        />

        <motion.div
          animate={{ scale: [1, 1.3, 1], opacity: [0.1, 0.15, 0.1] }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 1,
          }}
          className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500 rounded-full blur-[100px]"
        />
      </div>

      {/* Hero Section */}
      <div className="relative z-10 container mx-auto px-4 py-20">
        <div className="flex flex-col items-center justify-center min-h-[80vh] text-center">

          {/* Main Heading */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.8 }}
            className="mb-20 w-full flex justify-center"
          >
            <MorphingText
              texts={[
                "Your AI Travel Planning Assistant",
                "Plan Smarter. Travel Better.",
              ]}
              className="text-white text-4xl md:text-6xl lg:text-7xl font-bold leading-tight"
            />
          </motion.div>

          {/* Subheading */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.8 }}
            className="mt-6 text-xl text-zinc-400 max-w-2xl mb-12"
          >
            Experience the future of travel planning with our multi-agent AI system.
            Find flights, hotels, and complete travel packages—all in one conversation.
          </motion.p>

          {/* CTA Button */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.8 }}
          >
            <Link href="/chat">
              <InteractiveHoverButton className="mt-4 bg-gradient-to-r from-[#39ff14] to-[#00c853] text-black text-lg px-8 py-3 border-none shadow-2xl shadow-emerald-400/40">
                Start Planning Your Trip
              </InteractiveHoverButton>
            </Link>
          </motion.div>

          
        </div>
      </div>
    </div>
  );
}
