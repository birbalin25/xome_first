import { useEffect, useState } from "react";
import type { GenieColumn } from "../../types";

interface GenieResultTableProps {
  columns: GenieColumn[];
  rows: (string | null)[][];
  description: string;
  onViewRecommendations: (userIds: string[], model: string) => void;
  onSelectProperty: (propertyId: string) => void;
}

/** Column names (case-insensitive) treated as user id columns. */
const USER_ID_NAMES = new Set(["user_id", "userid"]);

/** Column names (case-insensitive) treated as clickable property links. */
const PROPERTY_ID_NAMES = new Set(["property_id", "propertyid"]);

const MODEL_OPTIONS = ["Model A", "Model B", "On-the-fly-logic"] as const;

export default function GenieResultTable({
  columns,
  rows,
  description,
  onViewRecommendations,
  onSelectProperty,
}: GenieResultTableProps) {
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());
  const [model, setModel] = useState<string>(MODEL_OPTIONS[0]);

  // Reset selection when rows change
  useEffect(() => {
    setSelectedUserIds(new Set());
  }, [rows]);

  if (columns.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border-2 border-dashed border-gray-200 text-gray-400">
        Use the search bar above to find users with Genie
      </div>
    );
  }

  // Detect user_id and property_id column indices
  const userIdColIndex = columns.findIndex((c) =>
    USER_ID_NAMES.has(c.name.toLowerCase())
  );
  const propertyIdColIndex = columns.findIndex((c) =>
    PROPERTY_ID_NAMES.has(c.name.toLowerCase())
  );

  const hasUserIdColumn = userIdColIndex >= 0;

  // Collect all non-null user IDs for select-all
  const allUserIds: string[] = hasUserIdColumn
    ? rows.map((r) => r[userIdColIndex]).filter((v): v is string => v != null)
    : [];

  const allSelected = allUserIds.length > 0 && selectedUserIds.size === allUserIds.length;
  const someSelected = selectedUserIds.size > 0 && selectedUserIds.size < allUserIds.length;

  const toggleUser = (userId: string) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const toggleAll = () => {
    if (allSelected) {
      setSelectedUserIds(new Set());
    } else {
      setSelectedUserIds(new Set(allUserIds));
    }
  };

  return (
    <div className="space-y-3">
      {/* Genie description */}
      {description && (
        <p className="text-sm text-gray-600">{description}</p>
      )}

      {/* Result count */}
      <div className="text-sm text-gray-500">
        {rows.length} {rows.length === 1 ? "row" : "rows"} returned
      </div>

      {rows.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-gray-200 text-gray-400">
          No results
        </div>
      ) : (
        <div className="overflow-auto rounded-lg border border-gray-200" style={{ maxHeight: "calc(12 * 37px + 37px)" }}>
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 z-10 bg-gray-50">
              <tr>
                {hasUserIdColumn && (
                  <th className="border-b border-gray-200 px-3 py-2">
                    <div className="flex items-center gap-2 whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        ref={(el) => {
                          if (el) el.indeterminate = someSelected;
                        }}
                        onChange={toggleAll}
                        className="h-4 w-4 cursor-pointer rounded border-gray-300 text-xome-600 accent-xome-600"
                      />
                      <button
                        onClick={() => setSelectedUserIds(new Set(allUserIds))}
                        className="text-xs font-medium text-blue-600 hover:text-blue-800"
                      >
                        Select All
                      </button>
                      <span className="text-xs text-gray-300">|</span>
                      <button
                        onClick={() => setSelectedUserIds(new Set())}
                        className="text-xs font-medium text-blue-600 hover:text-blue-800"
                      >
                        Unselect All
                      </button>
                    </div>
                  </th>
                )}
                {columns.map((col) => (
                  <th
                    key={col.name}
                    className="whitespace-nowrap border-b border-gray-200 px-4 py-2 text-left font-semibold text-gray-700"
                  >
                    {col.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => {
                const userId = hasUserIdColumn ? row[userIdColIndex] : null;
                const isChecked = userId ? selectedUserIds.has(userId) : false;

                return (
                  <tr
                    key={ri}
                    className={ri % 2 === 0 ? "bg-white" : "bg-gray-50"}
                  >
                    {hasUserIdColumn && (
                      <td className="border-b border-gray-100 px-3 py-2 text-center">
                        {userId && (
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleUser(userId)}
                            className="h-4 w-4 rounded border-gray-300 text-xome-600 accent-xome-600"
                          />
                        )}
                      </td>
                    )}
                    {row.map((cell, ci) => (
                      <td
                        key={ci}
                        className="whitespace-nowrap border-b border-gray-100 px-4 py-2 text-gray-800"
                      >
                        {/* Property links only when no user_id column */}
                        {ci === propertyIdColIndex && !hasUserIdColumn && cell ? (
                          <button
                            onClick={() => onSelectProperty(cell)}
                            className="text-blue-600 underline hover:text-blue-800"
                          >
                            {cell}
                          </button>
                        ) : (
                          (cell ?? "")
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Action bar — visible when user_id column exists */}
      {hasUserIdColumn && rows.length > 0 && (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
          <span className="text-sm font-medium text-gray-700">
            {selectedUserIds.size} user{selectedUserIds.size !== 1 ? "s" : ""} selected
          </span>

          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm focus:border-xome-500 focus:outline-none focus:ring-1 focus:ring-xome-500"
          >
            {MODEL_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>

          <button
            onClick={() =>
              onViewRecommendations(Array.from(selectedUserIds), model)
            }
            disabled={selectedUserIds.size === 0}
            className="rounded-md bg-xome-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-xome-700 disabled:opacity-50"
          >
            View Recommended Properties
          </button>
        </div>
      )}
    </div>
  );
}
