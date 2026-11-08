"use client";
import { StatusBadge } from "./ui/primitives";
import { useEffect, useState } from "react";
import {
  Resolution,
  evidenceRequest,
  evidenceControl,
  evidenceButton,
} from "./evidence-types";
type DocumentAccount = {
  id: string;
  title: string;
  dispositions: string[];
  extraction_status: string;
  extracted_values: number;
  reasons: { disposition: string; reason: string; refs: string[] }[];
  duplicate_pages: {
    page: number;
    duplicate_of_page: number;
    reason: string;
  }[];
};
type Accountability = {
  total: number;
  counts: Record<string, number>;
  documents: DocumentAccount[];
  note: string;
  unresolved_provenance: Resolution[];
};
export default function DocumentAccountability({
  version,
  onOpenDocument,
  onNavigate,
}: {
  version: string;
  onOpenDocument: (id: string) => void;
  onNavigate: (ref: string) => void;
}) {
  const [data, setData] = useState<Accountability | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  useEffect(() => {
    let active = true;
    evidenceRequest<Accountability>(
      `/api/document-accountability?version=${version}`,
    )
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [version]);
  return (
    <div className="space-y-4 p-5" data-testid="document-accountability">
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p>Loading document accountability…</p>}
      {data && (
        <>
          <p className="font-semibold">{data.total} documents accounted for</p>
          <p className="text-xs text-slate-500">{data.note}</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.counts).map(([state, count]) => (
              <span className="rounded bg-slate-100 p-2 text-xs" key={state}>
                {state}: {count}
              </span>
            ))}
          </div>
          <label className="block text-sm">
            Document disposition
            <select
              aria-label="Document disposition"
              className={evidenceControl}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">All dispositions</option>
              {Object.keys(data.counts).map((state) => (
                <option key={state} value={state}>
                  {state}
                </option>
              ))}
            </select>
          </label>
          <input
            aria-label="Accountability document search"
            className={evidenceControl}
            placeholder="Search documents or IDs"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="table-scroll">
            <table className="data-table accountability-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Disposition</th>
                  <th>Extraction</th>
                  <th>Accountability evidence</th>
                </tr>
              </thead>
              <tbody>
                {data.documents
                  .filter(
                    (d) =>
                      (filter === "all" || d.dispositions.includes(filter)) &&
                      `${d.id} ${d.title}`
                        .toLowerCase()
                        .includes(search.toLowerCase()),
                  )
                  .map((d) => (
                    <tr key={d.id} data-testid={`accountability-${d.id}`}>
                      <td>
                        <button
                          className="line-select"
                          aria-label={`Inspect ${d.id} document`}
                          onClick={() => onOpenDocument(d.id)}
                        >
                          <span className="line-key">{d.id}</span>
                          <strong>{d.title}</strong>
                        </button>
                      </td>
                      <td>
                        <div className="badge-stack">
                          {d.dispositions.map((v) => (
                            <StatusBadge key={v} value={v} />
                          ))}
                        </div>
                      </td>
                      <td>
                        <StatusBadge value={d.extraction_status} />
                        <small className="muted block">
                          {d.extracted_values} extracted fields
                        </small>
                      </td>
                      <td>
                        <details>
                          <summary>
                            Disposition reasons ({d.reasons.length})
                          </summary>
                          {d.reasons.map((reason, i) => (
                            <div key={i}>
                              <p>
                                {reason.disposition}: {reason.reason}
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {reason.refs.map((ref) => (
                                  <button
                                    className="text-button"
                                    key={ref}
                                    onClick={() => onNavigate(ref)}
                                  >
                                    {ref}
                                  </button>
                                ))}
                              </div>
                            </div>
                          ))}
                        </details>
                        {d.duplicate_pages.map((page) => (
                          <p key={page.page} className="text-xs text-amber-800">
                            Page {page.page} duplicates page{" "}
                            {page.duplicate_of_page}; review the page, not the
                            whole document as a duplicate.
                          </p>
                        ))}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {data.unresolved_provenance.length > 0 && (
            <details>
              <summary className="text-sm">
                Unresolved packet provenance (
                {data.unresolved_provenance.length})
              </summary>
              {data.unresolved_provenance.map((r) => (
                <button
                  className={`${evidenceButton} m-1 break-all`}
                  key={r.ref}
                  onClick={() => onNavigate(r.ref)}
                >
                  {r.ref}: {r.reason}
                </button>
              ))}
            </details>
          )}
        </>
      )}
    </div>
  );
}
