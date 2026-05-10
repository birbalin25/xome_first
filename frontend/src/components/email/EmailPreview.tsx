import { useState, useRef, useEffect } from "react";
import { Loader2, Sparkles, X } from "lucide-react";
import type { GeneratedEmail, PastEmail, Property } from "../../types";

interface EmailPreviewProps {
  email: GeneratedEmail | null;
  properties: Property[];
  onPropertyClick: (property: Property) => void;
  pastEmails?: PastEmail[];
  onUpdatePlainText?: (text: string) => void;
  onRefineWithAI?: (
    subject: string,
    plainText: string,
    prompt: string,
    previousEmail?: { subject: string; plain_text: string; saved_at?: string } | null
  ) => Promise<{ subject: string; plain_text: string }>;
  onUpdateSubject?: (subject: string) => void;
}

// Script injected into the iframe to intercept link clicks
const CLICK_INTERCEPTOR = `
<script>
document.addEventListener('click', function(e) {
  var link = e.target.closest('a');
  if (!link) return;
  e.preventDefault();
  e.stopPropagation();

  var href = link.getAttribute('href') || '';

  // Check for #property:{id} format first
  var match = href.match(/^#property:(.+)$/);
  if (match) {
    window.parent.postMessage({
      type: 'xome-property-click',
      propertyId: match[1]
    }, '*');
    return;
  }

  // Fallback: walk up the DOM for context text
  var linkText = link.innerText || '';
  var contextText = '';
  var node = link.parentElement;

  for (var i = 0; i < 8 && node && node !== document.body; i++) {
    var text = node.innerText || '';
    if (text.length > linkText.length + 30) {
      contextText = text;
      break;
    }
    node = node.parentElement;
  }

  if (!contextText && node) {
    contextText = node.innerText || '';
  }

  window.parent.postMessage({
    type: 'xome-property-click',
    context: contextText,
    linkText: linkText
  }, '*');
});
</script>
`;

export default function EmailPreview({
  email,
  properties,
  onPropertyClick,
  pastEmails = [],
  onUpdatePlainText,
  onRefineWithAI,
  onUpdateSubject,
}: EmailPreviewProps) {
  const [tab, setTab] = useState<"html" | "plain">("html");
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState("");
  const [viewingPast, setViewingPast] = useState(false);
  const [viewingPastText, setViewingPastText] = useState("");
  const [draftSubject, setDraftSubject] = useState("");
  const [showRefineBar, setShowRefineBar] = useState(false);
  const [refinePrompt, setRefinePrompt] = useState("");
  const [refining, setRefining] = useState(false);

  // Reset editing/viewing state when email changes (new generation)
  useEffect(() => {
    setEditing(false);
    setViewingPast(false);
    setViewingPastText("");
    setDraftSubject("");
    setShowRefineBar(false);
    setRefinePrompt("");
    setRefining(false);
  }, [email]);

  // Write HTML into the iframe with click interceptor
  useEffect(() => {
    if (tab === "html" && iframeRef.current && email?.html) {
      const doc = iframeRef.current.contentDocument;
      if (doc) {
        doc.open();
        doc.write(email.html + CLICK_INTERCEPTOR);
        doc.close();
      }
    }
  }, [tab, email?.html]);

  // Listen for postMessage from iframe and match to a property
  useEffect(() => {
    function handleMessage(e: MessageEvent) {
      if (e.data?.type !== "xome-property-click") return;

      // Exact match by property_id from href="#property:{id}"
      if (e.data.propertyId) {
        const exact = properties.find((p) => p.property_id === e.data.propertyId);
        if (exact) {
          onPropertyClick(exact);
          return;
        }
      }

      // Fallback: match by address in context text
      const context: string = e.data.context || "";
      let bestMatch: Property | null = null;
      let bestPos = -1;
      for (const p of properties) {
        const pos = context.lastIndexOf(p.address);
        if (pos !== -1 && pos > bestPos) {
          bestPos = pos;
          bestMatch = p;
        }
      }

      if (bestMatch) {
        onPropertyClick(bestMatch);
      } else {
        const fallback = properties.find(
          (p) => context.includes(p.neighborhood) || context.includes(p.city)
        );
        if (fallback) onPropertyClick(fallback);
      }
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [properties, onPropertyClick]);

  if (!email) return null;

  const handleDropdownChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (value === "") return; // "Load past email..." placeholder
    if (value === "__current__") {
      // Go back to current email view
      setViewingPast(false);
      setViewingPastText("");
      setEditing(false);
    } else {
      const idx = parseInt(value, 10);
      const past = pastEmails[idx];
      if (past) {
        setViewingPast(true);
        setViewingPastText(past.plain_text);
        setEditing(false);
      }
    }
  };

  const handleEdit = () => {
    setDraftText(email.plain_text);
    setDraftSubject(email.subject);
    setEditing(true);
  };

  const handleSave = () => {
    if (onUpdatePlainText) {
      onUpdatePlainText(draftText);
    }
    if (onUpdateSubject && draftSubject !== email.subject) {
      onUpdateSubject(draftSubject);
    }
    setEditing(false);
    setShowRefineBar(false);
    setRefinePrompt("");
  };

  const handleCancel = () => {
    setEditing(false);
    setDraftSubject("");
    setShowRefineBar(false);
    setRefinePrompt("");
  };

  const handleApplyRefine = async () => {
    if (!onRefineWithAI || !email || !refinePrompt.trim()) return;
    setRefining(true);
    try {
      const recentPast = pastEmails.length > 0
        ? { subject: pastEmails[0].subject, plain_text: pastEmails[0].plain_text, saved_at: pastEmails[0].saved_at }
        : null;
      const result = await onRefineWithAI(
        draftSubject,
        draftText,
        refinePrompt.trim(),
        recentPast
      );
      setDraftText(result.plain_text);
      setDraftSubject(result.subject);
      setRefinePrompt("");
      setShowRefineBar(false);
    } catch (err) {
      console.error("Failed to refine email", err);
    } finally {
      setRefining(false);
    }
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      {/* Subject */}
      <div className="border-b border-gray-200 px-5 py-3">
        <span className="text-xs font-medium text-gray-500">Subject:</span>{" "}
        {editing ? (
          <input
            type="text"
            value={draftSubject}
            onChange={(e) => setDraftSubject(e.target.value)}
            className="ml-1 inline-block w-[calc(100%-60px)] rounded border border-gray-300 px-2 py-0.5 text-sm font-medium text-gray-900 focus:border-xome-500 focus:outline-none focus:ring-1 focus:ring-xome-500"
          />
        ) : (
          <span className="font-medium text-gray-900">{email.subject}</span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setTab("html")}
          className={`px-5 py-2.5 text-sm font-medium transition ${
            tab === "html"
              ? "border-b-2 border-xome-600 text-xome-700"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          HTML Preview
        </button>
        <button
          onClick={() => setTab("plain")}
          className={`px-5 py-2.5 text-sm font-medium transition ${
            tab === "plain"
              ? "border-b-2 border-xome-600 text-xome-700"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Plain Text
        </button>
      </div>

      {/* Content */}
      <div className="p-1">
        {tab === "html" ? (
          <iframe
            ref={iframeRef}
            title="Email preview"
            className="h-[500px] w-full border-0"
            sandbox="allow-same-origin allow-scripts"
          />
        ) : (
          <div>
            {/* Toolbar */}
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2">
              <select
                onChange={handleDropdownChange}
                defaultValue=""
                className="rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 focus:border-xome-500 focus:outline-none focus:ring-1 focus:ring-xome-500"
              >
                <option value="" disabled>
                  Load past email...
                </option>
                <option value="__current__">Current email</option>
                {pastEmails.map((pe, i) => (
                  <option key={i} value={i}>
                    email_sent_on_{pe.saved_at.replace(/[: ]/g, "_")}
                  </option>
                ))}
              </select>
              {!viewingPast && (
                <div className="flex gap-2">
                  {editing ? (
                    <>
                      {onRefineWithAI && (
                        <button
                          onClick={() => setShowRefineBar((v) => !v)}
                          className="flex items-center gap-1 rounded bg-gradient-to-r from-purple-600 to-indigo-600 px-3 py-1 text-xs font-medium text-white transition hover:from-purple-700 hover:to-indigo-700"
                        >
                          <Sparkles className="h-3 w-3" />
                          Refine with AI
                        </button>
                      )}
                      <button
                        onClick={handleCancel}
                        className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-600 transition hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSave}
                        className="rounded bg-xome-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-xome-700"
                      >
                        Save
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={handleEdit}
                      className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-600 transition hover:bg-gray-50"
                    >
                      Edit
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Refine with AI prompt bar */}
            {editing && showRefineBar && (
              <div className="flex items-center gap-2 border-b border-gray-100 bg-purple-50 px-4 py-2">
                <input
                  type="text"
                  value={refinePrompt}
                  onChange={(e) => setRefinePrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !refining) handleApplyRefine();
                  }}
                  placeholder="e.g. make it shorter and more urgent"
                  className="flex-1 rounded border border-purple-200 bg-white px-3 py-1.5 text-sm text-gray-700 placeholder-gray-400 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                  disabled={refining}
                />
                <button
                  onClick={handleApplyRefine}
                  disabled={refining || !refinePrompt.trim()}
                  className="flex items-center gap-1.5 rounded bg-purple-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-purple-700 disabled:opacity-50"
                >
                  {refining && <Loader2 className="h-3 w-3 animate-spin" />}
                  {refining ? "Refining..." : "Apply"}
                </button>
                <button
                  onClick={() => {
                    setShowRefineBar(false);
                    setRefinePrompt("");
                  }}
                  className="rounded p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            {/* Text area (editing current) or read-only pre */}
            {viewingPast ? (
              <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap p-4 text-sm text-gray-500 bg-gray-50">
                {viewingPastText}
              </pre>
            ) : editing ? (
              <textarea
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                className="h-[500px] w-full resize-none p-4 text-sm text-gray-700 font-mono focus:outline-none"
              />
            ) : (
              <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap p-4 text-sm text-gray-700">
                {email.plain_text}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
