"use client";
import { useEffect, useState } from "react";
import type { SourceDocument, ReturnLine } from "./workpaper-types";
import { evidenceRequest, evidenceButton } from "./evidence-types";
type Destinations = { direct_lines: ReturnLine[]; downstream_lines: ReturnLine[]; unused_evidence_ids: string[]; document_used_by_engine: boolean; document_superseded_by_engine: boolean; associated_findings: { id: string; code: string; title?: string; description?: string; message?: string; relationship: string; refs: string[] }[]; trace_scope: string };
type Extracted = { id: string; label: string; field: string; value: unknown; page: number };
export default function DocumentInspector({ document, version, onBack, onNavigate }: { document: SourceDocument; version: string; onBack: () => void; onNavigate: (ref: string) => void }) {
  const [trace, setTrace] = useState<Destinations | null>(null);
  const [fields, setFields] = useState<Extracted[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([evidenceRequest<Destinations>(`/api/documents/${document.id}/destinations?version=${version}`), evidenceRequest<{ values: Extracted[] }>(`/api/documents/${document.id}/evidence`)])
      .then(([destinations, evidence]) => { if (active) { setTrace(destinations); setFields(evidence.values); } }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [document.id, version]);
  return <div className="space-y-3" data-testid="document-inspector">
    <button className={evidenceButton} onClick={onBack}>← Back to evidence</button>
    <p className="text-xs font-bold text-indigo-600">{document.id}</p><h3 className="font-semibold">{document.title}</h3>
    {error && <p role="alert">{error}</p>}
    <details data-testid="document-destinations"><summary className="cursor-pointer text-sm font-semibold">Reverse document tracing</summary>
      {!trace && !error && <p>Loading destinations…</p>}
      {trace && <div className="mt-2 space-y-3 text-xs">
        <p>Engine used: {String(trace.document_used_by_engine)}; superseded: {String(trace.document_superseded_by_engine)}</p>
        {([['Direct calculations', trace.direct_lines], ['Indirect dependent calculations', trace.downstream_lines]] as const).map(([label, lines]) => <section key={label}><h4 className="font-semibold">{label} ({lines.length})</h4>{lines.length === 0 && <p>No supported links.</p>}<ul>{lines.map(line => <li key={line.key}><button className="py-1 text-left text-indigo-700 underline" onClick={() => onNavigate(line.key)}>{line.key} · {line.label}</button></li>)}</ul></section>)}
        <section><h4 className="font-semibold">Associated findings ({trace.associated_findings.length})</h4>{trace.associated_findings.map(finding => <div className="mt-2 rounded bg-slate-50 p-2" key={finding.id}><p>{finding.title ?? finding.code} · {finding.relationship}</p><p>{finding.description ?? finding.message}</p><div className="flex flex-wrap gap-1">{finding.refs.map(ref => <button key={ref} className="text-indigo-700 underline" onClick={() => onNavigate(ref)}>{ref}</button>)}</div></div>)}</section>
        <p>{trace.unused_evidence_ids.length} extracted fields lack a direct source link. This does not establish irrelevance.</p><p className="text-slate-500">{trace.trace_scope}</p>
      </div>}
    </details>
    <details><summary className="cursor-pointer text-sm font-semibold">Extracted fields ({fields.length})</summary><ul className="max-h-96 overflow-auto">{fields.map(field => <li key={field.id}><button className="my-1 text-left text-xs text-indigo-700 underline" onClick={() => onNavigate(field.id)}>{field.id} · {field.field} · {field.label} · {String(field.value ?? "—")} · page {field.page}</button></li>)}</ul></details>
    {(document.pages ?? []).map(page => <div key={page.page} className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="mb-3 text-xs font-semibold text-slate-400">PAGE {page.page}</p><p className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-700">{page.printed_content}</p></div>)}
  </div>;
}
