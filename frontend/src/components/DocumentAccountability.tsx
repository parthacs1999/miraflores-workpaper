"use client";
import { useEffect, useState } from "react";
import { Resolution, evidenceRequest, evidenceControl, evidenceButton } from "./evidence-types";
type DocumentAccount = { id: string; title: string; dispositions: string[]; extraction_status: string; extracted_values: number; reasons: { disposition: string; reason: string; refs: string[] }[]; duplicate_pages: { page: number; duplicate_of_page: number; reason: string }[] };
type Accountability = { total: number; counts: Record<string, number>; documents: DocumentAccount[]; note: string; unresolved_provenance: Resolution[] };
export default function DocumentAccountability({ version, onOpenDocument, onNavigate }: { version: string; onOpenDocument: (id: string) => void; onNavigate: (ref: string) => void }) {
  const [data, setData] = useState<Accountability | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  useEffect(() => {
    let active = true;
    evidenceRequest<Accountability>(`/api/document-accountability?version=${version}`).then(result => { if (active) setData(result); }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [version]);
  return <div className="space-y-4 p-5" data-testid="document-accountability">
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p>Loading document accountability…</p>}
    {data && <>
      <p className="font-semibold">{data.total} documents accounted for</p><p className="text-xs text-slate-500">{data.note}</p>
      <div className="flex flex-wrap gap-2">{Object.entries(data.counts).map(([state, count]) => <span className="rounded bg-slate-100 p-2 text-xs" key={state}>{state}: {count}</span>)}</div>
      <label className="block text-sm">Document disposition<select aria-label="Document disposition" className={evidenceControl} value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All dispositions</option>{Object.keys(data.counts).map(state => <option key={state} value={state}>{state}</option>)}</select></label>
      <input aria-label="Accountability document search" className={evidenceControl} placeholder="Search documents or IDs" value={search} onChange={e => setSearch(e.target.value)} />
      <ul className="max-h-[720px] space-y-3 overflow-auto">{data.documents.filter(d => (filter === "all" || d.dispositions.includes(filter)) && `${d.id} ${d.title}`.toLowerCase().includes(search.toLowerCase())).map(d => <li key={d.id} className="rounded-xl border border-slate-200 p-3" data-testid={`accountability-${d.id}`}>
        <button className={evidenceButton} onClick={() => onOpenDocument(d.id)}>Inspect {d.id} document</button><p className="mt-2 text-sm font-medium">{d.title}</p>
        <p className="mt-1 text-xs font-semibold">{d.dispositions.join(" · ")}</p><p className="text-xs">Extraction: {d.extraction_status}; {d.extracted_values} extracted fields</p>
        <ul className="mt-2 space-y-1">{d.reasons.map((reason, index) => <li key={index} className="text-xs text-slate-600">{reason.disposition}: {reason.reason}<div className="flex flex-wrap gap-1">{reason.refs.map(ref => <button key={ref} className="text-indigo-700 underline" onClick={() => onNavigate(ref)}>{ref}</button>)}</div></li>)}</ul>
        {d.duplicate_pages.map(page => <p key={page.page} className="mt-1 text-xs text-amber-800">Page {page.page} duplicates page {page.duplicate_of_page}; review the page, not the whole document as a duplicate.</p>)}
      </li>)}</ul>
      {data.unresolved_provenance.length > 0 && <details><summary className="text-sm">Unresolved packet provenance ({data.unresolved_provenance.length})</summary>{data.unresolved_provenance.map(r => <button className={`${evidenceButton} m-1 break-all`} key={r.ref} onClick={() => onNavigate(r.ref)}>{r.ref}: {r.reason}</button>)}</details>}
    </>}
  </div>;
}
