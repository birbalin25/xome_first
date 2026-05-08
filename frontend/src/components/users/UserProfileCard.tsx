import { BedDouble, DollarSign, Heart, Mail, MapPin, Phone, Tag } from "lucide-react";
import type { UserProfile } from "../../types";
import { formatPrice } from "../../lib/utils";

interface UserProfileCardProps {
  profile: UserProfile;
}

const SEGMENT_COLORS: Record<string, string> = {
  first_time_buyer: "bg-green-100 text-green-700 border-green-200",
  investor: "bg-purple-100 text-purple-700 border-purple-200",
  upgrader: "bg-blue-100 text-blue-700 border-blue-200",
  downsizer: "bg-amber-100 text-amber-700 border-amber-200",
};

export default function UserProfileCard({ profile }: UserProfileCardProps) {
  const segmentClass =
    SEGMENT_COLORS[profile.user_segment] || "bg-gray-100 text-gray-700 border-gray-200";

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      {/* Header row: avatar + name + segment */}
      <div className="flex items-center gap-4 border-b border-gray-100 px-5 py-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-xome-100 text-sm font-bold text-xome-700">
          {profile.first_name[0]}{profile.last_name[0]}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-gray-900">
            {profile.first_name} {profile.last_name}
          </h3>
          <span className="mt-0.5 flex items-center gap-1.5 text-xs text-gray-500">
            <Tag className="h-3 w-3" />
            <span className="font-mono">{profile.user_id}</span>
          </span>
        </div>
        <span
          className={`shrink-0 rounded-full border px-3 py-1 text-xs font-semibold capitalize ${segmentClass}`}
        >
          {profile.user_segment?.replace(/_/g, " ")}
        </span>
      </div>

      {/* Detail chips row */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3 text-sm text-gray-600">
        <div className="flex items-center gap-1.5">
          <Mail className="h-3.5 w-3.5 text-gray-400" />
          <span>{profile.email}</span>
        </div>
        {profile.phone && (
          <div className="flex items-center gap-1.5">
            <Phone className="h-3.5 w-3.5 text-gray-400" />
            <span>{profile.phone}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <MapPin className="h-3.5 w-3.5 text-gray-400" />
          <span>{profile.preferred_city}, {profile.preferred_state}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <DollarSign className="h-3.5 w-3.5 text-gray-400" />
          <span>{formatPrice(profile.budget_min)} &ndash; {formatPrice(profile.budget_max)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Heart className="h-3.5 w-3.5 text-gray-400" />
          <span>{profile.preferred_property_type}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <BedDouble className="h-3.5 w-3.5 text-gray-400" />
          <span>{profile.preferred_beds_min}+ beds</span>
        </div>
      </div>
    </div>
  );
}
