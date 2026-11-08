"use client";
import { RecordDetails } from "./ui/primitives";
import { useEffect, useRef, useState } from "react";
import {
  evidenceRequest,
  evidenceButton as button,
  evidenceControl as control,
  type EvidenceGraph,
} from "./evidence-types";
import EvidenceResolver from "./EvidenceResolver";
import SourceVerification from "./SourceVerification";
import DocumentInspector from "./DocumentInspector";
import type { SourceDocument } from "./workpaper-types";
import { useWorkpaperIdentity } from "./session";

type Line = {
  key: string;
  label: string;
  value: unknown;
  rule?: string;
  note?: string;
};
type Delta = {
  key: string;
  change: string;
  old: Line | null;
  new: Line | null;
  numeric_difference: string | null;
  dollar_difference: string | null;
  percent_difference: string | null;
  percentage_reason: string | null;
  reasons?: unknown;
  support?: Record<string, { document_ids: string[]; refs: string[] }>;
};
type Comparison = {
  before: string;
  after: string;
  lines: Delta[];
  counts: Record<string, number>;
  version_matrix: {
    key: string;
    values: Record<
      string,
      { present: boolean; value: unknown; label?: string }
    >;
  }[];
  diagnostics: unknown[];
  findings: unknown[];
  adjustments: unknown;
  review_scope: string;
  warning: string;
  versions: {
    version: string;
    summary: unknown;
    computed_at: string;
    trigger: string;
  }[];
};
type Scenario = {
  id: string;
  description: string;
  compatible: boolean;
  compatibility_reason: string;
  choices: Record<string, string>;
  federal: {
    base: Record<string, unknown>;
    alternative: Record<string, unknown>;
    total_tax_change: number;
    penalty_change?: number;
  };
  california: Scenario["federal"];
  changed_lines: { key: string; old: unknown; new: unknown }[];
  baseline_checks: unknown[];
  effect_checks: unknown;
  support: Record<string, { document_ids: string[] }>;
};
type Scenarios = {
  alternatives: Scenario[];
  selected: Scenario[];
  conflicts: unknown[];
  unknown: string[];
  warnings: string[];
  combined_result: null;
  selection_valid: boolean;
  extension: unknown;
  extension_compatible: boolean;
};
type Replay = {
  as_of: string;
  active_version: string | null;
  documents: { id: string; title: string; received_at: string }[];
  versions: { version: string }[];
  events: {
    id: string;
    at: string;
    event: string;
    detail: string | null;
    refs: string[];
    origin: string;
  }[];
  communications: Record<string, unknown[]>;
  lines: Line[];
  withheld_lines: { key: string; reason: string }[];
  findings: unknown[];
  corrections: unknown[];
  verification_activity: unknown[];
  review_activity: unknown[];
  workflow_activity: unknown[];
  adjustments: unknown[];
  summary: unknown;
  warning: string;
  independent_findings: string;
};
type Impact = {
  affected_lines: string[];
  areas: string[];
  findings: unknown[];
  unresolved: string[];
  approvals: unknown[];
  assessments: unknown[];
  events: unknown[];
  warning: string;
};
type Analysis = {
  id: string;
  revision: number;
  state: string;
  data: { note: string; scenario_ids: string[]; version: string };
};
const versions = ["v1", "v2", "v3"];
const view = (value: unknown) =>
  value === undefined
    ? "Not supplied"
    : value === null
      ? "—"
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);
const Json = ({ value }: { value: unknown }) => <RecordDetails value={value} />;

export default function ChangeAnalysisWorkspace({
  section,
  onSectionChange,
}: {
  section?: string;
  onSectionChange?: (section: string) => void;
}) {
  const [localTab, setLocalTab] = useState("Version Comparison");
  const tab = section ?? localTab;
  const setTab = (next: string) => {
    setLocalTab(next);
    onSectionChange?.(next);
  };
  return (
    <section
      className="feature-workspace space-y-4"
      data-testid="change-analysis-workspace"
    >
      <header>
        <h2 className="text-xl font-semibold">Change Analysis</h2>
        <p className="text-sm text-slate-600">
          Compare original engine snapshots, explore supplied alternatives, and
          replay time-bounded evidence. Each view identifies its context.
        </p>
      </header>
      <nav className="segmented-tabs" hidden={!!section}>
        {[
          "Version Comparison",
          "What-if Analysis",
          "Timeline Replay",
          "Change Impact",
        ].map((t) => (
          <button
            className={button + (tab === t ? " bg-indigo-100" : "")}
            key={t}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </nav>
      {tab === "Version Comparison" ? (
        <VersionComparison />
      ) : tab === "What-if Analysis" ? (
        <WhatIf />
      ) : tab === "Timeline Replay" ? (
        <TimelineReplay />
      ) : (
        <ChangeImpact />
      )}
    </section>
  );
}
function VersionComparison() {
  const [before, setBefore] = useState("v1");
  const [after, setAfter] = useState("v3");
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [all, setAll] = useState(false);
  const [selected, setSelected] = useState<Delta | null>(null);
  const [evidence, setEvidence] = useState<{
    ref: string;
    version: string;
  } | null>(null);
  useEffect(() => {
    let active = true;
    evidenceRequest<Comparison>(
      `/api/version-comparison?before=${before}&after=${after}`,
    )
      .then((d) => {
        if (active) {
          setData(d);
          setSelected(null);
          setError("");
        }
      })
      .catch((e) => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, [before, after]);
  const delta = new Map(data?.lines.map((l) => [l.key, l]));
  return (
    <div className="space-y-3">
      <p className="rounded bg-blue-50 p-3 font-medium">
        Stored engine snapshots · current reviews shown separately · no tax
        recomputation
      </p>
      <div className="flex flex-wrap gap-3">
        <label>
          Compare from{" "}
          <select
            aria-label="Compare from"
            className={control}
            value={before}
            onChange={(e) => {
              setBefore(e.target.value);
              setData(null);
              setEvidence(null);
            }}
          >
            {versions.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Compare to{" "}
          <select
            aria-label="Compare to"
            className={control}
            value={after}
            onChange={(e) => {
              setAfter(e.target.value);
              setData(null);
              setEvidence(null);
            }}
          >
            {versions.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <input
          aria-label="Compare line search"
          placeholder="Find a return line"
          className={control}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label>
          <input
            type="checkbox"
            checked={all}
            onChange={(e) => setAll(e.target.checked)}
          />{" "}
          Show unchanged and other-version lines
        </label>
      </div>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p>Comparing stored versions…</p>}
      {data && (
        <>
          <p data-testid="comparison-counts">
            {Object.entries(data.counts)
              .map(([k, v]) => `${k}: ${v}`)
              .join(" · ")}
          </p>
          <details>
            <summary>All three version summaries and triggers</summary>
            <div className="grid gap-3 md:grid-cols-3">
              {data.versions.map((v) => (
                <article key={v.version}>
                  <h3>
                    {v.version} · {v.computed_at}
                  </h3>
                  <p>{v.trigger}</p>
                  <Json value={v.summary} />
                </article>
              ))}
            </div>
          </details>
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  {[
                    "Return line",
                    "Change",
                    ...versions,
                    `Δ ${before} → ${after}`,
                    "% change",
                    "Inspect",
                  ].map((h) => (
                    <th className="p-2" key={h}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.version_matrix
                  .filter(
                    (row) =>
                      (all ||
                        (delta.get(row.key)?.change !== "unchanged" &&
                          delta.has(row.key))) &&
                      (
                        row.key +
                        " " +
                        Object.values(row.values)
                          .map((v) => v.label ?? "")
                          .join(" ")
                      )
                        .toLowerCase()
                        .includes(search.toLowerCase()),
                  )
                  .map((row) => {
                    const d = delta.get(row.key);
                    return (
                      <tr
                        className="border-t"
                        key={row.key}
                        data-testid={`comparison-${row.key}`}
                      >
                        <td className="p-2">
                          {row.key}
                          <small className="block">
                            {row.values[after]?.label ??
                              row.values[before]?.label}
                          </small>
                        </td>
                        <td>{d?.change ?? "outside selected pair"}</td>
                        {versions.map((v) => (
                          <td className="p-2" key={v}>
                            {row.values[v].present
                              ? view(row.values[v].value)
                              : "Absent"}
                            {row.values[v].present && (
                              <button
                                aria-label={`Inspect ${row.key} ${v}`}
                                className="ml-2 text-indigo-700 underline"
                                onClick={() =>
                                  setEvidence({ ref: row.key, version: v })
                                }
                              >
                                ↗
                              </button>
                            )}
                          </td>
                        ))}
                        <td>
                          {d?.dollar_difference !== null &&
                          d?.dollar_difference !== undefined
                            ? "$" + d.dollar_difference
                            : (d?.numeric_difference ?? "—")}
                        </td>
                        <td title={d?.percentage_reason ?? ""}>
                          {d?.percent_difference === null ||
                          d?.percent_difference === undefined
                            ? "Undefined / nonnumeric"
                            : Number(d.percent_difference).toFixed(2) + "%"}
                        </td>
                        <td>
                          {d && (
                            <button
                              className={button}
                              onClick={() => setSelected(d)}
                            >
                              Change details {row.key}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
          {selected && (
            <article className="workflow-card">
              <h3 className="font-semibold">Change details: {selected.key}</h3>
              <Json
                value={selected.reasons ?? "No packet explanation supplied."}
              />
              {Object.entries(selected.support ?? {}).map(([v, support]) => (
                <div key={v}>
                  <strong>{v} supporting documents</strong>
                  {support.document_ids.map((id) => (
                    <button
                      className={button}
                      key={id}
                      onClick={() => setEvidence({ ref: id, version: v })}
                    >
                      {id} · {v}
                    </button>
                  ))}
                </div>
              ))}
            </article>
          )}
          <details>
            <summary>Diagnostic changes</summary>
            <Json
              value={data.diagnostics.filter(
                (d) => (d as { change: string }).change !== "unchanged",
              )}
            />
          </details>
          <details>
            <summary>Finding and current review changes</summary>
            <p>{data.review_scope}</p>
            <Json
              value={data.findings.filter(
                (f) => (f as { change: string }).change !== "unchanged",
              )}
            />
          </details>
          <details>
            <summary>Current adjustment ledgers by baseline</summary>
            <Json value={data.adjustments} />
          </details>
          <p className="text-sm">{data.warning}</p>
        </>
      )}
      {evidence && (
        <aside className="rounded border border-indigo-200">
          <h3 className="p-3 font-semibold">
            {evidence.version} lineage and source evidence
          </h3>
          <CurrentEvidence
            key={evidence.version + evidence.ref}
            version={evidence.version}
            reference={evidence.ref}
            onNavigate={(ref) => setEvidence({ ...evidence, ref })}
            onClose={() => setEvidence(null)}
          />
        </aside>
      )}
    </div>
  );
}
function CurrentEvidence({
  reference,
  version,
  onNavigate,
  onClose,
}: {
  reference: string;
  version: string;
  onNavigate: (ref: string) => void;
  onClose: () => void;
}) {
  const [document, setDocument] = useState<SourceDocument | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (/^D\d+$/.test(reference))
      evidenceRequest<SourceDocument>("/api/documents/" + reference)
        .then((d) => active && setDocument(d))
        .catch((e) => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, [reference]);
  if (reference.startsWith("ev-"))
    return (
      <SourceVerification
        evidenceId={reference}
        version={version}
        onClose={onClose}
        onOpenDocument={onNavigate}
      />
    );
  if (/^D\d+$/.test(reference))
    return document ? (
      <DocumentInspector
        document={document}
        version={version}
        onBack={onClose}
        onNavigate={onNavigate}
      />
    ) : (
      <p>{error || "Loading source document…"}</p>
    );
  return (
    <EvidenceResolver
      reference={reference}
      version={version}
      onNavigate={onNavigate}
    />
  );
}
function WhatIf() {
  const identity = useWorkpaperIdentity();
  const [version, setVersion] = useState("v3");
  const [ids, setIds] = useState<string[]>([]);
  const [data, setData] = useState<Scenarios | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<Analysis[]>([]);
  const [audit, setAudit] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    evidenceRequest<Scenarios>("/api/what-if/compare", {
      version,
      scenario_ids: ids,
    })
      .then((d) => {
        if (active) {
          setData(d);
          setError("");
        }
      })
      .catch((e) => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, [version, ids]);
  async function save() {
    setBusy(true);
    setError("");
    try {
      await evidenceRequest("/api/what-if/analyses", {
        version,
        scenario_ids: ids,
        note,
        expected_revision: 0,
      });
      const history = await evidenceRequest<{
        analyses: Analysis[];
        events: unknown[];
      }>("/api/what-if/analyses");
      setSaved(history.analyses);
      setAudit(history.events);
      setMessage(
        "Saved hypothetical analysis; no tax adjustment or approval was created.",
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function history() {
    try {
      const h = await evidenceRequest<{
        analyses: Analysis[];
        events: unknown[];
      }>("/api/what-if/analyses");
      setSaved(h.analyses);
      setAudit(h.events);
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <div className="space-y-3">
      <p className="rounded bg-purple-50 p-3 font-semibold">
        Hypothetical alternatives · supplied engine results · never approved
        corrections
      </p>
      <label>
        Scenario baseline{" "}
        <select
          aria-label="Scenario baseline"
          className={control}
          value={version}
          onChange={(e) => {
            setVersion(e.target.value);
            setData(null);
            setMessage("");
          }}
        >
          {versions.map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {data && (
        <>
          <div className="grid gap-2 md:grid-cols-2">
            {data.alternatives.map((a) => (
              <label key={a.id} className="workflow-card">
                <input
                  aria-label={`Scenario ${a.id}`}
                  type="checkbox"
                  checked={ids.includes(a.id)}
                  onChange={(e) => {
                    setIds(
                      e.target.checked
                        ? [...ids, a.id]
                        : ids.filter((id) => id !== a.id),
                    );
                    setData(null);
                    setMessage("");
                  }}
                />{" "}
                {a.description}
                <small className="block">
                  {a.id} ·{" "}
                  {a.compatible
                    ? "Compatible with original " + version
                    : "INCOMPATIBLE: " + a.compatibility_reason}
                </small>
              </label>
            ))}
          </div>
          <div
            className="rounded bg-amber-50 p-3"
            data-testid="scenario-warnings"
          >
            {data.warnings.map((w) => (
              <p className="text-sm" key={w}>
                {w}
              </p>
            ))}
            <p>
              No combined result is supplied; individual effects must not be
              summed.
            </p>
            {data.conflicts.length > 0 && (
              <>
                <strong>Conflicting alternatives</strong>
                <Json value={data.conflicts} />
              </>
            )}
          </div>
          {data.selected.map((a) => (
            <article className="space-y-2 rounded border p-3" key={a.id}>
              <h3 className="font-semibold">{a.description}</h3>
              <p>{a.compatibility_reason}</p>
              <Json value={a.choices} />
              <div className="grid gap-3 md:grid-cols-2">
                {(["federal", "california"] as const).map((j) => (
                  <section key={j}>
                    <h4 className="font-semibold">
                      {j} · tax effect {view(a[j].total_tax_change)} · penalty
                      effect {view(a[j].penalty_change)}
                    </h4>
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr>
                          <th>Metric</th>
                          <th>Baseline engine</th>
                          <th>Alternative engine</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.keys(a[j].base).map((k) => (
                          <tr key={k}>
                            <td>{k}</td>
                            <td>{view(a[j].base[k])}</td>
                            <td>{view(a[j].alternative[k])}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </section>
                ))}
              </div>
              <details>
                <summary>Supplied changed lines and baseline checks</summary>
                <Json
                  value={{
                    changed_lines: a.changed_lines,
                    checks: a.baseline_checks,
                    effects: a.effect_checks,
                    support: a.support,
                  }}
                />
              </details>
            </article>
          ))}
          <label className="block">
            Analysis note{" "}
            <textarea
              aria-label="Scenario analysis note"
              className={control + " w-full"}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <button
            className={button}
            disabled={
              busy ||
              !identity ||
              !ids.length ||
              !data.selection_valid ||
              !note.trim()
            }
            onClick={() => void save()}
          >
            Save hypothetical analysis
          </button>
          <button className={button} onClick={() => void history()}>
            Load saved analyses and history
          </button>
          <details>
            <summary>April extension estimate (stored v2 result)</summary>
            <p>
              Compatible baseline: {String(data.extension_compatible)}. This is
              historical evidence; viewing it does not file an extension or
              record a payment.
            </p>
            <Json value={data.extension} />
          </details>
        </>
      )}
      {saved.length > 0 && (
        <section>
          <h3>Saved hypothetical analyses</h3>
          {saved.map((a) => (
            <article key={a.id}>
              {a.id} · {a.data.version} · {a.state} ·{" "}
              {a.data.scenario_ids.join(", ")} · {a.data.note}
            </article>
          ))}
        </section>
      )}
      {audit !== null && (
        <details open>
          <summary>Scenario audit history</summary>
          <Json value={audit} />
        </details>
      )}
    </div>
  );
}
function TimelineReplay() {
  const [at, setAt] = useState("2026-03-04T09:12");
  const [data, setData] = useState<Replay | null>(null);
  const [graph, setGraph] = useState<EvidenceGraph | null>(null);
  const [reference, setReference] = useState("");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const generation = useRef(0);
  async function replay() {
    const g = ++generation.current;
    setData(null);
    setGraph(null);
    setError("");
    try {
      const result = await evidenceRequest<Replay>(
        "/api/timeline-replay?at=" +
          encodeURIComponent(at.length === 16 ? at + ":00Z" : at + "Z"),
      );
      if (g === generation.current) setData(result);
    } catch (e) {
      if (g === generation.current) setError(String(e));
    }
  }
  async function resolve(ref: string) {
    const g = ++generation.current;
    setGraph(null);
    setError("");
    setReference(ref);
    try {
      const result = await evidenceRequest<EvidenceGraph>(
        "/api/timeline-replay/evidence?at=" +
          encodeURIComponent(data!.as_of) +
          "&ref=" +
          encodeURIComponent(ref),
      );
      if (g === generation.current) setGraph(result);
    } catch (e) {
      if (g === generation.current) setError(String(e));
    }
  }
  return (
    <div className="space-y-3">
      <p className="rounded bg-amber-50 p-3 font-semibold">
        Historical replay · read only · current approvals and readiness remain
        separate
      </p>
      <label>
        Known at (UTC){" "}
        <input
          type="datetime-local"
          step="1"
          aria-label="Replay time UTC"
          className={control}
          value={at}
          onChange={(e) => {
            setAt(e.target.value);
            generation.current++;
            setData(null);
            setGraph(null);
          }}
        />
      </label>
      <button className={button} onClick={() => void replay()}>
        Replay selected time
      </button>
      {error && <p role="alert">{error}</p>}
      {data && (
        <>
          <p data-testid="replay-context">
            As of {data.as_of} · engine baseline{" "}
            {data.active_version ?? "not yet computed"} ·{" "}
            {data.documents.length} documents available
          </p>
          <p className="text-sm">{data.warning}</p>
          <div className="grid gap-4 lg:grid-cols-2">
            <section>
              <h3 className="font-semibold">Known documents</h3>
              <div
                className="max-h-72 overflow-auto"
                data-testid="replay-documents"
              >
                {data.documents.map((d) => (
                  <button
                    className={button + " mb-1 block text-left"}
                    key={d.id}
                    onClick={() => void resolve(d.id)}
                  >
                    {d.id} · {d.title} · {d.received_at}
                  </button>
                ))}
              </div>
              <h3 className="mt-3 font-semibold">
                Events available at this time
              </h3>
              <ol
                className="max-h-80 overflow-auto"
                data-testid="replay-events"
              >
                {data.events.map((e) => (
                  <li className="my-2 rounded border p-2 text-xs" key={e.id}>
                    <strong>
                      {e.at} · {e.event}
                    </strong>
                    <p>{e.origin} · never completes live workflow</p>
                    <p>{e.detail}</p>
                    {e.refs.map((ref) => (
                      <button
                        className={button}
                        key={ref}
                        onClick={() => void resolve(ref)}
                      >
                        {ref}
                      </button>
                    ))}
                  </li>
                ))}
              </ol>
            </section>
            <section>
              <h3 className="font-semibold">Historical evidence inspector</h3>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void resolve(reference);
                }}
              >
                <input
                  aria-label="Replay evidence reference"
                  className={control}
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                />
                <button className={button}>Resolve historical evidence</button>
              </form>
              {graph && (
                <div data-testid="historical-evidence">
                  <p>
                    {graph.resolution.status} ·{" "}
                    {graph.resolution.reason_code ?? graph.resolution.type}
                  </p>
                  <p>{graph.resolution.reason}</p>
                  <Json value={graph.resolution.value} />
                  {graph.resolution.related_refs.map((ref) => (
                    <button
                      className={button}
                      key={ref}
                      onClick={() => void resolve(ref)}
                    >
                      {ref}
                    </button>
                  ))}
                  {graph.document_ids.map((id) => (
                    <button
                      className={button}
                      key={id}
                      onClick={() => void resolve(id)}
                    >
                      Open historical {id}
                    </button>
                  ))}
                </div>
              )}
            </section>
          </div>
          <details>
            <summary>Known stored-version corrections</summary>
            <Json value={data.corrections} />
          </details>
          <details>
            <summary>Known client communications</summary>
            <Json value={data.communications} />
          </details>
          <details>
            <summary>
              Stored engine summary (not independently verified)
            </summary>
            <Json value={data.summary} />
          </details>
          <details>
            <summary>
              Time-eligible return lines ({data.lines.length}) and withheld
              dependencies ({data.withheld_lines.length})
            </summary>
            <input
              className={control}
              aria-label="Historical line search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {data.lines
              .filter((l) =>
                (l.key + " " + l.label)
                  .toLowerCase()
                  .includes(search.toLowerCase()),
              )
              .map((l) => (
                <button
                  className={button + " m-1"}
                  key={l.key}
                  onClick={() => void resolve(l.key)}
                >
                  {l.key} · {view(l.value)}
                </button>
              ))}
            <Json value={data.withheld_lines} />
          </details>
          <details>
            <summary>Historical diagnostics and actual review activity</summary>
            <p>{data.independent_findings}</p>
            <Json
              value={{
                diagnostics: data.findings,
                actual_reviews: data.review_activity,
                actual_field_verifications: data.verification_activity,
                actual_workflow: data.workflow_activity,
                actual_adjustments: data.adjustments,
              }}
            />
          </details>
        </>
      )}
    </div>
  );
}
function ChangeImpact() {
  const identity = useWorkpaperIdentity();
  const [ref, setRef] = useState("SchC.1");
  const [data, setData] = useState<Impact | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  async function preview() {
    setError("");
    setData(null);
    try {
      setData(
        await evidenceRequest<Impact>(
          "/api/change-impact?ref=" + encodeURIComponent(ref),
        ),
      );
    } catch (e) {
      setError(String(e));
    }
  }
  async function reassess() {
    setError("");
    try {
      setData(
        await evidenceRequest<Impact>("/api/change-impact/reassess", {
          version: "v3",
          refs: [ref],
          note,
        }),
      );
      setMessage(
        "Impact assessment recorded. Historical decisions are preserved; dependent approvals are rechecked transactionally.",
      );
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <div className="space-y-3">
      <p className="rounded bg-blue-50 p-3 font-semibold">
        Current workpaper dependency impact · preview does not apply a tax
        change
      </p>
      <label>
        Changed reference{" "}
        <input
          aria-label="Change impact reference"
          className={control}
          value={ref}
          onChange={(e) => {
            setRef(e.target.value);
            setData(null);
          }}
        />
      </label>
      <button className={button} onClick={() => void preview()}>
        Preview change impact
      </button>
      <p className="text-xs">
        Use a return line, document, extracted evidence reference, or
        policy:current.
      </p>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {data && (
        <>
          <p data-testid="impact-areas">
            Affected areas: {data.areas.join(", ") || "No supported path"}
          </p>
          <p>{data.affected_lines.length} affected return lines</p>
          <p>{data.warning}</p>
          {data.unresolved.length > 0 && (
            <p>Unresolved references: {data.unresolved.join(", ")}</p>
          )}
          <details>
            <summary>Affected return lines</summary>
            <Json value={data.affected_lines} />
          </details>
          <details>
            <summary>Dependent findings</summary>
            <Json value={data.findings} />
          </details>
          <details open>
            <summary>Approval validity</summary>
            <div data-testid="impact-approvals">
              <Json value={data.approvals} />
            </div>
          </details>
          <details>
            <summary>Review reassessment status</summary>
            <Json value={data.assessments} />
          </details>
          <details>
            <summary>Append-only change and approval history</summary>
            <Json value={data.events} />
          </details>
          <textarea
            aria-label="Impact assessment note"
            className={control + " w-full"}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Document why this impact assessment was performed"
          />
          <button
            className={button}
            disabled={
              !identity ||
              !["reviewer", "partner"].includes(identity.role) ||
              !note.trim()
            }
            onClick={() => void reassess()}
          >
            Record impact reassessment
          </button>
        </>
      )}
    </div>
  );
}
