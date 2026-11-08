"use client";
import { useWorkpaperIdentity } from "@/components/session";
import { useEffect, useState } from "react";
import {
  Resolution,
  VerificationHistory,
  evidenceRequest,
  evidenceControl,
  evidenceButton,
} from "./evidence-types";
type Metadata = {
  methods: string[];
  staff: {
    id: string;
    name: string;
    role: string;
    credential: string | null;
    active_from: string;
  }[];
};
type Automatic = {
  document_id: string | null;
  page: number | null;
  text_as_read: string | null;
  extracted_value: unknown;
  match: { matched_text: string; start: number; end: number } | null;
};

function pageText(source: Resolution | null): string {
  const value = source?.value;
  return value &&
    typeof value === "object" &&
    "printed_content" in value &&
    typeof value.printed_content === "string"
    ? value.printed_content
    : "";
}
export default function FieldVerification({
  evidenceId,
  version,
  automatic,
}: {
  evidenceId: string;
  version: string;
  automatic: Automatic;
}) {
  const initialRef =
    automatic.document_id && automatic.page
      ? `doc:${automatic.document_id}#page${automatic.page}`
      : "";
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [history, setHistory] = useState<VerificationHistory | null>(null);
  const [source, setSource] = useState<Resolution | null>(null);
  const [sourceRef, setSourceRef] = useState(initialRef);
  const [quoteText, setQuoteText] = useState(
    automatic.match?.matched_text ??
      automatic.text_as_read ??
      String(automatic.extracted_value ?? ""),
  );
  const [quoteStart, setQuoteStart] = useState("");
  const identity = useWorkpaperIdentity();
  const [legacyActor, setVerifier] = useState("st-02");
  const verifier = identity?.id ?? legacyActor;
  const [method, setMethod] = useState("agreed_to_source_document");
  const [status, setStatus] = useState("confirmed");
  const [notes, setNotes] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    Promise.all([
      evidenceRequest<Metadata>("/api/verification-metadata"),
      evidenceRequest<VerificationHistory>(
        `/api/field-verifications/${evidenceId}?version=${version}`,
      ),
      evidenceRequest<Resolution>(
        `/api/evidence-resolution?ref=${encodeURIComponent(initialRef)}&version=${version}`,
      ),
    ])
      .then(([meta, audit, resolution]) => {
        if (active) {
          setMetadata(meta);
          setHistory(audit);
          setSource(resolution);
        }
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [evidenceId, version, initialRef]);
  const content = pageText(source);
  const locations: number[] = [];
  if (content && quoteText.trim()) {
    for (
      let start = content.indexOf(quoteText);
      start >= 0;
      start = content.indexOf(quoteText, start + Math.max(1, quoteText.length))
    )
      locations.push(start);
  }
  const isPage = source?.type === "document_page";
  async function loadSource() {
    setBusy(true);
    setError("");
    setQuoteStart("");
    setReviewed(false);
    try {
      setSource(
        await evidenceRequest<Resolution>(
          `/api/evidence-resolution?ref=${encodeURIComponent(sourceRef)}&version=${version}`,
        ),
      );
    } catch (err) {
      setSource(null);
      setError(err instanceof Error ? err.message : "Unable to resolve source");
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    if (!history || !source) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await evidenceRequest(
        `/api/field-verifications/${evidenceId}?version=${version}`,
        {
          verifier_id: verifier,
          method,
          source_ref: sourceRef,
          status,
          notes,
          expected_sequence: history.sequence,
          quote: isPage
            ? {
                start: Number(quoteStart),
                end: Number(quoteStart) + quoteText.length,
                text: quoteText,
              }
            : null,
        },
      );
      setHistory(
        await evidenceRequest<VerificationHistory>(
          `/api/field-verifications/${evidenceId}?version=${version}`,
        ),
      );
      setMessage("Field verification recorded.");
      setReviewed(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to record verification",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="space-y-3 rounded-xl border border-indigo-200 p-3"
      data-testid="field-verification"
    >
      <h4 className="text-sm font-semibold">Human field verification</h4>
      <p className="text-xs text-slate-500">
        Separate from automatic matching. Staff IDs are selected demonstration
        identities, not authenticated login.
      </p>
      {history && (
        <p className="text-sm" data-testid="human-verification-status">
          {history.latest
            ? `${history.latest.status} · ${history.latest.assurance} · ${history.latest.verifier_id}${history.latest.stale ? " · stale packet" : ""}`
            : "No human verification recorded"}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-800">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="text-sm text-green-800">
          {message}
        </p>
      )}
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <label className="block text-xs">
          Field verifier
          <select
            aria-label="Field verifier"
            className={evidenceControl}
            value={verifier}
            disabled={!!identity || busy}
            onChange={(e) => setVerifier(e.target.value)}
          >
            {metadata?.staff
              .filter(
                (s) =>
                  ["preparer", "reviewer", "partner"].includes(s.role) &&
                  s.active_from <= new Date().toISOString().slice(0, 10),
              )
              .map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name} · {s.credential ?? "staff"} · {s.id}
                </option>
              ))}
          </select>
        </label>
        <label className="block text-xs">
          Verification method
          <select
            aria-label="Field verification method"
            className={evidenceControl}
            value={method}
            onChange={(e) => {
              setMethod(e.target.value);
              setReviewed(false);
            }}
          >
            {metadata?.methods.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs">
          Verification source reference
          <input
            aria-label="Verification source reference"
            className={evidenceControl}
            value={sourceRef}
            required
            onChange={(e) => {
              setSourceRef(e.target.value);
              setReviewed(false);
            }}
          />
        </label>
        <button
          className={evidenceButton}
          type="button"
          disabled={busy}
          onClick={() => void loadSource()}
        >
          Load verification source
        </button>
        {source && (
          <>
            <p className="text-xs">
              Source: {source.status} · {source.type} · {source.reason}
            </p>
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words bg-slate-50 p-2 text-xs">
              {content || JSON.stringify(source.value, null, 2)}
            </pre>
          </>
        )}
        {isPage && (
          <>
            <label className="block text-xs">
              Source text to locate
              <input
                aria-label="Source text to locate"
                className={evidenceControl}
                required
                value={quoteText}
                onChange={(e) => {
                  setQuoteText(e.target.value);
                  setQuoteStart("");
                  setReviewed(false);
                }}
              />
            </label>
            <label className="block text-xs">
              Specific source location
              <select
                aria-label="Specific source location"
                className={evidenceControl}
                required
                value={quoteStart}
                onChange={(e) => {
                  setQuoteStart(e.target.value);
                  setReviewed(false);
                }}
              >
                <option value="">Select the reviewed field location</option>
                {locations.map((start) => (
                  <option key={start} value={String(start)}>
                    Offset {start}:{" "}
                    {content.slice(
                      Math.max(0, start - 45),
                      Math.min(content.length, start + quoteText.length + 25),
                    )}
                  </option>
                ))}
              </select>
            </label>
            {locations.length > 1 && (
              <p className="text-xs text-amber-800">
                Identical text occurs {locations.length} times. Select the
                specific field after reviewing its context.
              </p>
            )}
            {quoteStart !== "" && (
              <p className="text-xs">
                Selected source:{" "}
                {content.slice(
                  Math.max(0, Number(quoteStart) - 50),
                  Number(quoteStart),
                )}
                <mark
                  data-testid="human-source-highlight"
                  className="bg-indigo-100"
                >
                  {quoteText}
                </mark>
                {content.slice(
                  Number(quoteStart) + quoteText.length,
                  Number(quoteStart) + quoteText.length + 50,
                )}
              </p>
            )}
          </>
        )}
        <label className="block text-xs">
          Verification outcome
          <select
            aria-label="Verification outcome"
            className={evidenceControl}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="confirmed">Confirmed</option>
            <option value="needs_review">Needs review</option>
            <option value="revoked">Revoke previous attestation</option>
          </select>
        </label>
        <label className="block text-xs">
          Verification notes
          <textarea
            aria-label="Field verification notes"
            required
            maxLength={4000}
            className={evidenceControl}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
        <label className="flex gap-2 text-xs">
          <input
            aria-label="I reviewed the specific field and source"
            type="checkbox"
            checked={reviewed}
            onChange={(e) => setReviewed(e.target.checked)}
          />
          I reviewed the specific field and source.
        </label>
        <button
          className={evidenceButton}
          disabled={
            busy ||
            !metadata ||
            !history ||
            !reviewed ||
            !notes.trim() ||
            source?.status !== "resolved" ||
            source.ref !== sourceRef ||
            (isPage && quoteStart === "")
          }
          type="submit"
        >
          Record field verification
        </button>
      </form>
      <h5 className="text-sm font-semibold">Verification audit history</h5>
      <ol className="space-y-2" data-testid="field-verification-history">
        {history?.events.map((event) => (
          <li key={event.id} className="rounded bg-slate-50 p-2 text-xs">
            <p>
              #{event.sequence} · {event.status} · {event.verifier_id} ·{" "}
              {event.assurance} · {event.method}
            </p>
            <p>
              {event.source_ref} · {event.created_at}
            </p>
            <p>{event.notes}</p>
            {event.snapshot.quote && (
              <p>
                Source offsets {event.snapshot.quote.start}–
                {event.snapshot.quote.end}: {event.snapshot.quote.text}
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
