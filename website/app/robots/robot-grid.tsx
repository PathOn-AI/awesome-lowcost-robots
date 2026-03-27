"use client";

import { useState } from "react";
import type { Robot } from "@/lib/robots";

export function RobotGrid({
  robots,
  categories,
  purposes,
}: {
  robots: Robot[];
  categories: string[];
  purposes: string[];
}) {
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [activePurpose, setActivePurpose] = useState<string | null>(null);

  const filtered = robots.filter((r) => {
    if (activeCategory && r.category !== activeCategory) return false;
    if (activePurpose && !r.purpose.includes(activePurpose)) return false;
    return true;
  });

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 mb-8">
        {/* Type dropdown */}
        <select
          value={activeCategory}
          onChange={(e) => setActiveCategory(e.target.value)}
          className="h-9 px-3 pr-8 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-700 appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2216%22%20height%3D%2216%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%236b7280%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-[length:16px] bg-[right_8px_center] bg-no-repeat cursor-pointer hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-1"
        >
          <option value="">All Types ({robots.length})</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat} ({robots.filter((r) => r.category === cat).length})
            </option>
          ))}
        </select>

        {/* Divider */}
        <div className="h-5 w-px bg-gray-200" />

        {/* Purpose pills */}
        <button
          onClick={() => setActivePurpose(null)}
          className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
            activePurpose === null
              ? "bg-gray-900 text-white"
              : "bg-gray-100 text-gray-700 hover:bg-gray-200"
          }`}
        >
          All
        </button>
        {purposes.map((p) => (
          <button
            key={p}
            onClick={() => setActivePurpose(p)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              activePurpose === p
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Result count */}
      <p className="text-sm text-gray-400 mb-4">
        Showing {filtered.length} of {robots.length} robots
      </p>

      {/* Robot cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {filtered.map((robot) => (
          <a
            key={robot.slug}
            href={`/robots/${robot.slug}`}
            className="group block border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
          >
            <div className="aspect-video bg-gray-100 relative overflow-hidden">
              <img
                src={robot.image}
                alt={robot.name}
                className="absolute inset-0 w-full h-full object-cover"
              />
            </div>
            <div className="p-4">
              <div className="flex items-start justify-between gap-2 mb-2">
                <h3 className="font-semibold group-hover:text-blue-600 transition-colors">
                  {robot.name}
                </h3>
                <span className="shrink-0 text-xs px-2 py-1 bg-gray-100 rounded-full text-gray-600">
                  {robot.category}
                </span>
              </div>
              <p className="text-sm text-gray-600 line-clamp-2">
                {robot.description}
              </p>
              {robot.purpose.length > 0 && (
                <div className="flex gap-1.5 mt-3">
                  {robot.purpose.map((p) => (
                    <span
                      key={p}
                      className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full"
                    >
                      {p}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
