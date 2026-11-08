"use client";
import { useConfirm } from "./ui/primitives";
import { useWorkpaperIdentity } from "@/components/session";

import { apiFetch } from "@/components/session";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Staff = { id: string; name: string; role: string; active_from: string };
type Draft = {
  target: string;
  proposed_value: string;
  rationale: string;
  authority: string;
  refs: string[];
};
type Effect = {
  method: string;
  category: string | null;
  federal_tax: string | null;
  california_tax: string | null;
  manual_review: boolean;
  requires_partner: boolean | null;
  warning: string;
};
type Adjustment = {
  id: string;
  state: string;
  revision: number;
  sequence: number;
  prepared_by: string[];
  stale: boolean;
  conflicts?: string[];
  supersedes_id: string | null;
  payload: Draft & {
    label: string;
    engine_value: string;
    delta: string;
    effect: Effect;
  };
};
type Metadata = {
  staff: Staff[];
  targets: {
    key: string;
    label: string;
    engine_value: string;
    method_available: boolean;
  }[];
  demo: Draft;
};
type Summary = {
  approved_adjustment_ids: string[];
  warning: string;
  jurisdictions: Record<
    string,
    {
      tax_effect: string;
      estimated_total_tax: string;
      estimated_payments: string;
      estimated_balance_due: string;
    }
  >;
};
type AuditEvent = {
  id: number;
  action: string;
  actor_id: string;
  actor_role: string;
  previous_state: string | null;
  new_state: string;
  revision: number;
  note: string;
  created_at: string;
  snapshot: Adjustment;
};
const blank: Draft = {
  target: "SchC.1",
  proposed_value: "",
  rationale: "",
  authority: "",
  refs: [],
};
const control = "ui-control w-full";
const button = "ui-button secondary";

async function request<T>(
  path: string,
  body?: object,
  method = "POST",
): Promise<T> {
  const response = await apiFetch(
    `${API}${path}`,
    body
      ? {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : { cache: "no-store" },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status})`,
    );
  return data as T;
}

export default function AdjustmentWorkspace({
  version,
  onOpenDocument,
  onOpenEvidence,
  onOpenReference,
  initialAdjustmentId,
}: {
  version: string;
  onOpenDocument: (id: string) => void;
  onOpenEvidence: (id: string) => void;
  onOpenReference?: (ref: string) => void;
  initialAdjustmentId?: string | null;
}) {
  const confirm = useConfirm();
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [items, setItems] = useState<Adjustment[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const identity = useWorkpaperIdentity();
  const [legacyActor, setActor] = useState("st-01");
  const actor = identity?.id ?? legacyActor;
  const [draft, setDraft] = useState<Draft>(blank);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const selected = items.find((item) => item.id === selectedId);
  const currentStaff = metadata?.staff.find((staff) => staff.id === actor);
  const independent =
    !!selected &&
    !selected.prepared_by.includes(actor) &&
    ["reviewer", "partner"].includes(currentStaff?.role ?? "");
  const partnerAllowed =
    !selected?.payload.effect.requires_partner ||
    currentStaff?.role === "partner";

  useEffect(() => {
    let active = true;
    Promise.all([
      request<Metadata>(`/api/adjustment-metadata?version=${version}`),
      request<{ adjustments: Adjustment[] }>(
        `/api/adjustments?version=${version}`,
      ),
      request<Summary>(`/api/workpaper-summary?version=${version}`),
      initialAdjustmentId
        ? request<{ events: AuditEvent[] }>(
            `/api/adjustments/${initialAdjustmentId}/history`,
          )
        : Promise.resolve({ events: [] as AuditEvent[] }),
    ])
      .then(([meta, list, totals, audit]) => {
        if (active) {
          setMetadata(meta);
          setItems(list.adjustments);
          setSummary(totals);
          if (initialAdjustmentId) {
            setSelectedId(initialAdjustmentId);
            setEvents(audit.events);
          }
        }
      })
      .catch((err) => {
        if (active) setError(String(err.message));
      });
    return () => {
      active = false;
    };
  }, [version, initialAdjustmentId]);

  async function reload(id: string | null) {
    const [list, totals, audit] = await Promise.all([
      request<{ adjustments: Adjustment[] }>(
        `/api/adjustments?version=${version}`,
      ),
      request<Summary>(`/api/workpaper-summary?version=${version}`),
      id
        ? request<{ events: AuditEvent[] }>(`/api/adjustments/${id}/history`)
        : Promise.resolve({ events: [] }),
    ]);
    setItems(list.adjustments);
    setSummary(totals);
    setEvents(audit.events);
    setSelectedId(id);
  }
  async function run(operation: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await operation();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to save adjustment",
      );
    } finally {
      setBusy(false);
    }
  }
  function newDraft() {
    setSelectedId(null);
    setEvents([]);
    setEditing(false);
    setDraft(blank);
    setMessage("");
    setError("");
  }
  async function save() {
    await run(async () => {
      const result =
        editing && selected
          ? await request<Adjustment>(
              `/api/adjustments/${selected.id}/revisions`,
              {
                ...draft,
                actor_id: actor,
                expected_sequence: selected.sequence,
              },
            )
          : await request<Adjustment>(`/api/adjustments?version=${version}`, {
              ...draft,
              actor_id: actor,
            });
      await reload(result.id);
      setEditing(false);
      setMessage("Adjustment draft saved.");
    });
  }
  async function act(action: string) {
    if (
      !(await confirm({
        title: `Confirm ${action.replace(/_/g, " ")} adjustment`,
        description:
          "This records a ledger transition with immutable history. Independent approval, partner thresholds and conflict checks remain enforced by the backend.",
        danger: ["reverse", "reject", "supersede"].includes(action),
      }))
    )
      return;
    if (!selected) return;
    await run(async () => {
      const result = await request<Adjustment & { replacement_id?: string }>(
        `/api/adjustments/${selected.id}/actions`,
        { actor_id: actor, expected_sequence: selected.sequence, action, note },
      );
      await reload(result.replacement_id ?? result.id);
      setNote("");
      setMessage(`Adjustment ${action} recorded.`);
    });
  }

  return (
    <div className="space-y-5 p-5" data-testid="adjustment-workspace">
      <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
        Engine values are immutable. This workspace records separate, estimated
        workpaper adjustments. Staff selection is a local demonstration
        identity, not authenticated login.
      </p>
      <label className="block text-sm font-medium">
        Adjustment staff
        <select
          aria-label="Adjustment staff"
          className={control}
          value={actor}
          disabled={!!identity || busy}
          onChange={(e) => setActor(e.target.value)}
        >
          {metadata?.staff
            .filter(
              (s) =>
                ["preparer", "reviewer", "partner"].includes(s.role) &&
                s.active_from <= new Date().toISOString().slice(0, 10),
            )
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} · {s.role} · {s.id}
              </option>
            ))}
        </select>
      </label>
      {error && (
        <p
          role="alert"
          className="rounded-lg bg-red-50 p-3 text-sm text-red-800"
        >
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="text-sm text-green-800">
          {message}
        </p>
      )}
      <section
        className="rounded-lg border border-slate-200 p-3"
        data-testid="approved-summary"
      >
        <h3 className="font-semibold">Approved workpaper estimates</h3>
        <p className="text-sm">
          {summary?.approved_adjustment_ids.length ?? 0} currently approved
          adjustments
        </p>
        {summary && (
          <div className="overflow-auto">
            <table className="mt-2 w-full text-left text-xs">
              <thead>
                <tr>
                  <th>Jurisdiction</th>
                  <th>Tax effect</th>
                  <th>Estimated total tax</th>
                  <th>Estimated balance due</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary.jurisdictions).map(([name, totals]) => (
                  <tr key={name}>
                    <td className="py-2">{name}</td>
                    <td data-testid={`${name}-effect`}>{totals.tax_effect}</td>
                    <td>{totals.estimated_total_tax}</td>
                    <td>{totals.estimated_balance_due}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-2 text-xs text-slate-500">{summary?.warning}</p>
      </section>
      <div className="flex flex-wrap gap-2">
        <button className={button} disabled={busy} onClick={newDraft}>
          New adjustment
        </button>
        <button
          className={button}
          disabled={busy || !metadata}
          onClick={() => {
            newDraft();
            if (metadata) setDraft(metadata.demo);
          }}
        >
          Load business receipts example
        </button>
      </div>
      <ul className="space-y-2" aria-label="Adjustment list">
        {items.map((item) => (
          <li key={item.id}>
            <button
              className={`${button} w-full text-left ${selectedId === item.id ? "bg-indigo-50" : ""}`}
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await reload(item.id);
                  setEditing(false);
                })
              }
            >
              {item.payload.target} · {item.state} · revision {item.revision}
              <span className="block break-all text-xs text-slate-500">
                {item.id}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {(!selected || editing) && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <h3 className="font-semibold">
            {editing ? "Revise adjustment" : "Create adjustment draft"}
          </h3>
          <label className="block text-sm">
            Target line
            <select
              aria-label="Adjustment target"
              className={control}
              value={draft.target}
              onChange={(e) => setDraft({ ...draft, target: e.target.value })}
            >
              {metadata?.targets.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.key} · {t.label} · engine {t.engine_value}
                  {t.method_available ? "" : " · manual review"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Proposed value
            <input
              aria-label="Proposed value"
              className={control}
              required
              type="number"
              step="0.01"
              value={draft.proposed_value}
              onChange={(e) =>
                setDraft({ ...draft, proposed_value: e.target.value })
              }
            />
          </label>
          <label className="block text-sm">
            Adjustment rationale
            <textarea
              aria-label="Adjustment rationale"
              className={control}
              required
              maxLength={4000}
              value={draft.rationale}
              onChange={(e) =>
                setDraft({ ...draft, rationale: e.target.value })
              }
            />
          </label>
          <label className="block text-sm">
            Authority relied on
            <textarea
              aria-label="Authority relied on"
              className={control}
              required
              maxLength={4000}
              value={draft.authority}
              onChange={(e) =>
                setDraft({ ...draft, authority: e.target.value })
              }
            />
          </label>
          <label className="block text-sm">
            Evidence references (one per line)
            <textarea
              aria-label="Adjustment evidence references"
              className={control}
              required
              value={draft.refs.join("\n")}
              onChange={(e) =>
                setDraft({ ...draft, refs: e.target.value.split("\n") })
              }
            />
          </label>
          <button
            className="ui-button primary"
            disabled={busy || !metadata}
            type="submit"
          >
            {editing ? "Save revision" : "Save adjustment draft"}
          </button>
        </form>
      )}
      {selected && (
        <section
          className="space-y-3 rounded-lg border border-slate-200 p-4"
          aria-label="Adjustment details"
        >
          <h3 className="font-semibold">
            {selected.payload.target} adjustment
          </h3>
          <p>
            State:{" "}
            <strong data-testid="adjustment-state">{selected.state}</strong> ·
            Revision {selected.revision}
          </p>
          <p className="text-sm">
            Engine {selected.payload.engine_value} → proposed{" "}
            {selected.payload.proposed_value} · change {selected.payload.delta}
          </p>
          <p className="text-sm">{selected.payload.rationale}</p>
          <p className="text-sm">Authority: {selected.payload.authority}</p>
          <p className="text-sm">
            Method: {selected.payload.effect.method}
            {selected.payload.effect.category &&
              ` (${selected.payload.effect.category})`}
          </p>
          <p className="text-sm">
            Estimated federal tax effect:{" "}
            {selected.payload.effect.federal_tax ?? "Unknown"}; California:{" "}
            {selected.payload.effect.california_tax ?? "Unknown"}
          </p>
          <p className="text-sm text-amber-800">
            {selected.payload.effect.manual_review
              ? "Manual review required. Approval blocked."
              : selected.payload.effect.requires_partner
                ? "Partner approval required (tax effect exceeds $1,000)."
                : "Independent reviewer or partner approval required."}
          </p>
          <p className="text-xs text-slate-500">
            {selected.payload.effect.warning}
          </p>
          {selected.stale && (
            <p className="text-red-800">
              Packet fingerprint changed. Excluded from summary; create a fresh
              adjustment.
            </p>
          )}
          {!!selected.conflicts?.length && (
            <p className="break-all text-red-800">
              Conflicting adjustments: {selected.conflicts.join(", ")}.
              Submission and approval blocked.
            </p>
          )}
          {selected.supersedes_id && (
            <p className="break-all text-xs">
              Replaces {selected.supersedes_id}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {selected.payload.refs.map((ref) => (
              <button
                className={button}
                type="button"
                key={ref}
                onClick={() => {
                  if (onOpenReference) {
                    onOpenReference(ref);
                    return;
                  }
                  if (ref.startsWith("ev-")) onOpenEvidence(ref);
                  else if (ref.startsWith("doc:"))
                    onOpenDocument(ref.slice(4).split("#")[0]);
                }}
                disabled={
                  !onOpenReference &&
                  !ref.startsWith("ev-") &&
                  !ref.startsWith("doc:")
                }
              >
                {ref}
              </button>
            ))}
          </div>
          {["draft", "rejected"].includes(selected.state) && (
            <button
              className={button}
              disabled={busy}
              onClick={() => {
                const p = selected.payload;
                setDraft({
                  target: p.target,
                  proposed_value: p.proposed_value,
                  rationale: p.rationale,
                  authority: p.authority,
                  refs: p.refs,
                });
                setEditing(true);
              }}
            >
              Edit revision
            </button>
          )}
          <label className="block text-sm">
            Action note
            <textarea
              aria-label="Adjustment action note"
              className={control}
              maxLength={4000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {selected.state === "draft" && (
              <button
                className={button}
                disabled={
                  busy ||
                  !note.trim() ||
                  selected.stale ||
                  !!selected.conflicts?.length
                }
                onClick={() => void act("submit")}
              >
                Submit adjustment
              </button>
            )}
            {selected.state === "submitted" && (
              <>
                <button
                  className={button}
                  disabled={
                    busy ||
                    !note.trim() ||
                    !independent ||
                    !partnerAllowed ||
                    selected.payload.effect.manual_review ||
                    selected.stale ||
                    !!selected.conflicts?.length
                  }
                  onClick={() => void act("approve")}
                >
                  Approve adjustment
                </button>
                <button
                  className={button}
                  disabled={
                    busy || !note.trim() || !independent || selected.stale
                  }
                  onClick={() => void act("reject")}
                >
                  Reject adjustment
                </button>
              </>
            )}
            {selected.state === "approved" && (
              <>
                <button
                  className={button}
                  disabled={
                    busy ||
                    !note.trim() ||
                    !independent ||
                    !partnerAllowed ||
                    selected.stale
                  }
                  onClick={() => void act("reverse")}
                >
                  Reverse adjustment
                </button>
                <button
                  className={button}
                  disabled={
                    busy ||
                    !note.trim() ||
                    !independent ||
                    !partnerAllowed ||
                    selected.stale
                  }
                  onClick={() => void act("supersede")}
                >
                  Supersede with new draft
                </button>
              </>
            )}
          </div>
          <h4 className="font-semibold">Append-only audit history</h4>
          <ol className="space-y-2" data-testid="adjustment-history">
            {events.map((event) => (
              <li key={event.id} className="rounded bg-slate-50 p-3 text-xs">
                <p>
                  {event.action} · {event.actor_id} ({event.actor_role}) ·
                  revision {event.revision} · {event.previous_state ?? "new"} →{" "}
                  {event.new_state}
                </p>
                <p>{event.note}</p>
                <time>{event.created_at}</time>
                <details>
                  <summary>Preserved snapshot</summary>
                  <pre className="overflow-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(event.snapshot, null, 2)}
                  </pre>
                </details>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
