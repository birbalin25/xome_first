import { Send, Mail, Loader2, Check } from "lucide-react";
import type { GeneratedEmail } from "../../types";

interface EmailActionsProps {
  selectedUserId: string;
  properties: { length: number };
  email: GeneratedEmail | null;
  onGenerate: () => void;
  onSave: () => void;
  generating: boolean;
  saving: boolean;
  savedPath: string;
}

export default function EmailActions({
  selectedUserId,
  properties,
  email,
  onGenerate,
  onSave,
  generating,
  saving,
  savedPath,
}: EmailActionsProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        onClick={onGenerate}
        disabled={!selectedUserId || properties.length === 0 || generating}
        className="flex items-center gap-2 rounded-md bg-xome-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-xome-700 disabled:opacity-50"
      >
        {generating ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Mail className="h-4 w-4" />
        )}
        {generating ? "Generating..." : "Generate Email"}
      </button>

      <button
        onClick={onSave}
        disabled={!email || saving}
        className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
      >
        {saving ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : savedPath ? (
          <Check className="h-4 w-4 text-green-600" />
        ) : (
          <Send className="h-4 w-4" />
        )}
        {saving ? "Sending..." : savedPath ? "Sent" : "Send Email"}
      </button>

      {savedPath && (
        <span className="text-xs text-gray-500">
          Sent: <code className="rounded bg-gray-100 px-1.5 py-0.5">{savedPath}</code>
        </span>
      )}
    </div>
  );
}
