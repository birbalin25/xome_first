import { MapPin, Tag, User } from "lucide-react";
import type { FilterState, UserSummary } from "../../types";
import { formatPrice } from "../../lib/utils";

interface GenieUserListProps {
  users: UserSummary[];
  filters: FilterState;
  onSelectUser: (userId: string) => void;
}

const SEGMENT_COLORS: Record<string, string> = {
  first_time_buyer: "bg-green-100 text-green-700",
  investor: "bg-purple-100 text-purple-700",
  upgrader: "bg-blue-100 text-blue-700",
  downsizer: "bg-amber-100 text-amber-700",
};

function matchesFilters(user: UserSummary, filters: FilterState): boolean {
  if (filters.city && user.preferred_city !== filters.city) return false;
  if (filters.state && user.preferred_state !== filters.state) return false;
  if (filters.property_type && user.preferred_property_type !== filters.property_type) return false;
  if (filters.segment && user.user_segment !== filters.segment) return false;

  const budgetMin = parseFloat(user.budget_min) || 0;
  const budgetMax = parseFloat(user.budget_max) || Infinity;
  if (filters.price_min > 0 && budgetMax < filters.price_min) return false;
  if (filters.price_max < 5_000_000 && budgetMin > filters.price_max) return false;

  return true;
}

export default function GenieUserList({
  users,
  filters,
  onSelectUser,
}: GenieUserListProps) {
  const filtered = users.filter((u) => matchesFilters(u, filters));

  if (users.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border-2 border-dashed border-gray-200 text-gray-400">
        Use the search bar above to find users with Genie
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-gray-500">
        Showing {filtered.length} of {users.length} users
      </div>

      {filtered.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-gray-200 text-gray-400">
          No users match the current filters
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((user) => {
            const segmentClass =
              SEGMENT_COLORS[user.user_segment] || "bg-gray-100 text-gray-700";
            return (
              <button
                key={user.user_id}
                onClick={() => onSelectUser(user.user_id)}
                className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 text-left shadow-sm transition hover:border-xome-400 hover:shadow-md"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-xome-100 text-xs font-bold text-xome-700">
                      {user.first_name?.[0] || ""}
                      {user.last_name?.[0] || ""}
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-gray-900">
                        {user.first_name} {user.last_name}
                      </div>
                      <div className="truncate text-xs text-gray-400">
                        {user.email}
                      </div>
                    </div>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize ${segmentClass}`}
                  >
                    {user.user_segment?.replace(/_/g, " ")}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {user.preferred_city}, {user.preferred_state}
                  </span>
                  <span>
                    {formatPrice(user.budget_min)} - {formatPrice(user.budget_max)}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1 text-gray-400">
                    <Tag className="h-3 w-3" />
                    {user.preferred_property_type}
                  </span>
                  <span className="font-medium text-xome-600">
                    {user.rec_count || 0} recs
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
