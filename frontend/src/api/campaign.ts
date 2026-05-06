import type {
  FilterOptions,
  FilterState,
  GeneratedEmail,
  Property,
  UserProfile,
  UserSummary,
} from "../types";

const BASE = "/api/campaign";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

export async function fetchFilters(): Promise<FilterOptions> {
  const res = await fetch(`${BASE}/filters`);
  return json(res);
}

export async function searchUsers(
  filters: Partial<FilterState>
): Promise<UserSummary[]> {
  const res = await fetch(`${BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filters),
  });
  const data = await json<{ users: UserSummary[] }>(res);
  return data.users;
}

export async function fetchUserProfile(
  userId: string
): Promise<UserProfile> {
  const res = await fetch(`${BASE}/users/${userId}/profile`);
  return json(res);
}

export async function fetchListings(
  userId: string,
  filters?: { city?: string; state?: string; listing_count?: number }
): Promise<Property[]> {
  const res = await fetch(`${BASE}/users/${userId}/listings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filters ?? {}),
  });
  const data = await json<{ properties: Property[] }>(res);
  return data.properties;
}

export async function generateEmail(
  userId: string,
  properties: Property[]
): Promise<GeneratedEmail> {
  const res = await fetch(`${BASE}/generate-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, properties }),
  });
  return json(res);
}

export async function saveEmail(payload: {
  user_id: string;
  subject: string;
  html: string;
  plain_text: string;
  properties: Array<{ property_id: string; recommendation_id?: string }>;
}): Promise<{ path: string; filename: string }> {
  const res = await fetch(`${BASE}/save-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return json(res);
}
