import { Loader2, MessageSquarePlus, Search, X } from "lucide-react";
import { useState } from "react";

interface GenieSearchBarProps {
  onSubmit: (query: string) => void;
  loading: boolean;
  conversationId: string | null;
  onNewSearch: () => void;
  error?: string;
}

export default function GenieSearchBar({
  onSubmit,
  loading,
  conversationId,
  onNewSearch,
  error,
}: GenieSearchBarProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = () => {
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    onSubmit(trimmed);
    setQuery("");
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder="Ask Genie to find users... e.g. 'Show me investors in Miami'"
            disabled={loading}
            className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-sm shadow-sm transition placeholder:text-gray-400 focus:border-xome-500 focus:outline-none focus:ring-1 focus:ring-xome-500 disabled:opacity-50"
          />
        </div>

        <button
          onClick={handleSubmit}
          disabled={loading || !query.trim()}
          className="flex items-center gap-2 rounded-lg bg-xome-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-xome-700 disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          {loading ? "Querying..." : "Search"}
        </button>

        {conversationId && (
          <button
            onClick={onNewSearch}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm font-medium text-gray-600 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
          >
            <X className="h-3.5 w-3.5" />
            New Search
          </button>
        )}
      </div>

      {/* Follow-up badge */}
      {conversationId && !loading && (
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <MessageSquarePlus className="h-3.5 w-3.5" />
          <span>Follow-up mode — refine your previous query or start a new search</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}
