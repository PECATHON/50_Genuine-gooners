"use client";
import React, { useMemo, useState } from "react";
import { FlightCard, FlightOption } from "@/components/FlightCard";

function toFlightOption(obj: any): FlightOption {
  let price: FlightOption["price"] | undefined;
  let currency: string | undefined;
  let airline: string | undefined;
  let departTime: string | undefined;
  let arriveTime: string | undefined;
  let duration: string | number | undefined;
  let stops: number | undefined;

  if (obj && typeof obj === "object") {
    // price candidates
    if (typeof obj.price === "number" || typeof obj.price === "string") price = obj.price;
    else if (obj.price && typeof obj.price === "object") price = obj.price;
    else if (obj.pricing && typeof obj.pricing === "object") {
      price = obj.pricing.total ?? obj.pricing;
      currency = currency || obj.pricing.currency;
    }

    currency = currency || obj.currency || obj?.price?.currency;

    // segments/legs
    const segments = obj.segments || obj.legs || obj.itinerarySegments || [];
    if (Array.isArray(segments) && segments.length) {
      const first = segments[0] || {};
      const last = segments[segments.length - 1] || {};
      airline = first.carrier || first.airline || first.marketingCarrier || airline;
      departTime = first.departureTime || first.departure || first.departureDateTime || departTime;
      arriveTime = last.arrivalTime || last.arrival || last.arrivalDateTime || arriveTime;
      stops = Math.max(0, segments.length - 1);
    }

    duration = obj.duration || obj.totalDuration || duration;
  }

  return { airline, price, currency, departTime, arriveTime, duration, stops, raw: obj };
}

export default function FlightsPage() {
  const [fromId, setFromId] = useState("BOM.AIRPORT");
  const [toId, setToId] = useState("DEL.AIRPORT");
  const [departDate, setDepartDate] = useState("2025-11-23");
  const [adults, setAdults] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<any>(null);

  const options: FlightOption[] = useMemo(() => {
    const results: FlightOption[] = [];
    const root = payload?.results ?? payload; // tool returns {status, query, results}
    const data = root?.data ?? root;
    if (!data || typeof data !== "object") return results;

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
    if (typeof data === "object") {
      Object.values(data).forEach((v) => {
        if (Array.isArray(v) && v.length) candidateLists.push(v);
      });
    }

    const list = candidateLists[0] || [];
    for (const item of list.slice(0, 10)) results.push(toFlightOption(item));
    return results;
  }, [payload]);

  const search = async () => {
    setLoading(true);
    setError(null);
    setPayload(null);
    try {
      const url = new URL("/api/flights/search", process.env.NEXT_PUBLIC_PYTHON_BACKEND_URL || "http://localhost:8000");
      url.searchParams.set("fromId", fromId);
      url.searchParams.set("toId", toId);
      url.searchParams.set("departDate", departDate);
      url.searchParams.set("adults", String(adults));
      const res = await fetch(url.toString());
      const json = await res.json();
      if (!res.ok || json?.status === "error") {
        throw new Error(json?.message || json?.detail || `HTTP ${res.status}`);
      }
      setPayload(json);
    } catch (e: any) {
      setError(e?.message || "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-semibold text-zinc-900 mb-4">Find Flights</h1>

      <div className="rounded-xl border border-zinc-200 bg-white p-4 mb-6 grid grid-cols-1 md:grid-cols-5 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500">From (fromId)</label>
          <input value={fromId} onChange={(e) => setFromId(e.target.value)} className="h-9 px-3 border rounded-md" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500">To (toId)</label>
          <input value={toId} onChange={(e) => setToId(e.target.value)} className="h-9 px-3 border rounded-md" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500">Depart date</label>
          <input type="date" value={departDate} onChange={(e) => setDepartDate(e.target.value)} className="h-9 px-3 border rounded-md" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500">Adults</label>
          <input type="number" min={1} value={adults} onChange={(e) => setAdults(parseInt(e.target.value || "1", 10))} className="h-9 px-3 border rounded-md" />
        </div>
        <div className="flex items-end">
          <button onClick={search} disabled={loading} className="w-full h-9 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50">
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="text-red-600 text-sm mb-4">{error}</div>
      ) : null}

      {options.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {options.slice(0, 10).map((opt, idx) => (
            <FlightCard key={idx} option={opt} />
          ))}
        </div>
      ) : (
        <div className="text-sm text-zinc-500">No flights yet. Set parameters and click Search.</div>
      )}
    </div>
  );
}
