import { SlidersHorizontal } from "lucide-react";
import type { FilterOptions, FilterState } from "../../types";
import { formatPrice } from "../../lib/utils";
import { METROS } from "./metros";

interface FilterPanelProps {
  options: FilterOptions | null;
  filters: FilterState;
  onChange: (patch: Partial<FilterState>) => void;
  onSearch: () => void;
  loading: boolean;
}

export const METRO_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(METROS).map(([city, meta]) => [city, meta.state])
);

export default function FilterPanel({
  options,
  filters,
  onChange,
  onSearch,
  loading,
}: FilterPanelProps) {
  if (!options) {
    return (
      <div className="animate-pulse space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 rounded bg-gray-200" />
        ))}
      </div>
    );
  }

  const handleCityChange = (city: string) => {
    const state = METRO_MAP[city] || "";
    onChange({ city, state });
  };

  const handleStateChange = (state: string) => {
    onChange({ state });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-gray-500">
        <SlidersHorizontal className="h-4 w-4" />
        Filters
      </div>

      {/* City */}
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-gray-600">
          City
        </span>
        <select
          value={filters.city}
          onChange={(e) => handleCityChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-xome-500 focus:outline-none focus:ring-1 focus:ring-xome-500"
        >
          <option value="">All Cities</option>
          {options.cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>

      {/* State */}
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-gray-600">
          State
        </span>
        <select
          value={filters.state}
          onChange={(e) => handleStateChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-xome-500 focus:outline-none focus:ring-1 focus:ring-xome-500"
        >
          <option value="">All States</option>
          {options.states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      {/* Price Range */}
      <div>
        <span className="mb-1 block text-xs font-medium text-gray-600">
          Price Range
        </span>
        <div className="space-y-2">
          <input
            type="range"
            min={options.price_range.min}
            max={options.price_range.max}
            step={10000}
            value={filters.price_min}
            onChange={(e) =>
              onChange({ price_min: Number(e.target.value) })
            }
            className="w-full accent-xome-600"
          />
          <input
            type="range"
            min={options.price_range.min}
            max={options.price_range.max}
            step={10000}
            value={filters.price_max}
            onChange={(e) =>
              onChange({ price_max: Number(e.target.value) })
            }
            className="w-full accent-xome-600"
          />
          <div className="flex justify-between text-xs text-gray-500">
            <span>{formatPrice(filters.price_min)}</span>
            <span>{formatPrice(filters.price_max)}</span>
          </div>
        </div>
      </div>

      {/* Top Listings */}
      <div>
        <span className="mb-1 block text-xs font-medium text-gray-600">
          Top Listings
        </span>
        <input
          type="range"
          min={1}
          max={30}
          step={1}
          value={filters.listing_count}
          onChange={(e) =>
            onChange({ listing_count: Number(e.target.value) })
          }
          className="w-full accent-xome-600"
        />
        <div className="flex justify-between text-xs text-gray-500">
          <span>1</span>
          <span className="font-semibold text-xome-700">{filters.listing_count}</span>
          <span>30</span>
        </div>
      </div>

      {/* Property Type */}
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-gray-600">
          Property Type
        </span>
        <select
          value={filters.property_type}
          onChange={(e) => onChange({ property_type: e.target.value })}
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-xome-500 focus:outline-none focus:ring-1 focus:ring-xome-500"
        >
          <option value="">All Types</option>
          {options.property_types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      {/* Segment */}
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-gray-600">
          Buyer Segment
        </span>
        <select
          value={filters.segment}
          onChange={(e) => onChange({ segment: e.target.value })}
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-xome-500 focus:outline-none focus:ring-1 focus:ring-xome-500"
        >
          <option value="">All Segments</option>
          {options.segments.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      {/* Search button */}
      <button
        onClick={onSearch}
        disabled={loading}
        className="w-full rounded-md bg-xome-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-xome-700 disabled:opacity-50"
      >
        {loading ? "Applying..." : "Apply Filters"}
      </button>
    </div>
  );
}
