import type { GenieColumn } from "../../types";

interface GenieResultTableProps {
  columns: GenieColumn[];
  rows: (string | null)[][];
  description: string;
  onSelectUser: (userId: string) => void;
  onSelectProperty: (propertyId: string) => void;
}

/** Column names (case-insensitive) treated as clickable user links. */
const USER_ID_NAMES = new Set(["user_id", "userid"]);

/** Column names (case-insensitive) treated as clickable property links. */
const PROPERTY_ID_NAMES = new Set(["property_id", "propertyid"]);

export default function GenieResultTable({
  columns,
  rows,
  description,
  onSelectUser,
  onSelectProperty,
}: GenieResultTableProps) {
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
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-gray-50">
              <tr>
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
              {rows.map((row, ri) => (
                <tr
                  key={ri}
                  className={ri % 2 === 0 ? "bg-white" : "bg-gray-50"}
                >
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className="whitespace-nowrap border-b border-gray-100 px-4 py-2 text-gray-800"
                    >
                      {ci === userIdColIndex && cell ? (
                        <button
                          onClick={() => onSelectUser(cell)}
                          className="text-blue-600 underline hover:text-blue-800"
                        >
                          {cell}
                        </button>
                      ) : ci === propertyIdColIndex && cell ? (
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
