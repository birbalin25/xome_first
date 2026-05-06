import { useCallback, useEffect, useState } from "react";
import type {
  FilterOptions,
  FilterState,
  GeneratedEmail,
  Property,
  UserProfile,
  UserSummary,
} from "../../types";
import * as api from "../../api/campaign";
import FilterPanel from "../filters/FilterPanel";
import UserDropdown from "../users/UserDropdown";
import UserProfileCard from "../users/UserProfileCard";
import PropertyGrid from "../properties/PropertyGrid";
import EmailActions from "../email/EmailActions";
import EmailPreview from "../email/EmailPreview";
import PropertyDetailModal from "../properties/PropertyDetailModal";
import Sidebar from "./Sidebar";

const INITIAL_FILTERS: FilterState = {
  city: "",
  state: "",
  property_type: "",
  segment: "",
  price_min: 0,
  price_max: 5_000_000,
  listing_count: 10,
};

export default function AppShell() {
  // ── Filter state ────────────────────────────
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [filters, setFilters] = useState<FilterState>(INITIAL_FILTERS);

  // ── Users ───────────────────────────────────
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [usersLoading, setUsersLoading] = useState(false);

  // ── Properties ──────────────────────────────
  const [properties, setProperties] = useState<Property[]>([]);
  const [propsLoading, setPropsLoading] = useState(false);

  // ── Email ───────────────────────────────────
  const [email, setEmail] = useState<GeneratedEmail | null>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedPath, setSavedPath] = useState("");

  // ── Property detail modal ─────────────────
  const [modalProperty, setModalProperty] = useState<Property | null>(null);

  // ── Load filter options on mount ────────────
  useEffect(() => {
    api.fetchFilters().then((opts) => {
      setFilterOptions(opts);
      setFilters((f) => ({
        ...f,
        price_min: opts.price_range.min,
        price_max: opts.price_range.max,
      }));
    });
  }, []);

  // ── Filter change handler ───────────────────
  const handleFilterChange = useCallback((patch: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
  }, []);

  // ── Search users ────────────────────────────
  const handleSearchUsers = useCallback(async () => {
    setUsersLoading(true);
    setSelectedUserId("");
    setUserProfile(null);
    setProperties([]);
    setEmail(null);
    setSavedPath("");
    try {
      const result = await api.searchUsers(filters);
      setUsers(result);
    } catch (err) {
      console.error("Failed to search users", err);
    } finally {
      setUsersLoading(false);
    }
  }, [filters]);

  // ── Select user → load profile + listings ───
  const handleSelectUser = useCallback(
    async (userId: string) => {
      setSelectedUserId(userId);
      setEmail(null);
      setSavedPath("");
      setPropsLoading(true);
      try {
        const [profile, listings] = await Promise.all([
          api.fetchUserProfile(userId),
          api.fetchListings(userId, {
            city: filters.city || undefined,
            state: filters.state || undefined,
            listing_count: filters.listing_count,
          }),
        ]);
        setUserProfile(profile);
        setProperties(listings);
      } catch (err) {
        console.error("Failed to load user data", err);
      } finally {
        setPropsLoading(false);
      }
    },
    [filters.city, filters.state, filters.listing_count]
  );

  // ── Generate email ──────────────────────────
  const handleGenerateEmail = useCallback(async () => {
    if (!selectedUserId || properties.length === 0) return;
    setGenerating(true);
    setSavedPath("");
    try {
      const result = await api.generateEmail(selectedUserId, properties);
      setEmail(result);
    } catch (err) {
      console.error("Failed to generate email", err);
    } finally {
      setGenerating(false);
    }
  }, [selectedUserId, properties]);

  // ── Save email ──────────────────────────────
  const handleSaveEmail = useCallback(async () => {
    if (!email || !selectedUserId) return;
    setSaving(true);
    try {
      const result = await api.saveEmail({
        user_id: selectedUserId,
        subject: email.subject,
        html: email.html,
        plain_text: email.plain_text,
        properties: properties.map((p) => ({
          property_id: p.property_id,
          recommendation_id: p.recommendation_id,
        })),
      });
      setSavedPath(result.path);

      // Optimistically update properties with today's campaign date
      const today = new Date().toISOString().split("T")[0];
      setProperties((prev) =>
        prev.map((p) => ({ ...p, campaign_sent_date: p.campaign_sent_date ?? today }))
      );
    } catch (err) {
      console.error("Failed to save email", err);
    } finally {
      setSaving(false);
    }
  }, [email, selectedUserId, properties]);

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Sidebar */}
      <Sidebar>
        <FilterPanel
          options={filterOptions}
          filters={filters}
          onChange={handleFilterChange}
          onSearch={handleSearchUsers}
          loading={usersLoading}
        />
      </Sidebar>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-7xl space-y-6">
          {/* User dropdown + profile */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <UserDropdown
                users={users}
                selectedId={selectedUserId}
                onSelect={handleSelectUser}
                loading={usersLoading}
              />
            </div>
            {userProfile && (
              <div>
                <UserProfileCard profile={userProfile} />
              </div>
            )}
          </div>

          {/* Property grid */}
          <div>
            <h2 className="mb-3 text-lg font-semibold text-gray-800">
              Top Recommended Listings
            </h2>
            <PropertyGrid properties={properties} loading={propsLoading} />
          </div>

          {/* Email actions + preview */}
          <div className="space-y-4">
            <EmailActions
              selectedUserId={selectedUserId}
              properties={properties}
              email={email}
              onGenerate={handleGenerateEmail}
              onSave={handleSaveEmail}
              generating={generating}
              saving={saving}
              savedPath={savedPath}
            />
            <EmailPreview
              email={email}
              properties={properties}
              onPropertyClick={(p) => setModalProperty(p)}
            />
          </div>
        </div>
      </main>

      {/* Property detail modal */}
      {modalProperty && (
        <PropertyDetailModal
          property={modalProperty}
          onClose={() => setModalProperty(null)}
        />
      )}
    </div>
  );
}
