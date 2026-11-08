"use client";
import { Pagination, StatusBadge, EmptyState } from "./ui/primitives";
import { useAppNavigation } from "./shell/navigation";
import { useWorkpaperIdentity } from "@/components/session";
import { useEffect, useMemo, useState } from "react";
import {
  evidenceRequest,
  evidenceControl as control,
  evidenceButton as button,
} from "./evidence-types";

type Input = {
  label: string;
  value: unknown;
  ref: string;
  kind: string;
  available_after_engine?: boolean;
  available_at?: string | null;
  raw: string | null;
  location: { start: number; end: number } | null;
};
type Check = {
  id: string;
  area: string;
  title: string;
  target: string | null;
  method: string;
  check_type: string;
  jurisdiction: string;
  expected_value: string | null;
  expected_unrounded?: string;
  reported_value: string | null;
  difference: string | null;
  tolerance: string | null;
  rounding_quantum?: string;
  tolerance_basis?: string;
  conclusion: string;
  reason: string;
  inputs: Input[];
  steps: { description: string; result: unknown }[];
  refs: string[];
  materiality: string | Record<string, unknown>;
};
type Adjustment = {
  id: string;
  state: string;
  payload: { target: string; proposed_value: string };
  stale: boolean;
};
type Finding = {
  id: string;
  issue_key: string;
  title: string;
  description: string;
  origin: string;
  origins: string[];
  severity: string;
  tax_year: number;
  jurisdiction: string;
  area: string;
  refs: string[];
  status: string;
  review_note: string;
  reconciliations: string[];
  aliases: string[];
  adjustment_links: Adjustment[];
  review_validity?: { state: string; data: { reason: string } };
};
type Dashboard = {
  version: string;
  findings: Finding[];
  checks: Check[];
  total: number;
  standards: { flag_if_change_over_percent: number; and_over_amount: number };
  note: string;
};
type Audit = {
  events: {
    id: number;
    new_status: string;
    note: string;
    actor_name: string;
    created_at: string;
  }[];
  decisions: {
    id: number;
    disposition: string;
    authority: string;
    actor_id: string;
  }[];
};
type Staff = { id: string; name: string; role: string; active_from: string };

export default function ReconciliationDashboard({
  version,
  onNavigate,
  onOpenAdjustment,
}: {
  version: string;
  onNavigate: (ref: string) => void;
  onOpenAdjustment: (id: string) => void;
}) {
  const navigation = useAppNavigation();
  const [page, setPage] = useState(0);
  const [data, setData] = useState<Dashboard | null>(null);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedCheck, setSelectedCheck] = useState<string | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [area, setArea] = useState("all");
  const [jurisdiction, setJurisdiction] = useState("all");
  const [severity, setSeverity] = useState("all");
  const [search, setSearch] = useState("");
  const identity = useWorkpaperIdentity();
  const [legacyActor, setActor] = useState("st-02");
  const actor = identity?.id ?? legacyActor;
  const [status, setStatus] = useState("in_review");
  const [disposition, setDisposition] = useState("investigating");
  const [note, setNote] = useState("");
  const [authority, setAuthority] = useState("");
  const [adjustmentId, setAdjustmentId] = useState("");
  const [linkId, setLinkId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const finding = data?.findings.find((f) => f.id === selected);
  const check =
    data?.checks.find((c) => c.id === selectedCheck) ??
    data?.checks.find((c) => finding?.reconciliations.includes(c.id));
  const grouped = useMemo(() => {
    const groups: Record<string, Finding[]> = {};
    for (const f of data?.findings ?? []) {
      if (
        (area !== "all" && f.area !== area) ||
        (jurisdiction !== "all" && f.jurisdiction !== jurisdiction) ||
        (severity !== "all" && f.severity !== severity) ||
        !`${f.title} ${f.id} ${f.issue_key}`
          .toLowerCase()
          .includes(search.toLowerCase())
      )
        continue;
      const key = `${f.area} · ${f.jurisdiction} · ${f.severity}`;
      (groups[key] ??= []).push(f);
    }
    return groups;
  }, [data, area, jurisdiction, severity, search]);
  const filteredFindings = Object.values(grouped).flat();
  const pageFindings = filteredFindings.slice(page * 20, (page + 1) * 20);
  useEffect(() => {
    let active = true;
    Promise.all([
      evidenceRequest<Dashboard>(`/api/unified-findings?version=${version}`),
      evidenceRequest<{ staff: Staff[] }>("/api/verification-metadata"),
    ])
      .then(([dashboard, metadata]) => {
        if (active) {
          setData(dashboard);
          const linked = dashboard.findings.find(
            (f) =>
              f.id === navigation?.reference ||
              f.issue_key === navigation?.reference,
          );
          if (linked) {
            setSelected(linked.id);
            setSelectedCheck(linked.reconciliations[0] ?? null);
          }
          setStaff(metadata.staff);
        }
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [version, navigation?.reference]);
  async function refresh(id?: string) {
    setData(
      await evidenceRequest<Dashboard>(
        `/api/unified-findings?version=${version}`,
      ),
    );
    if (id)
      setAudit(
        await evidenceRequest<Audit>(
          `/api/unified-findings/${encodeURIComponent(id)}/history?version=${version}`,
        ),
      );
  }
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Reconciliation action failed",
      );
    } finally {
      setBusy(false);
    }
  }
  function select(f: Finding) {
    setSelected(f.id);
    setSelectedCheck(f.reconciliations[0] ?? null);
    setNote(f.review_note);
    setAudit(null);
    setMessage("");
    setAdjustmentId("");
    void run(async () =>
      setAudit(
        await evidenceRequest<Audit>(
          `/api/unified-findings/${encodeURIComponent(f.id)}/history?version=${version}`,
        ),
      ),
    );
  }
  async function saveDecision() {
    if (!finding) return;
    await run(async () => {
      await evidenceRequest(
        `/api/reconciliation-decision?version=${version}&finding_id=${encodeURIComponent(finding.id)}`,
        {
          actor_id: actor,
          status,
          disposition,
          note,
          authority,
          refs: finding.refs.filter((r) => !r.startsWith("F8949.MISSING.")),
          adjustment_id: adjustmentId || null,
        },
      );
      await refresh(finding.id);
      setMessage("Documented reconciliation decision saved.");
    });
  }
  async function createCorrection() {
    if (!check) return;
    await run(async () => {
      const adjustment = await evidenceRequest<Adjustment>(
        `/api/reconciliations/${encodeURIComponent(check.id)}/adjustment?version=${version}`,
        { actor_id: actor, note, authority },
      );
      await refresh(finding?.id);
      setMessage(
        `Draft correction linked: ${adjustment.id}. Independent adjustment approval is still required.`,
      );
    });
  }
  return (
    <div className="space-y-4 p-5" data-testid="reconciliation-dashboard">
      <p className="rounded bg-amber-50 p-3 text-sm">
        Original engine values remain unchanged. A resolved review is a
        documented CPA decision, not an automatic correction or a completed tax
        recomputation.
      </p>
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
      {!data && !error && <p>Loading independent reconciliations…</p>}
      {data && (
        <>
          <p className="text-sm">
            {data.checks.length} reproducible checks · {data.total} unified
            issues · prior-year standard: over{" "}
            {data.standards.flag_if_change_over_percent}% and $
            {data.standards.and_over_amount}. No general reconciliation
            materiality is specified.
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            {(
              [
                [
                  "Tax area",
                  area,
                  setArea,
                  [...new Set(data.findings.map((f) => f.area))],
                ],
                [
                  "Jurisdiction",
                  jurisdiction,
                  setJurisdiction,
                  [...new Set(data.findings.map((f) => f.jurisdiction))],
                ],
                [
                  "Severity",
                  severity,
                  setSeverity,
                  ["critical", "high", "medium", "info"],
                ],
              ] as const
            ).map(([label, value, setter, options]) => (
              <label className="text-xs" key={label}>
                {label}
                <select
                  aria-label={`Reconciliation ${label.toLowerCase()}`}
                  className={control}
                  value={value}
                  onChange={(e) => {
                    setter(e.target.value);
                    setPage(0);
                  }}
                >
                  <option value="all">All</option>
                  {options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <input
            aria-label="Find reconciliation issue"
            className={control}
            placeholder="Search issue or rule ID"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
          <div className="reconciliation-detail-layout">
            <div className="finding-table section-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Finding</th>
                    <th>Tax area</th>
                    <th>Severity</th>
                    <th>Review</th>
                  </tr>
                </thead>
                <tbody>
                  {pageFindings.map((f) => (
                    <tr
                      key={f.id}
                      className={selected === f.id ? "selected" : ""}
                    >
                      <td>
                        <button
                          className="line-select"
                          disabled={busy}
                          aria-label={`Inspect reconciliation ${f.issue_key}`}
                          onClick={() => select(f)}
                        >
                          <strong>{f.title}</strong>
                          <small>
                            {f.origins.join(" + ")} · {f.tax_year} ·{" "}
                            {f.jurisdiction}
                          </small>
                        </button>
                      </td>
                      <td>{f.area}</td>
                      <td>
                        <StatusBadge value={f.severity} />
                      </td>
                      <td>
                        <StatusBadge
                          value={
                            f.review_validity?.state === "needs_reassessment"
                              ? "needs_reassessment"
                              : f.status
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!filteredFindings.length && (
                <EmptyState title="No matching findings" />
              )}
              <Pagination
                page={page}
                pageSize={20}
                total={filteredFindings.length}
                onPage={setPage}
              />
            </div>
            <div className="reconciliation-record">
              <details>
                <summary className="text-sm font-semibold">
                  All checks, including matches and unsupported calculations
                </summary>
                <select
                  aria-label="Select reconciliation check"
                  className={control}
                  value={selectedCheck ?? ""}
                  onChange={(e) => {
                    setSelectedCheck(e.target.value);
                    const f = data.findings.find((item) =>
                      item.reconciliations.includes(e.target.value),
                    );
                    setSelected(f?.id ?? null);
                  }}
                >
                  <option value="">Choose a check</option>
                  {data.checks.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.id} · {c.conclusion}
                    </option>
                  ))}
                </select>
              </details>
              {check && (
                <section
                  className="space-y-3 rounded-xl border border-slate-200 p-3"
                  data-testid="reconciliation-calculation"
                >
                  <h3 className="font-semibold">{check.title}</h3>
                  <p className="text-xs font-semibold">
                    {check.id} · {check.check_type} · {check.jurisdiction}
                  </p>
                  <p className="text-sm">{check.method}</p>
                  <p
                    className="text-sm"
                    data-testid="reconciliation-conclusion"
                  >
                    {check.conclusion}
                  </p>
                  <p className="text-xs">{check.reason}</p>
                  <div className="overflow-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr>
                          <th>Expected</th>
                          <th>Reported engine/source</th>
                          <th>Difference (reported − expected)</th>
                          <th>Tolerance</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td data-testid="reconciliation-expected">
                            {check.expected_value ?? "Unsupported / unknown"}
                          </td>
                          <td data-testid="reconciliation-reported">
                            {check.reported_value ?? "Missing"}
                          </td>
                          <td data-testid="reconciliation-difference">
                            {check.difference ?? "Not computed"}
                          </td>
                          <td>{check.tolerance ?? "Not specified"}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p className="text-xs text-slate-500">
                    {check.tolerance_basis}{" "}
                    {check.rounding_quantum &&
                      `Display quantum: ${check.rounding_quantum}.`}
                  </p>
                  {check.target && (
                    <button
                      className={button}
                      onClick={() => onNavigate(check.target!)}
                    >
                      Open return line {check.target}
                    </button>
                  )}
                  <h4 className="text-sm font-semibold">
                    Preserved inputs and source evidence
                  </h4>
                  <ul className="max-h-72 space-y-2 overflow-auto">
                    {check.inputs.map((input, i) => (
                      <li className="rounded bg-slate-50 p-2 text-xs" key={i}>
                        <p>
                          {input.label}:{" "}
                          {typeof input.value === "object"
                            ? JSON.stringify(input.value)
                            : String(input.value)}
                        </p>
                        <p>
                          {input.kind}
                          {input.available_after_engine &&
                            " · source received after this engine computation"}
                          {input.location &&
                            ` · offsets ${input.location.start}–${input.location.end}`}
                        </p>
                        <button
                          className="text-indigo-700 underline"
                          onClick={() => onNavigate(input.ref)}
                        >
                          {input.ref}
                        </button>
                        {input.raw && (
                          <p className="break-words">{input.raw}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                  <h4 className="text-sm font-semibold">Computation steps</h4>
                  <ol className="list-decimal space-y-1 pl-5 text-xs">
                    {check.steps.map((step, i) => (
                      <li key={i}>
                        {step.description}: {String(step.result)}
                      </li>
                    ))}
                  </ol>
                  <div className="flex flex-wrap gap-1">
                    {check.refs.map((ref) => (
                      <button
                        key={ref}
                        className={button}
                        onClick={() => onNavigate(ref)}
                      >
                        {ref}
                      </button>
                    ))}
                  </div>
                </section>
              )}
              {finding && (
                <section
                  className="space-y-3 rounded-xl border border-indigo-200 p-3"
                  data-testid="reconciliation-review"
                >
                  <h3 className="font-semibold">CPA review: {finding.title}</h3>
                  <p className="text-xs">
                    Stable ID: {finding.id}; current status:{" "}
                    <strong data-testid="reconciliation-review-status">
                      {finding.status}
                    </strong>
                  </p>
                  <p className="text-xs">{finding.description}</p>
                  {finding.review_validity?.state === "needs_reassessment" && (
                    <p className="rounded bg-amber-50 p-2 text-xs text-amber-900">
                      Prior resolution needs reassessment:{" "}
                      {finding.review_validity.data.reason}
                    </p>
                  )}
                  {finding.aliases.length > 0 && (
                    <p className="text-xs">
                      Merged issue aliases: {finding.aliases.join(", ")}
                    </p>
                  )}
                  <label className="block text-xs">
                    Reconciliation reviewer
                    <select
                      aria-label="Reconciliation reviewer"
                      className={control}
                      value={actor}
                      disabled={!!identity || busy}
                      onChange={(e) => setActor(e.target.value)}
                    >
                      {staff
                        .filter(
                          (s) =>
                            ["preparer", "reviewer", "partner"].includes(
                              s.role,
                            ) &&
                            s.active_from <=
                              new Date().toISOString().slice(0, 10),
                        )
                        .map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name} · {s.id}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="block text-xs">
                    Decision status
                    <select
                      aria-label="Reconciliation decision status"
                      className={control}
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                    >
                      {["open", "in_review", "resolved", "escalated"].map(
                        (s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                  <label className="block text-xs">
                    Disposition
                    <select
                      aria-label="Reconciliation disposition"
                      className={control}
                      value={disposition}
                      onChange={(e) => setDisposition(e.target.value)}
                    >
                      {[
                        "investigating",
                        "accepted_as_reported",
                        "professional_judgment",
                        "unsupported_acknowledged",
                        "correction_linked",
                      ].map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-xs">
                    Reconciliation notes
                    <textarea
                      aria-label="Reconciliation notes"
                      className={control}
                      maxLength={4000}
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                    />
                  </label>
                  <label className="block text-xs">
                    Authority and assumptions
                    <textarea
                      aria-label="Reconciliation authority"
                      className={control}
                      maxLength={4000}
                      value={authority}
                      onChange={(e) => setAuthority(e.target.value)}
                    />
                  </label>
                  <p className="text-xs">
                    Evidence references above open Phase 2 source inspection and
                    field verification.
                  </p>
                  <button
                    className={button}
                    disabled={busy || !note.trim() || !authority.trim()}
                    onClick={() => void saveDecision()}
                  >
                    Save reconciliation decision
                  </button>
                  <h4 className="text-sm font-semibold">
                    Linked Phase 1 corrections
                  </h4>
                  {finding.adjustment_links.map((a) => (
                    <div className="space-y-1 text-xs" key={a.id}>
                      <button
                        className={button}
                        onClick={() => onOpenAdjustment(a.id)}
                      >
                        Open adjustment {a.id}
                      </button>
                      <p>
                        {a.state} · {a.payload.target} →{" "}
                        {a.payload.proposed_value}
                        {a.stale ? " · stale" : ""}
                      </p>
                    </div>
                  ))}
                  <label className="block text-xs">
                    Approved adjustment for resolution
                    <select
                      aria-label="Approved correction for resolution"
                      className={control}
                      value={adjustmentId}
                      onChange={(e) => setAdjustmentId(e.target.value)}
                    >
                      <option value="">No correction selected</option>
                      {finding.adjustment_links
                        .filter((a) => a.state === "approved" && !a.stale)
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.id}
                          </option>
                        ))}
                    </select>
                  </label>
                  <button
                    className={button}
                    disabled={
                      busy ||
                      !check ||
                      !check.target ||
                      check.expected_value === null ||
                      !["exact_mismatch", "judgment_required"].includes(
                        check.conclusion,
                      ) ||
                      !note.trim() ||
                      !authority.trim()
                    }
                    onClick={() => void createCorrection()}
                  >
                    Create linked adjustment draft
                  </button>
                  <label className="block text-xs">
                    Existing adjustment ID
                    <input
                      aria-label="Existing correction ID"
                      className={control}
                      value={linkId}
                      onChange={(e) => setLinkId(e.target.value)}
                    />
                  </label>
                  <button
                    className={button}
                    disabled={busy || !linkId || !note.trim()}
                    onClick={() =>
                      void run(async () => {
                        await evidenceRequest(
                          `/api/reconciliation-links?version=${version}&finding_id=${encodeURIComponent(finding.id)}`,
                          { actor_id: actor, adjustment_id: linkId, note },
                        );
                        await refresh(finding.id);
                        setMessage("Existing adjustment linked.");
                      })
                    }
                  >
                    Link existing adjustment
                  </button>
                  <h4 className="text-sm font-semibold">
                    Append-only review history
                  </h4>
                  <ol
                    className="space-y-1 text-xs"
                    data-testid="reconciliation-history"
                  >
                    {audit?.events.map((e) => (
                      <li key={e.id}>
                        {e.new_status} · {e.actor_name} · {e.created_at}:{" "}
                        {e.note}
                      </li>
                    ))}
                  </ol>
                  {audit?.decisions.map((d) => (
                    <p className="text-xs" key={d.id}>
                      {d.actor_id} · {d.disposition} · authority: {d.authority}
                    </p>
                  ))}
                </section>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
