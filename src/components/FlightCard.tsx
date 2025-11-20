"use client";
import React from "react";

type Price = {
  currencyCode?: string;
  units?: number;
  nanos?: number;
  amount?: number | string;
};

export type FlightOption = {
  airline?: string;
  price?: Price | number | string;
  currency?: string;
  departTime?: string;
  arriveTime?: string;
  duration?: string | number;
  stops?: number;
  segments?: any[];
  raw?: any;
};

function formatPrice(price: FlightOption["price"], currency?: string) {
  if (typeof price === "number" || typeof price === "string") {
    return `${price}${currency ? ` ${currency}` : ""}`;
  }
  if (price && typeof price === "object") {
    const cur = currency || price.currencyCode || "";
    const units = price.units ?? (typeof price.amount === "number" ? price.amount : undefined);
    const nanos = price.nanos ?? 0;
    if (typeof units === "number") {
      const total = units + (typeof nanos === "number" ? nanos / 1e9 : 0);
      return `${Math.round(total)}${cur ? ` ${cur}` : ""}`;
    }
  }
  return "";
}

function formatTimeLabel(label?: string) {
  if (!label) return "";
  // Basic ISO or time string passthrough
  return label.replace("T", " ");
}

export const FlightCard: React.FC<{ option: FlightOption }> = ({ option }) => {
  const airline = option.airline || "";
  const priceText = formatPrice(option.price, option.currency);
  const depart = formatTimeLabel(option.departTime);
  const arrive = formatTimeLabel(option.arriveTime);
  const duration = option.duration ? String(option.duration) : "";
  const stops = typeof option.stops === "number" ? option.stops : undefined;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm hover:shadow-md transition p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="font-semibold text-zinc-800 truncate">
          {airline || "Flight option"}
        </div>
        {priceText ? (
          <div className="text-indigo-600 font-bold text-lg">{priceText}</div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm text-zinc-600">
        <div>
          <div className="text-zinc-500">Departure</div>
          <div className="font-medium text-zinc-800">{depart || "—"}</div>
        </div>
        <div>
          <div className="text-zinc-500">Arrival</div>
          <div className="font-medium text-zinc-800">{arrive || "—"}</div>
        </div>
        <div>
          <div className="text-zinc-500">Duration</div>
          <div className="font-medium text-zinc-800">{duration || "—"}</div>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-500">
        <div>{typeof stops === "number" ? `${stops} stop${stops === 1 ? "" : "s"}` : "Stops —"}</div>
        <button
          className="px-3 py-1.5 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 text-xs"
          onClick={() => {
            if (option.raw) {
              console.log("Flight raw option:", option.raw);
              alert("Logged this flight option to console.");
            }
          }}
        >
          View details
        </button>
      </div>
    </div>
  );
};
