"use client";
import { useEffect, useState } from "react";
import {
  EvidenceGraph,
  evidenceRequest,
  evidenceControl,
  evidenceButton,
} from "./evidence-types";

export default function EvidenceResolver({
  reference = "",
  version,
  onNavigate,
}: {
  reference?: string;
  version: string;
  onNavigate: (ref: string) => void;
}) {
  const [input, setInput] = useState(reference);
  const [graph, setGraph] = useState<EvidenceGraph | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let active = true;
    if (reference) {
      evidenceRequest<EvidenceGraph>(
        `/api/evidence-graph?ref=${encodeURIComponent(reference)}&version=${version}`,
      )
        .then((result) => {
          if (active) setGraph(result);
        })
        .catch((err) => {
          if (active) setError(err.message);
        });
    }
    return () => {
      active = false;
    };
  }, [reference, version]);
  async function resolve() {
    setLoading(true);
    setError("");
    setGraph(null);
    try {
      setGraph(
        await evidenceRequest<EvidenceGraph>(
          `/api/evidence-graph?ref=${encodeURIComponent(input)}&version=${version}`,
        ),
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to resolve evidence",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="space-y-3 p-3" data-testid="evidence-resolver">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void resolve();
        }}
        className="space-y-2"
      >
        <label className="block text-sm">
          Evidence reference
          <input
            aria-label="Evidence reference"
            className={evidenceControl}
            required
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="py:/carryovers_into_2025/capital_loss_short"
          />
        </label>
        <button className={evidenceButton} disabled={loading} type="submit">
          Resolve evidence
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {graph && (
        <>
          <p className="text-sm font-semibold" data-testid="resolution-status">
            {graph.resolution.status} · {graph.resolution.type}
          </p>
          <p className="text-sm">{graph.resolution.label}</p>
          <p className="text-xs">
            {graph.resolution.reason}
            {graph.resolution.reason_code &&
              ` (${graph.resolution.reason_code})`}
          </p>
          <p className="break-all text-xs text-slate-500">
            {graph.resolution.location}
          </p>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-xs">
            {JSON.stringify(graph.resolution.value, null, 2)}
          </pre>
          <div className="flex flex-wrap gap-2">
            {graph.resolution.related_refs.map((ref) => (
              <button
                key={ref}
                className={evidenceButton}
                onClick={() => onNavigate(ref)}
              >
                {ref}
              </button>
            ))}
          </div>
          {graph.document_ids.length > 0 && (
            <div>
              <p className="text-xs font-semibold">Supporting documents</p>
              {graph.document_ids.map((id) => (
                <button
                  key={id}
                  className={evidenceButton}
                  onClick={() => onNavigate(id)}
                >
                  Open {id}
                </button>
              ))}
            </div>
          )}
          {graph.unresolved.length > 0 && (
            <div className="rounded bg-amber-50 p-3">
              <p className="text-sm font-semibold">Unresolved references</p>
              {graph.unresolved.map((node) => (
                <p key={node.ref} className="break-all text-xs">
                  {node.ref}: {node.reason} ({node.reason_code})
                </p>
              ))}
            </div>
          )}
          {graph.cycles.length > 0 && (
            <p className="text-xs text-amber-800">
              Cycles detected:{" "}
              {graph.cycles.map((c) => `${c.from} → ${c.to}`).join(", ")}
            </p>
          )}
        </>
      )}
    </div>
  );
}
