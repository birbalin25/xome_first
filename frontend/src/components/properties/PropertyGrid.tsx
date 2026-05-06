import type { Property } from "../../types";
import PropertyCard from "./PropertyCard";

interface PropertyGridProps {
  properties: Property[];
  loading: boolean;
  selectedIds?: Set<string>;
  onToggle?: (propertyId: string) => void;
}

export default function PropertyGrid({
  properties,
  loading,
  selectedIds,
  onToggle,
}: PropertyGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-72 animate-pulse rounded-xl border border-gray-200 bg-gray-100"
          />
        ))}
      </div>
    );
  }

  if (properties.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border-2 border-dashed border-gray-200 text-gray-400">
        Select a user to view their top recommended listings
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
      {properties.map((p) => (
        <PropertyCard
          key={p.property_id}
          property={p}
          selected={selectedIds?.has(p.property_id)}
          onToggle={onToggle}
        />
      ))}
    </div>
  );
}
