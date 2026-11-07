
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReviewWorkspace, {
  type ReviewFinding,
} from "@/components/ReviewWorkspace";
import SourceVerification from "@/components/SourceVerification";

const API =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RecordData = Record<string, any>;
type Tab = "return" | "documents" | "review";

function money(value: unknown): string {
  if (typeof value !== "number") {
    return String(value ?? "—");
  }

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
  }).format(value);
}

async function checkResponse(response: Response) {
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json();
}

function findMatchingLine(
  finding: ReviewFinding,
  lines: RecordData[]
): RecordData | null {
  const references = Array.isArray(finding.refs)
    ? finding.refs.filter(
      (ref): ref is string => typeof ref === "string"
    )
    : [];

  for (const ref of references) {
    const exactMatch = lines.find(
      (line) => line.key === ref
    );

    if (exactMatch) return exactMatch;
  }

  const searchableText = [
    finding.description,
    finding.title,
    ...references,
  ]
    .filter(Boolean)
    .join(" ");

  for (const line of lines) {
    if (typeof line.key !== "string") continue;

    const escapedKey = line.key.replace(
      /[.*+?^${}()|[\]\\]/g,
      "\\$&"
    );

    const expression = new RegExp(
      `(^|[^A-Za-z0-9_.])${escapedKey}(?=$|[^A-Za-z0-9_.])`
    );

    if (expression.test(searchableText)) {
      return line;
    }
  }

  return null;
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("return");
  const [overview, setOverview] =
    useState<RecordData | null>(null);
  const [lines, setLines] = useState<RecordData[]>([]);
  const [documents, setDocuments] = useState<RecordData[]>([]);
  const [validation, setValidation] =
    useState<RecordData | null>(null);

  const [version, setVersion] = useState("v3");
  const [search, setSearch] = useState("");

  const [selectedLine, setSelectedLine] =
    useState<RecordData | null>(null);
  const [selectedDocument, setSelectedDocument] =
    useState<RecordData | null>(null);
  const [lineage, setLineage] =
    useState<RecordData | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] =
    useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [inspectorLoading, setInspectorLoading] =
    useState(false);
  const [error, setError] = useState("");
  const [inspectorMessage, setInspectorMessage] = useState("");

  const selectionRequest = useRef(0);

  useEffect(() => {
    let active = true;

    Promise.all([
      fetch(`${API}/api/overview`).then(checkResponse),
      fetch(`${API}/api/documents`).then(checkResponse),
    ])
      .then(([overviewData, documentData]) => {
        if (!active) return;

        setOverview(overviewData);
        setDocuments(
          Array.isArray(documentData)
            ? documentData
            : documentData.documents ?? []
        );
      })
      .catch((err) => {
        if (!active) return;
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load workpaper"
        );
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    selectionRequest.current += 1;
    setLoading(true);
    setLines([]);
    setSelectedLine(null);
    setSelectedDocument(null);
    setSelectedEvidenceId(null);
    setLineage(null);
    setInspectorMessage("");
    setInspectorLoading(false);

    Promise.all([
      fetch(
        `${API}/api/return-lines?version=${encodeURIComponent(
          version
        )}`
      ).then(checkResponse),
      fetch(
        `${API}/api/validation?version=${encodeURIComponent(
          version
        )}`
      ).then(checkResponse),
    ])
      .then(([returnData, validationData]) => {
        if (!active) return;

        setLines(returnData.lines ?? []);
        setValidation(validationData);
        setError("");
      })
      .catch((err) => {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load return data"
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [version]);

  async function selectLine(line: RecordData) {
    const requestId = ++selectionRequest.current;

    setSelectedLine(line);
    setSelectedDocument(null);
    setSelectedEvidenceId(null);
    setLineage(null);
    setInspectorMessage("");
    setInspectorLoading(true);
    setError("");

    try {
      const result = await fetch(
        `${API}/api/lineage/${encodeURIComponent(
          line.key
        )}?version=${encodeURIComponent(version)}`
      ).then(checkResponse);

      if (requestId !== selectionRequest.current) return;

      setLineage(result.lineage ?? result);
    } catch (err) {
      if (requestId !== selectionRequest.current) return;

      setInspectorMessage(
        err instanceof Error
          ? err.message
          : "Unable to trace return line"
      );
    } finally {
      if (requestId === selectionRequest.current) {
        setInspectorLoading(false);
      }
    }
  }

  async function selectDocument(id: string) {
    const requestId = ++selectionRequest.current;

    setSelectedDocument(null);
    setSelectedEvidenceId(null);
    setInspectorLoading(true);
    setInspectorMessage("");
    setError("");

    try {
      const document = await fetch(
        `${API}/api/documents/${encodeURIComponent(id)}`
      ).then(checkResponse);

      if (requestId !== selectionRequest.current) return;

      setSelectedDocument(document);
    } catch (err) {
      if (requestId !== selectionRequest.current) return;

      setInspectorMessage(
        err instanceof Error
          ? err.message
          : "Unable to open document"
      );
    } finally {
      if (requestId === selectionRequest.current) {
        setInspectorLoading(false);
      }
    }
  }

  function selectFindingEvidence(finding: ReviewFinding) {
    const matchingLine = findMatchingLine(finding, lines);

    if (matchingLine) {
      void selectLine(matchingLine);
      return;
    }

    selectionRequest.current += 1;
    setSelectedLine(null);
    setSelectedDocument(null);
    setSelectedEvidenceId(null);
    setLineage(null);
    setInspectorLoading(false);
    setInspectorMessage(
      "No matching return line was found for this finding. " +
      "Its references are available in the review panel."
    );
  }

  function openEvidence(evidenceId: string) {
    selectionRequest.current += 1;
    setInspectorLoading(false);
    setSelectedDocument(null);
    setSelectedEvidenceId(evidenceId);
    setInspectorMessage("");
  }

  function closeEvidence() {
    setSelectedEvidenceId(null);
  }

  const filteredLines = useMemo(() => {
    const query = search.toLowerCase();

    return lines.filter((line) =>
      `${line.key ?? ""} ${line.label ?? ""} ${line.form ?? ""
        }`
        .toLowerCase()
        .includes(query)
    );
  }, [lines, search]);

  const filteredDocuments = useMemo(() => {
    const query = search.toLowerCase();

    return documents.filter((doc) =>
      `${doc.id ?? ""} ${doc.title ?? ""} ${doc.document_type ?? ""
        }`
        .toLowerCase()
        .includes(query)
    );
  }, [documents, search]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-600">
              MIRAFLORES / WORKPAPER
            </div>

            <h1 className="mt-1 text-2xl font-semibold">
              Okafor–Lindqvist
            </h1>

            <p className="text-sm text-slate-500">
              2025 Individual Tax Return · Evidence Workspace
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="rounded-full bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700">
              Review in progress
            </span>

            <select
              aria-label="Return version"
              value={version}
              onChange={(event) =>
                setVersion(event.target.value)
              }
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm"
            >
              <option value="v1">Return v1</option>
              <option value="v2">Return v2</option>
              <option value="v3">Return v3</option>
            </select>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-6 py-7">
        {error && (
          <div
            role="alert"
            className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <div className="mb-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Source documents"
            value={overview?.stats?.documents ?? "—"}
          />
          <Metric
            label="Extracted values"
            value={
              overview?.stats?.extracted_values ?? "—"
            }
          />
          <Metric label="Return lines" value={lines.length} />
          <Metric
            label="Validation findings"
            value={validation?.total ?? "—"}
          />
        </div>

        <div className="grid gap-6 xl:grid-cols-[230px_minmax(0,1fr)_390px]">
          <aside className="h-fit rounded-2xl border border-slate-200 bg-white p-4">
            <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Workspace
            </p>

            {(
              [
                ["return", "Tax Return"],
                ["documents", "Document Explorer"],
                ["review", "Review Findings"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => {
                  setTab(key);
                  setSearch("");
                }}
                className={`mb-1 w-full rounded-xl px-4 py-3 text-left text-sm font-medium transition ${tab === key
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600 hover:bg-slate-50"
                  }`}
              >
                {label}
              </button>
            ))}

            <div className="mt-6 border-t border-slate-100 px-3 pt-5">
              <p className="text-xs font-semibold text-slate-400">
                CURRENT DATASET
              </p>
              <p className="mt-2 text-sm font-medium">
                {overview?.packet?.client_id ?? "CL-20417"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Original packet · Tax year 2025
              </p>
            </div>
          </aside>

          <section className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 p-5">
              <h2 className="text-lg font-semibold">
                {tab === "return"
                  ? "Tax Return Lines"
                  : tab === "documents"
                    ? "Source Documents"
                    : "Independent Validation"}
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                {tab === "return"
                  ? "Select a line to inspect its calculation and evidence."
                  : tab === "documents"
                    ? "Open a document to inspect its simulated printed content."
                    : "Review, resolve, and track tax workpaper findings."}
              </p>

              {tab !== "review" && (
                <input
                  value={search}
                  onChange={(event) =>
                    setSearch(event.target.value)
                  }
                  placeholder={
                    tab === "return"
                      ? "Search by form, line, or description..."
                      : "Search documents..."
                  }
                  className="mt-5 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-indigo-400"
                />
              )}
            </div>

            {tab === "review" ? (
              <ReviewWorkspace
                version={version}
                onSelectFinding={selectFindingEvidence}
              />
            ) : loading ? (
              <p className="p-6 text-sm text-slate-500">
                Loading workpaper...
              </p>
            ) : tab === "return" ? (
              <div className="max-h-[680px] overflow-auto">
                {filteredLines.map((line) => (
                  <button
                    key={line.key}
                    onClick={() => void selectLine(line)}
                    className={`flex w-full items-center justify-between gap-4 border-b border-slate-100 px-5 py-4 text-left hover:bg-indigo-50/50 ${selectedLine?.key === line.key
                        ? "bg-indigo-50"
                        : ""
                      }`}
                  >
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-indigo-600">
                        {line.key}
                      </p>
                      <p className="mt-1 text-sm font-medium">
                        {line.label}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {line.jurisdiction}
                      </p>
                    </div>
                    <p className="shrink-0 font-mono text-sm font-semibold">
                      {money(line.value)}
                    </p>
                  </button>
                ))}

                {filteredLines.length === 0 && (
                  <p className="p-6 text-sm text-slate-500">
                    No matching return lines.
                  </p>
                )}
              </div>
            ) : (
              <div className="max-h-[680px] overflow-auto">
                {filteredDocuments.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() =>
                      void selectDocument(doc.id)
                    }
                    className="w-full border-b border-slate-100 px-5 py-4 text-left hover:bg-indigo-50/50"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-xs font-bold text-indigo-600">
                        {doc.id}
                      </span>
                      <span className="text-xs text-slate-400">
                        {doc.page_count} pages
                      </span>
                    </div>
                    <p className="mt-2 text-sm font-medium">
                      {doc.title}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {doc.document_type}
                    </p>
                  </button>
                ))}

                {filteredDocuments.length === 0 && (
                  <p className="p-6 text-sm text-slate-500">
                    No matching documents.
                  </p>
                )}
              </div>
            )}
          </section>

          <aside className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 p-5">
              <h2 className="text-lg font-semibold">
                Evidence Inspector
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Calculation lineage and source records
              </p>
            </div>

            <div className="max-h-[750px] overflow-auto p-5">
              {selectedEvidenceId ? (
                <SourceVerification
                  evidenceId={selectedEvidenceId}
                  onClose={closeEvidence}
                  onOpenDocument={(id) =>
                    void selectDocument(id)
                  }
                />
              ) : inspectorLoading ? (
                <p className="text-sm text-slate-500">
                  Loading supporting evidence...
                </p>
              ) : selectedDocument ? (
                <div>
                  <button
                    onClick={() =>
                      setSelectedDocument(null)
                    }
                    className="mb-4 text-sm font-medium text-indigo-600"
                  >
                    ← Back to evidence
                  </button>

                  <p className="text-xs font-bold text-indigo-600">
                    {selectedDocument.id}
                  </p>
                  <h3 className="mt-2 font-semibold">
                    {selectedDocument.title}
                  </h3>

                  {(selectedDocument.pages ?? []).map(
                    (page: RecordData) => (
                      <div
                        key={page.page}
                        className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4"
                      >
                        <p className="mb-3 text-xs font-semibold text-slate-400">
                          PAGE {page.page}
                        </p>
                        <p className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-700">
                          {page.printed_content}
                        </p>
                      </div>
                    )
                  )}
                </div>
              ) : lineage ? (
                <LineageNode
                  node={lineage}
                  onOpenDocument={selectDocument}
                  onOpenEvidence={openEvidence}
                />
              ) : inspectorMessage ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <h3 className="text-sm font-semibold text-amber-900">
                    Evidence not linked
                  </h3>
                  <p className="mt-2 text-sm text-amber-800">
                    {inspectorMessage}
                  </p>
                </div>
              ) : (
                <div className="py-14 text-center">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-2xl text-indigo-600">
                    ◎
                  </div>
                  <h3 className="font-semibold">
                    Explore the evidence
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Select a return line or review finding.
                    Then click an evidence reference to verify
                    it against the simulated source document.
                  </p>
                </div>
              )}
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight">
        {value}
      </p>
    </div>
  );
}

function LineageNode({
  node,
  onOpenDocument,
  onOpenEvidence,
}: {
  node: RecordData;
  onOpenDocument: (id: string) => void;
  onOpenEvidence: (id: string) => void;
}) {
  if (node.missing || node.cycle) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
        {node.key}:{" "}
        {node.missing ? "Missing input" : "Cycle detected"}
      </div>
    );
  }

  return (
    <div className="mb-4 rounded-xl border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs font-bold text-indigo-600">
            {node.key}
          </p>
          <p className="mt-1 text-sm font-medium">
            {node.label}
          </p>
        </div>
        <span className="font-mono text-sm font-semibold">
          {money(node.value)}
        </span>
      </div>

      {node.rule && (
        <p className="mt-2 text-xs text-slate-400">
          Rule: {node.rule}
        </p>
      )}

      {(node.sources ?? []).map(
        (source: RecordData, index: number) => {
          const ref = String(source.ref ?? "");
          const isEvidence = /^ev-\d+$/.test(ref);

          return (
            <div
              key={`${ref}-${index}`}
              className="mt-3 rounded-lg bg-slate-50 p-3"
            >
              {isEvidence ? (
                <button
                  type="button"
                  onClick={() => onOpenEvidence(ref)}
                  className="break-all text-left font-mono text-xs font-semibold text-indigo-600 hover:underline"
                >
                  {ref}
                </button>
              ) : (
                <p className="break-all font-mono text-xs text-slate-500">
                  {ref}
                </p>
              )}

              {source.evidence && (
                <>
                  <p className="mt-2 text-sm font-medium">
                    {source.evidence.label}
                  </p>
                  <p className="mt-1 text-sm">
                    Extracted:{" "}
                    {String(source.evidence.value ?? "—")}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Confidence:{" "}
                    {typeof source.evidence.confidence ===
                      "number"
                      ? `${Math.round(
                        source.evidence.confidence * 100
                      )}%`
                      : "—"}
                  </p>
                </>
              )}

              {source.document && (
                <button
                  type="button"
                  onClick={() =>
                    onOpenDocument(source.document.id)
                  }
                  className="mt-3 text-left text-sm font-medium text-indigo-600 hover:underline"
                >
                  Open {source.document.id}:{" "}
                  {source.document.title}
                </button>
              )}

              {source.type === "external_reference" && (
                <p className="mt-1 text-xs text-amber-700">
                  Reference resolution pending
                </p>
              )}
            </div>
          );
        }
      )}

      {(node.inputs ?? []).length > 0 && (
        <div className="mt-4 border-l-2 border-indigo-100 pl-3">
          <p className="mb-3 text-xs font-semibold uppercase text-slate-400">
            Calculation inputs
          </p>
          {node.inputs.map(
            (input: RecordData, index: number) => (
              <LineageNode
                key={`${input.key}-${index}`}
                node={input}
                onOpenDocument={onOpenDocument}
                onOpenEvidence={onOpenEvidence}
              />
            )
          )}
        </div>
      )}
    </div>
  );
}
