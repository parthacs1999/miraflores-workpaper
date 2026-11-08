"use client";

import { useAppNavigation, viewInfo } from "@/components/shell/navigation";
import {
  PageHeader,
  StatusBadge,
  Pagination,
  EmptyState,
} from "@/components/ui/primitives";
import ReturnLineContext from "@/components/ReturnLineContext";
import FirmWorkflow from "@/components/FirmWorkflow";
import { apiFetch } from "@/components/session";

import { useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import ReviewWorkspace, {
  type ReviewFinding,
} from "@/components/ReviewWorkspace";
import SourceVerification from "@/components/SourceVerification";
import ReconciliationDashboard from "@/components/ReconciliationDashboard";
import DocumentAccountability from "@/components/DocumentAccountability";
import DocumentInspector from "@/components/DocumentInspector";
import EvidenceResolver from "@/components/EvidenceResolver";
import AdjustmentWorkspace from "@/components/AdjustmentWorkspace";
import type {
  SourceDocument,
  ReturnLine,
  Lineage,
  Overview,
} from "@/components/workpaper-types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Tab =
  | "return"
  | "documents"
  | "review"
  | "adjustments"
  | "accountability"
  | "resolver"
  | "reconciliation";

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
  lines: ReturnLine[],
): ReturnLine | null {
  const references = Array.isArray(finding.refs)
    ? finding.refs.filter((ref): ref is string => typeof ref === "string")
    : [];

  for (const ref of references) {
    const exactMatch = lines.find((line) => line.key === ref);

    if (exactMatch) return exactMatch;
  }

  const searchableText = [finding.description, finding.title, ...references]
    .filter(Boolean)
    .join(" ");

  for (const line of lines) {
    if (typeof line.key !== "string") continue;

    const escapedKey = line.key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

    const expression = new RegExp(
      `(^|[^A-Za-z0-9_.])${escapedKey}(?=$|[^A-Za-z0-9_.])`,
    );

    if (expression.test(searchableText)) {
      return line;
    }
  }

  return null;
}

type AdjustmentOverlay = {
  id: string;
  state: string;
  stale: boolean;
  payload: { target: string; proposed_value: string };
};
function Home() {
  const navigation = useAppNavigation();
  const [localTab, setLocalTab] = useState<Tab>("return");
  const routeTab =
    navigation?.view === "findings" ? "review" : navigation?.view;
  const tab: Tab = (
    [
      "return",
      "documents",
      "review",
      "adjustments",
      "accountability",
      "resolver",
      "reconciliation",
    ].includes(routeTab ?? "")
      ? routeTab
      : localTab
  ) as Tab;
  const setTab = (next: Tab) => {
    setLocalTab(next);
    navigation?.navigate(next === "review" ? "findings" : next);
  };
  const [jurisdiction, setJurisdiction] = useState("all");
  const [category, setCategory] = useState("all");
  const [documentType, setDocumentType] = useState("all");
  const [page, setPage] = useState(0);
  const [overlayState, setOverlayState] = useState<{
    version: string;
    items: AdjustmentOverlay[];
    error: string;
  }>({ version: "", items: [], error: "" });
  const [documentState, setDocumentState] = useState("all");
  const [accounts, setAccounts] = useState<{
    version: string;
    documents: { id: string; dispositions: string[] }[];
  }>({ version: "", documents: [] });
  const [overview, setOverview] = useState<Overview | null>(null);
  const [lines, setLines] = useState<ReturnLine[]>([]);
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [validation, setValidation] = useState<{ total: number } | null>(null);

  const [version, setVersion] = useState("v3");
  const overlays = overlayState.version === version ? overlayState.items : [];
  const [search, setSearch] = useState("");

  const [selectedLine, setSelectedLine] = useState<ReturnLine | null>(null);
  const [selectedDocument, setSelectedDocument] =
    useState<SourceDocument | null>(null);
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(
    null,
  );

  const [adjustmentToOpen, setAdjustmentToOpen] = useState<string | null>(null);
  const [selectedReference, setSelectedReference] = useState<string | null>(
    null,
  );

  const [loading, setLoading] = useState(true);
  const [inspectorLoading, setInspectorLoading] = useState(false);
  const [error, setError] = useState("");
  const [inspectorMessage, setInspectorMessage] = useState("");

  const selectionRequest = useRef(0);

  useEffect(() => {
    let active = true;

    Promise.all([
      apiFetch(`${API}/api/overview`).then(checkResponse),
      apiFetch(`${API}/api/documents`).then(checkResponse),
    ])
      .then(([overviewData, documentData]) => {
        if (!active) return;

        setOverview(overviewData);
        setDocuments(
          Array.isArray(documentData)
            ? documentData
            : (documentData.documents ?? []),
        );
      })
      .catch((err) => {
        if (!active) return;
        setError(
          err instanceof Error ? err.message : "Unable to load workpaper",
        );
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    Promise.all([
      apiFetch(
        `${API}/api/return-lines?version=${encodeURIComponent(version)}`,
      ).then(checkResponse),
      apiFetch(
        `${API}/api/validation?version=${encodeURIComponent(version)}`,
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
          err instanceof Error ? err.message : "Unable to load return data",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [version]);

  useEffect(() => {
    let active = true;
    apiFetch(`${API}/api/adjustments?version=${version}`)
      .then(checkResponse)
      .then((d) => {
        if (active)
          setOverlayState({ version, items: d.adjustments ?? [], error: "" });
      })
      .catch(() => {
        if (active)
          setOverlayState({
            version,
            items: [],
            error:
              "Adjustment ledger unavailable. Approved workpaper values cannot be established; engine values remain separate.",
          });
      });
    return () => {
      active = false;
    };
  }, [version]);
  useEffect(() => {
    let active = true;
    apiFetch(`${API}/api/document-accountability?version=${version}`)
      .then(checkResponse)
      .then((d) => {
        if (active) setAccounts({ version, documents: d.documents });
      })
      .catch(() => {
        if (active) setAccounts({ version, documents: [] });
      });
    return () => {
      active = false;
    };
  }, [version]);
  const selectDeepLine = useEffectEvent(
    (line: ReturnLine) => void selectLine(line, false),
  );
  useEffect(() => {
    const key = navigation?.reference;
    if (!key || tab !== "return" || !lines.length) return;
    const line = lines.find((l) => l.key === key);
    if (line) selectDeepLine(line);
  }, [navigation?.reference, tab, lines]);
  function changeVersion(nextVersion: string) {
    if (nextVersion === version) return;
    setAdjustmentToOpen(null);
    selectionRequest.current += 1;
    setLoading(true);
    setLines([]);
    setSelectedLine(null);
    setSelectedDocument(null);
    setSelectedEvidenceId(null);
    setSelectedReference(null);
    setLineage(null);
    setInspectorMessage("");
    setInspectorLoading(false);
    setVersion(nextVersion);
  }

  async function selectLine(line: ReturnLine, updateUrl = true) {
    if (updateUrl) navigation?.navigate("return", line.key);
    const requestId = ++selectionRequest.current;

    setSelectedLine(line);
    setSelectedDocument(null);
    setSelectedEvidenceId(null);
    setSelectedReference(null);
    setLineage(null);
    setInspectorMessage("");
    setInspectorLoading(true);
    setError("");

    try {
      const result = await apiFetch(
        `${API}/api/lineage/${encodeURIComponent(
          line.key,
        )}?version=${encodeURIComponent(version)}`,
      ).then(checkResponse);

      if (requestId !== selectionRequest.current) return;

      setLineage(result.lineage ?? result);
    } catch (err) {
      if (requestId !== selectionRequest.current) return;

      setInspectorMessage(
        err instanceof Error ? err.message : "Unable to trace return line",
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
    setSelectedReference(null);
    setInspectorLoading(true);
    setInspectorMessage("");
    setError("");

    try {
      const document = await apiFetch(
        `${API}/api/documents/${encodeURIComponent(id)}`,
      ).then(checkResponse);

      if (requestId !== selectionRequest.current) return;

      setSelectedDocument(document);
      if (window.matchMedia("(max-width:1000px)").matches)
        requestAnimationFrame(() => documentInspectorScroll());
    } catch (err) {
      if (requestId !== selectionRequest.current) return;

      setInspectorMessage(
        err instanceof Error ? err.message : "Unable to open document",
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
      void selectLine(matchingLine, false);
      return;
    }

    if (finding.refs?.length) {
      openReference(finding.refs[0]);
      return;
    }
    selectionRequest.current += 1;
    setSelectedLine(null);
    setSelectedDocument(null);
    setSelectedEvidenceId(null);
    setSelectedReference(null);
    setLineage(null);
    setInspectorLoading(false);
    setInspectorMessage(
      "No matching return line was found for this finding. " +
        "Its references are available in the review panel.",
    );
  }

  function documentInspectorScroll() {
    document
      .querySelector(".workpaper-inspector")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function openEvidence(evidenceId: string) {
    setSelectedReference(null);
    selectionRequest.current += 1;
    setInspectorLoading(false);
    setSelectedDocument(null);
    setSelectedEvidenceId(evidenceId);
    if (window.matchMedia("(max-width:1000px)").matches)
      requestAnimationFrame(documentInspectorScroll);
    setInspectorMessage("");
  }

  function openReference(ref: string) {
    if (/^ev-\d+$/.test(ref)) {
      openEvidence(ref);
      return;
    }
    if (/^D\d+$/.test(ref)) {
      void selectDocument(ref);
      return;
    }
    if (lines.some((line) => line.key === ref)) {
      void selectLine(
        lines.find((line) => line.key === ref)!,
        false,
      );
      return;
    }
    selectionRequest.current += 1;
    setSelectedEvidenceId(null);
    setSelectedDocument(null);
    setInspectorLoading(false);
    setInspectorMessage("");
    setSelectedReference(ref);
  }

  function closeEvidence() {
    setSelectedEvidenceId(null);
    setSelectedReference(null);
  }

  const filteredLines = useMemo(() => {
    const query = search.toLowerCase();

    return lines.filter(
      (line) =>
        (jurisdiction === "all" || line.jurisdiction === jurisdiction) &&
        (category === "all" || line.form === category) &&
        `${line.key ?? ""} ${line.label ?? ""} ${line.form ?? ""}`
          .toLowerCase()
          .includes(query),
    );
  }, [lines, search, jurisdiction, category]);

  const filteredDocuments = useMemo(() => {
    const query = search.toLowerCase();

    return documents.filter(
      (doc) =>
        (documentType === "all" || doc.document_type === documentType) &&
        (documentState === "all" ||
          (accounts.version === version &&
            accounts.documents
              .find((d) => d.id === doc.id)
              ?.dispositions.includes(documentState))) &&
        `${doc.id ?? ""} ${doc.title ?? ""} ${doc.document_type ?? ""}`
          .toLowerCase()
          .includes(query),
    );
  }, [documents, search, documentType, documentState, accounts, version]);

  const showInspector =
    ["return", "documents", "review"].includes(tab) ||
    !!(
      selectedEvidenceId ||
      selectedDocument ||
      selectedReference ||
      lineage ||
      inspectorMessage
    );
  return (
    <div className="workpaper-workspace feature-workspace">
      <PageHeader
        eyebrow="Tax workpaper"
        title={
          navigation?.legacy
            ? "Okafor–Lindqvist"
            : viewInfo(navigation?.view ?? "return").label
        }
        description="Original engine values · Evidence-backed investigation · Independent approval"
        actions={
          <select
            aria-label="Return version"
            value={version}
            onChange={(e) => changeVersion(e.target.value)}
            className="ui-control"
          >
            <option value="v1">Return v1</option>
            <option value="v2">Return v2</option>
            <option value="v3">Return v3</option>
          </select>
        }
      />
      <div className="workpaper-context">
        <span>
          <span>Source documents</span>{" "}
          <strong>{overview?.stats.documents ?? "—"}</strong>
        </span>
        <span>
          <span>Extracted values</span>{" "}
          <strong>{overview?.stats.extracted_values ?? "—"}</strong>
        </span>
        <span>
          Return lines <strong>{lines.length}</strong>
        </span>
        <span>
          Validation findings <strong>{validation?.total ?? "—"}</strong>
        </span>
        <StatusBadge value="in_review">Review in progress</StatusBadge>
      </div>
      <div>
        {error && (
          <div
            role="alert"
            className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <nav
          className="segmented-tabs workpaper-subnav"
          aria-label="Workpaper tools"
        >
          {(
            [
              ...(navigation?.legacy
                ? [
                    ["return", "Tax Return"],
                    ["documents", "Document Explorer"],
                    ["adjustments", "Tax Adjustments"],
                    ["reconciliation", "Reconciliation Dashboard"],
                  ]
                : []),
              ["accountability", "Document Accountability"],
              ["resolver", "Evidence Resolver"],
              ["review", "Review Findings"],
            ] as [Tab, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => {
                setTab(id);
                setSearch("");
                setPage(0);
              }}
              aria-pressed={tab === id}
            >
              {label}
            </button>
          ))}
        </nav>
        <div
          className={`workpaper-layout ${["return", "documents"].includes(tab) ? "" : "investigation-layout"} ${!showInspector ? "without-inspector" : ""}`}
        >
          <section className="workpaper-master section-card">
            <div className="border-b border-slate-100 p-5">
              <h2 className="text-lg font-semibold">
                {tab === "return"
                  ? "Tax Return Lines"
                  : tab === "documents"
                    ? "Source Documents"
                    : tab === "adjustments"
                      ? "Audited Tax Adjustments"
                      : tab === "accountability"
                        ? "Document Accountability"
                        : tab === "resolver"
                          ? "Unified Evidence Resolver"
                          : tab === "reconciliation"
                            ? "Reconciliation Dashboard"
                            : "Independent Validation"}
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                {tab === "return"
                  ? "Select a line to inspect its calculation and evidence."
                  : tab === "documents"
                    ? "Open a document to inspect its simulated printed content."
                    : tab === "adjustments"
                      ? "Prepare, independently approve, and audit estimated tax adjustments."
                      : tab === "accountability"
                        ? "Evidence-based dispositions across all source documents."
                        : tab === "resolver"
                          ? "Inspect every documented reference format and unresolved reason."
                          : "Review, resolve, and track tax workpaper findings."}
              </p>

              {(tab === "return" || tab === "documents") && (
                <input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setPage(0);
                  }}
                  placeholder={
                    tab === "return"
                      ? "Search by form, line, or description..."
                      : "Search documents..."
                  }
                  className="mt-5 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-indigo-400"
                />
              )}
            </div>

            {tab === "return" && (
              <div className="workpaper-tools">
                <label>
                  Jurisdiction
                  <select
                    aria-label="Return jurisdiction"
                    className="ui-control"
                    value={jurisdiction}
                    onChange={(e) => {
                      setJurisdiction(e.target.value);
                      setPage(0);
                    }}
                  >
                    <option value="all">Federal & California</option>
                    {[...new Set(lines.map((l) => l.jurisdiction))].map((j) => (
                      <option key={j}>{j}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Tax form
                  <select
                    aria-label="Tax form"
                    className="ui-control"
                    value={category}
                    onChange={(e) => {
                      setCategory(e.target.value);
                      setPage(0);
                    }}
                  >
                    <option value="all">All forms</option>
                    {[...new Set(lines.map((l) => l.form))].map((j) => (
                      <option key={j}>{j}</option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            {overlayState.version === version && overlayState.error && (
              <p role="alert" className="notice warning">
                {overlayState.error}
              </p>
            )}
            {tab === "documents" && (
              <div className="workpaper-tools">
                <label>
                  Review status
                  <select
                    className="ui-control"
                    aria-label="Document review status"
                    value={documentState}
                    onChange={(e) => setDocumentState(e.target.value)}
                  >
                    <option value="all">All dispositions</option>
                    {[
                      "used",
                      "superseded",
                      "duplicate",
                      "unextracted",
                      "unused",
                      "requires_review",
                    ].map((v) => (
                      <option key={v} value={v}>
                        {v.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Document type
                  <select
                    className="ui-control"
                    aria-label="Document type"
                    value={documentType}
                    onChange={(e) => {
                      setDocumentType(e.target.value);
                      setPage(0);
                    }}
                  >
                    <option value="all">All document types</option>
                    {[...new Set(documents.map((d) => d.document_type))].map(
                      (t) => (
                        <option key={t}>{t}</option>
                      ),
                    )}
                  </select>
                </label>
              </div>
            )}
            {tab === "reconciliation" ? (
              <ReconciliationDashboard
                key={version}
                version={version}
                onNavigate={openReference}
                onOpenAdjustment={(id) => {
                  setAdjustmentToOpen(id);
                  setTab("adjustments");
                }}
              />
            ) : tab === "accountability" ? (
              <DocumentAccountability
                key={version}
                version={version}
                onOpenDocument={selectDocument}
                onNavigate={openReference}
              />
            ) : tab === "resolver" ? (
              <EvidenceResolver
                key={version}
                version={version}
                onNavigate={openReference}
              />
            ) : tab === "adjustments" ? (
              <AdjustmentWorkspace
                key={version}
                version={version}
                onOpenDocument={selectDocument}
                onOpenEvidence={openEvidence}
                onOpenReference={openReference}
                initialAdjustmentId={adjustmentToOpen}
              />
            ) : tab === "review" ? (
              <ReviewWorkspace
                version={version}
                onSelectFinding={selectFindingEvidence}
                onOpenReference={openReference}
              />
            ) : loading ? (
              <p className="p-6 text-sm text-slate-500">Loading workpaper...</p>
            ) : tab === "return" ? (
              <>
                <div className="table-scroll">
                  <table className="data-table return-lines-table">
                    <thead>
                      <tr>
                        <th scope="col">Return line</th>
                        <th scope="col">Engine value</th>
                        <th scope="col">Proposed</th>
                        <th scope="col">Approved workpaper</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredLines
                        .slice(page * 40, (page + 1) * 40)
                        .map((line) => {
                          const related = overlays.filter(
                            (a) => a.payload.target === line.key,
                          );
                          const approved = related.find(
                            (a) => a.state === "approved" && !a.stale,
                          );
                          const proposed = related.filter(
                            (a) =>
                              ["draft", "submitted"].includes(a.state) &&
                              !a.stale,
                          );
                          return (
                            <tr
                              key={line.key}
                              className={
                                selectedLine?.key === line.key ? "selected" : ""
                              }
                            >
                              <td>
                                <button
                                  className="line-select"
                                  aria-label={`${line.key} ${line.label}`}
                                  onClick={() => void selectLine(line)}
                                >
                                  <span className="line-key">{line.key}</span>
                                  <strong>{line.label}</strong>
                                  <small>
                                    {line.jurisdiction} · {line.form} ·{" "}
                                    {(line.sources ?? []).length} direct sources
                                  </small>
                                </button>
                              </td>
                              <td className="numeric">{money(line.value)}</td>
                              <td className="numeric">
                                {proposed.length === 1
                                  ? money(
                                      Number(
                                        proposed[0].payload.proposed_value,
                                      ),
                                    )
                                  : proposed.length
                                    ? `${proposed.length} alternatives`
                                    : "—"}
                              </td>
                              <td className="numeric">
                                {overlayState.version !== version ? (
                                  "Loading ledger…"
                                ) : overlayState.error ? (
                                  "Unavailable"
                                ) : approved ? (
                                  <>
                                    <strong>
                                      {money(
                                        Number(approved.payload.proposed_value),
                                      )}
                                    </strong>
                                    <StatusBadge value="approved" />
                                  </>
                                ) : (
                                  <>
                                    <span>{money(line.value)}</span>
                                    <small className="muted block">
                                      Engine baseline
                                    </small>
                                  </>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                  {!filteredLines.length && (
                    <EmptyState
                      title="No matching return lines"
                      description="Try another form, jurisdiction, or search term."
                    />
                  )}
                </div>
                <Pagination
                  page={page}
                  pageSize={40}
                  total={filteredLines.length}
                  onPage={setPage}
                />
                <p className="table-footnote">
                  Approved values apply only to the ledger’s exact target.
                  Downstream engine totals are not recomputed. Draft
                  alternatives are never summed.
                </p>
              </>
            ) : (
              <div className="max-h-[680px] overflow-auto">
                {filteredDocuments.map((doc) => (
                  <button
                    key={doc.id}
                    aria-label={`${doc.id} ${doc.title}`}
                    onClick={() => void selectDocument(doc.id)}
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
                    <p className="mt-2 text-sm font-medium">{doc.title}</p>
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

          <aside
            className="workpaper-inspector section-card"
            hidden={!showInspector}
          >
            <div className="border-b border-slate-100 p-5">
              <h2 className="text-lg font-semibold">Evidence Inspector</h2>
              <p className="mt-1 text-sm text-slate-500">
                Calculation lineage and source records
              </p>
            </div>

            <div className="inspector-body">
              {selectedEvidenceId ? (
                <SourceVerification
                  key={`${version}-${selectedEvidenceId}`}
                  version={version}
                  evidenceId={selectedEvidenceId}
                  onClose={closeEvidence}
                  onOpenDocument={(id) => void selectDocument(id)}
                />
              ) : inspectorLoading ? (
                <p className="text-sm text-slate-500">
                  Loading supporting evidence...
                </p>
              ) : selectedDocument ? (
                <DocumentInspector
                  key={`${version}-${selectedDocument.id}`}
                  document={selectedDocument}
                  version={version}
                  onBack={() => setSelectedDocument(null)}
                  onNavigate={openReference}
                />
              ) : selectedReference ? (
                <EvidenceResolver
                  key={`${version}-${selectedReference}`}
                  reference={selectedReference}
                  version={version}
                  onNavigate={openReference}
                />
              ) : lineage ? (
                <>
                  <ReturnLineContext
                    key={`${version}-${lineage.key}`}
                    lineage={lineage}
                    version={version}
                    onReference={openReference}
                    onFinding={(id) =>
                      navigation?.navigate("reconciliation", id)
                    }
                  />
                  <LineageNode
                    node={lineage}
                    onOpenDocument={selectDocument}
                    onOpenEvidence={openEvidence}
                    onOpenReference={openReference}
                  />
                </>
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
                  <h3 className="font-semibold">Explore the evidence</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Select a return line or review finding. Then click an
                    evidence reference to verify it against the simulated source
                    document.
                  </p>
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function LineageNode({
  node,
  onOpenDocument,
  onOpenEvidence,
  onOpenReference,
}: {
  node: Lineage;
  onOpenDocument: (id: string) => void;
  onOpenEvidence: (id: string) => void;
  onOpenReference: (ref: string) => void;
}) {
  if (node.missing || node.cycle) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
        {node.key}: {node.missing ? "Missing input" : "Cycle detected"}
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
          <p className="mt-1 text-sm font-medium">{node.label}</p>
        </div>
        <span className="font-mono text-sm font-semibold">
          {money(node.value)}
        </span>
      </div>

      {node.rule && (
        <p className="mt-2 text-xs text-slate-400">Rule: {node.rule}</p>
      )}

      {(node.sources ?? []).map((source, index: number) => {
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
              <button
                className="break-all text-left font-mono text-xs text-indigo-700 underline"
                onClick={() => onOpenReference(ref)}
              >
                {ref}
              </button>
            )}

            {source.evidence && (
              <>
                <p className="mt-2 text-sm font-medium">
                  {source.evidence.label}
                </p>
                <p className="mt-1 text-sm">
                  Extracted: {String(source.evidence.value ?? "—")}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Confidence:{" "}
                  {typeof source.evidence.confidence === "number"
                    ? `${Math.round(source.evidence.confidence * 100)}%`
                    : "—"}
                </p>
              </>
            )}

            {source.document && (
              <button
                type="button"
                onClick={() =>
                  source.document && onOpenDocument(source.document.id)
                }
                className="mt-3 text-left text-sm font-medium text-indigo-600 hover:underline"
              >
                Open {source.document.id}: {source.document.title}
              </button>
            )}

            {source.type === "external_reference" && (
              <p className="mt-1 text-xs text-amber-700">
                {source.resolution?.status === "resolved"
                  ? `Resolved ${source.resolution.type}`
                  : (source.resolution?.reason ??
                    "Reference resolution unavailable")}
              </p>
            )}
          </div>
        );
      })}

      {(node.inputs ?? []).length > 0 && (
        <div className="mt-4 border-l-2 border-indigo-100 pl-3">
          <p className="mb-3 text-xs font-semibold uppercase text-slate-400">
            Calculation inputs
          </p>
          {(node.inputs ?? []).map((input, index: number) => (
            <LineageNode
              key={`${input.key}-${index}`}
              node={input}
              onOpenDocument={onOpenDocument}
              onOpenEvidence={onOpenEvidence}
              onOpenReference={onOpenReference}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <FirmWorkflow>
      <Home />
    </FirmWorkflow>
  );
}
