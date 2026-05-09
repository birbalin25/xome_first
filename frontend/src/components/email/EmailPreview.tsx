import { useState, useRef, useEffect } from "react";
import type { GeneratedEmail, Property } from "../../types";

interface EmailPreviewProps {
  email: GeneratedEmail | null;
  properties: Property[];
  onPropertyClick: (property: Property) => void;
}

// Script injected into the iframe to intercept link clicks
const CLICK_INTERCEPTOR = `
<script>
document.addEventListener('click', function(e) {
  var link = e.target.closest('a');
  if (!link) return;
  e.preventDefault();
  e.stopPropagation();

  // Walk up from the link, stopping at the first ancestor with meaningful
  // context beyond just the button text (i.e. address, price, etc.).
  // This avoids overshooting into a parent that contains ALL properties.
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

export default function EmailPreview({ email, properties, onPropertyClick }: EmailPreviewProps) {
  const [tab, setTab] = useState<"html" | "plain">("html");
  const iframeRef = useRef<HTMLIFrameElement>(null);

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
      const context: string = e.data.context || "";

      // Match by address — if multiple properties match, pick the one whose
      // address appears latest in the context (closest to the button).
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
        // Fallback: try partial match on neighborhood or city
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

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      {/* Subject */}
      <div className="border-b border-gray-200 px-5 py-3">
        <span className="text-xs font-medium text-gray-500">Subject:</span>{" "}
        <span className="font-medium text-gray-900">{email.subject}</span>
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
          <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap p-4 text-sm text-gray-700">
            {email.plain_text}
          </pre>
        )}
      </div>
    </div>
  );
}
