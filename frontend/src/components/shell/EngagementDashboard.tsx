"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCheck,
  ClipboardList,
  FileSearch,
  Flag,
  FolderOpen,
  MessageSquare,
  ShieldAlert,
} from "lucide-react";
import { evidenceRequest } from "../evidence-types";
import {
  ActivityTimeline,
  EmptyState,
  ErrorState,
  Notice,
  PageHeader,
  SectionCard,
  Skeleton,
  StatCard,
  StatusBadge,
  humanize,
} from "../ui/primitives";
export type WorkflowEntity = {
  id: string;
  kind: string;
  area: string;
  state: string;
  revision: number;
  authors: string[];
  data: Record<string, unknown>;
};
export type WorkflowOverview = {
  engagement: WorkflowEntity;
  memberships: WorkflowEntity[];
  staff: { id: string; name: string; role: string }[];
  records: WorkflowEntity[];
  notes: WorkflowEntity[];
  tasks: WorkflowEntity[];
  signoffs: { id: string; area: string; state: string }[];
  notifications: WorkflowEntity[];
};
export type Readiness = {
  filing_ready: boolean;
  blockers: { code: string; resources: string[] }[];
  label: string;
};
export type ChangeEvent = {
  id: number;
  category: string;
  resource_id: string;
  action: string;
  actor_id: string;
  created_at: string;
  areas: string[];
};
type Finding = {
  id: string;
  title: string;
  severity: string;
  area: string;
  status: string;
  review_validity?: { state: string };
};
type DocumentSummary = {
  total: number;
  counts: Record<string, number>;
  documents: { id: string; title: string; dispositions: string[] }[];
};
type Adjustment = {
  id: string;
  state: string;
  stale: boolean;
  payload: { target: string; label: string };
};
type Version = {
  version: string;
  summary: Record<string, Record<string, number>>;
};
type Data = {
  findings: Finding[] | null;
  documents: DocumentSummary | null;
  adjustments: Adjustment[] | null;
  questions: WorkflowEntity[] | null;
  versions: Version[] | null;
};
const empty: Data = {
  findings: null,
  documents: null,
  adjustments: null,
  questions: null,
  versions: null,
};
export default function EngagementDashboard({
  workflow,
  fullAccess,
  admin,
  navigate,
  activity,
  openActivity,
}: {
  workflow: WorkflowOverview | null;
  readiness: Readiness | null;
  fullAccess: boolean;
  admin: boolean;
  navigate: (view: string, ref?: string) => void;
  activity: ChangeEvent[];
  openActivity: () => void;
}) {
  const [data, setData] = useState<Data>(empty);
  const [loading, setLoading] = useState(fullAccess && !admin);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!fullAccess || admin) return;
    setError("");
    const results = await Promise.allSettled([
      evidenceRequest<{ findings: Finding[] }>(
        "/api/unified-findings?version=v3",
      ),
      evidenceRequest<DocumentSummary>(
        "/api/document-accountability?version=v3",
      ),
      evidenceRequest<{ adjustments: Adjustment[] }>(
        "/api/adjustments?version=v3",
      ),
      evidenceRequest<{ items: WorkflowEntity[] }>("/api/product/overview"),
      evidenceRequest<Version[]>("/api/return-versions"),
    ]);
    const [f, d, a, q, v] = results;
    setData({
      findings: f.status === "fulfilled" ? f.value.findings : null,
      documents: d.status === "fulfilled" ? d.value : null,
      adjustments: a.status === "fulfilled" ? a.value.adjustments : null,
      questions:
        q.status === "fulfilled"
          ? q.value.items.filter((i) => i.kind === "p_question")
          : null,
      versions: v.status === "fulfilled" ? v.value : null,
    });
    if (results.some((r) => r.status === "rejected"))
      setError(
        "Some engagement metrics could not be loaded. Unavailable metrics are shown as —, never as zero.",
      );
    setLoading(false);
  }, [fullAccess, admin]);
  useEffect(() => {
    let active = true;
    if (fullAccess && !admin) {
      void Promise.resolve().then(() => {
        if (active) void load();
      });
    }
    return () => {
      active = false;
    };
  }, [load, fullAccess, admin]);
  useEffect(() => {
    const update = () => void load();
    window.addEventListener("workpaper:changes", update);
    return () => window.removeEventListener("workpaper:changes", update);
  }, [load]);
  const unresolved = data.findings?.filter(
    (f) =>
      f.status !== "resolved" ||
      f.review_validity?.state === "needs_reassessment",
  );
  const pending =
    data.adjustments && workflow
      ? data.adjustments.filter((a) => a.state === "submitted").length +
        workflow.records.filter((r) => r.state === "submitted").length
      : null;
  const questions =
    data.questions && workflow
      ? data.questions.filter((q) => q.data.blocking && q.state !== "resolved")
          .length +
        workflow.records.filter(
          (r) => r.data.record_type === "question" && r.state !== "approved",
        ).length
      : null;
  const tasks = workflow?.tasks.filter((t) => t.state !== "complete");
  const count = (value: number | null | undefined) =>
    fullAccess && !admin ? (value ?? "—") : "Restricted";
  const priorities = [
    ...(unresolved ?? [])
      .filter((f) => ["critical", "high"].includes(f.severity))
      .slice(0, 3)
      .map((f) => ({
        id: f.id,
        title: f.title,
        category: humanize(f.area),
        severity: f.severity,
        view: "reconciliation",
        owner: workflow?.memberships.find(
          (m) => m.state === "active" && m.data.responsibility === "preparer",
        )?.data.staff_id as string | undefined,
      })),
    ...(data.questions ?? [])
      .filter((q) => q.data.blocking && q.state !== "resolved")
      .slice(0, 2)
      .map((q) => ({
        id: q.id,
        title: String(q.data.title),
        category: "Blocking question",
        severity: "high",
        view: "collaboration",
        owner: String(q.data.owner_id),
      })),
    ...(workflow?.notes ?? [])
      .filter((n) => n.state !== "resolved")
      .slice(0, 2)
      .map((n) => ({
        id: n.id,
        title: String(n.data.title),
        category: "Review note",
        severity: "high",
        view: "notes",
        owner: String(n.data.owner_id),
      })),
    ...(data.documents?.documents ?? [])
      .filter((d) => d.dispositions.includes("requires_review"))
      .slice(0, 1)
      .map((d) => ({
        id: d.id,
        title: d.title,
        category: "Evidence review",
        severity: "medium",
        view: "documents",
        owner: undefined,
      })),
  ].slice(0, 6);
  const resolved =
    data.findings?.filter(
      (f) =>
        f.status === "resolved" &&
        f.review_validity?.state !== "needs_reassessment",
    ).length ?? 0;
  const inReview =
    data.findings?.filter(
      (f) =>
        f.status === "in_review" &&
        f.review_validity?.state !== "needs_reassessment",
    ).length ?? 0;
  const stale =
    data.findings?.filter(
      (f) => f.review_validity?.state === "needs_reassessment",
    ).length ?? 0;
  const version = String(workflow?.engagement.data.baseline ?? "v3");
  const baseline = data.versions?.find((v) => v.version === version);
  return (
    <div className="dashboard" data-testid="engagement-dashboard">
      <PageHeader
        eyebrow="Engagement overview"
        title="A clear view of the work ahead."
        description="Okafor–Lindqvist household · 2025 individual return"
        actions={
          <button
            className="ui-button secondary"
            onClick={() => navigate("readiness")}
          >
            <ShieldAlert size={16} />
            Review filing readiness
            <ArrowUpRight size={14} />
          </button>
        }
      />
      <div className="engagement-summary">
        <div className="engagement-summary-title">
          <span className="large-engagement-avatar">OL</span>
          <div>
            <h2>Okafor–Lindqvist</h2>
            <p>
              CL-20417 <span>·</span> Tax year{" "}
              {String(workflow?.engagement.data.tax_year ?? 2025)}{" "}
              <span>·</span> Return {version}
            </p>
          </div>
        </div>
        <div className="engagement-team">
          {["preparer", "reviewer", "partner"].map((role) => {
            const assignment = workflow?.memberships.find(
              (m) => m.state === "active" && m.data.responsibility === role,
            );
            const person = workflow?.staff.find(
              (s) => s.id === assignment?.data.staff_id,
            );
            return (
              <div key={role}>
                <span>{humanize(role)}</span>
                <strong>{person?.name ?? "Not assigned"}</strong>
              </div>
            );
          })}
        </div>
        <StatusBadge value="blocked">FILING BLOCKED</StatusBadge>
      </div>
      {error && <ErrorState message={error} retry={() => void load()} />}
      {loading ? (
        <Skeleton rows={3} />
      ) : (
        <div className="kpi-grid" data-testid="dashboard-metrics">
          <StatCard
            label="Open findings"
            value={count(unresolved?.length)}
            description="Open or needing reassessment"
            icon={<Flag size={17} />}
            action={
              fullAccess && !admin
                ? () => navigate("reconciliation")
                : undefined
            }
          />
          <StatCard
            label="Documents to review"
            value={count(data.documents?.counts.requires_review)}
            description="Distinct requires-review disposition"
            icon={<FileSearch size={17} />}
            action={
              fullAccess && !admin
                ? () => navigate("accountability")
                : undefined
            }
          />
          <StatCard
            label="Pending approvals"
            value={count(pending)}
            description="Submitted records + adjustments"
            icon={<CheckCheck size={17} />}
            action={
              fullAccess && !admin ? () => navigate("signoffs") : undefined
            }
          />
          <StatCard
            label="Outstanding tasks"
            value={tasks?.length ?? "—"}
            description="Visible incomplete assignments"
            icon={<ClipboardList size={17} />}
            action={() => navigate("tasks")}
          />
          <StatCard
            label="Blocking questions"
            value={count(questions)}
            description="Unresolved collaboration + practice questions"
            icon={<MessageSquare size={17} />}
            action={!admin ? () => navigate("collaboration") : undefined}
          />
        </div>
      )}
      {(!fullAccess || admin) && (
        <Notice>
          Your role has a scoped operational view. Tax metrics are restricted,
          rather than presented as zero. Open Firm Operations for authorized
          assignments, deadlines and budgets.
        </Notice>
      )}
      <div className="dashboard-columns">
        <SectionCard
          title="Priority action queue"
          description="Material discrepancies and unresolved evidence, ready for investigation."
          action={
            <button
              className="text-button"
              onClick={() => navigate(admin ? "tasks" : "readiness")}
            >
              View all blockers <ArrowRight size={14} />
            </button>
          }
        >
          {loading ? (
            <Skeleton />
          ) : priorities.length ? (
            <div className="priority-list">
              {priorities.map((p, i) => (
                <button key={p.id} onClick={() => navigate(p.view, p.id)}>
                  <span className={`priority-icon ${p.severity}`}>
                    <Flag size={16} />
                  </span>
                  <span className="priority-copy">
                    <strong>{p.title}</strong>
                    <small>
                      {p.category} ·{" "}
                      {p.owner
                        ? (workflow?.staff.find((s) => s.id === p.owner)
                            ?.name ?? p.owner)
                        : "Owner not supplied"}
                    </small>
                  </span>
                  <span className="priority-order">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <ChevronRightIcon />
                </button>
              ))}
            </div>
          ) : (
            <EmptyState
              title={
                admin || !fullAccess
                  ? "Operational work is available"
                  : "No priority items in the loaded view"
              }
              description="Full readiness remains separate from this queue."
              action={
                <button
                  className="ui-button secondary"
                  onClick={() => navigate("operations")}
                >
                  Open firm operations
                </button>
              }
            />
          )}
        </SectionCard>
        <SectionCard
          title="Review activity"
          description="Documented finding decisions, not return completion."
        >
          {data.findings ? (
            <>
              <div className="review-count">
                <strong>{resolved}</strong>
                <span>
                  of {data.findings.length} finding reviews
                  <br />
                  resolved with a current decision
                </span>
              </div>
              <div
                className="review-progress"
                aria-label={`${resolved} of ${data.findings.length} finding reviews resolved`}
              >
                <span
                  style={{
                    width: `${data.findings.length ? (resolved / data.findings.length) * 100 : 0}%`,
                  }}
                />
              </div>
              <div className="review-breakdown">
                <div>
                  <span>
                    <i className="legend-dot blue" />
                    In review
                  </span>
                  <strong>{inReview}</strong>
                </div>
                <div>
                  <span>
                    <i className="legend-dot amber" />
                    Needs reassessment
                  </span>
                  <strong>{stale}</strong>
                </div>
                <div>
                  <span>
                    <i className="legend-dot slate" />
                    Other unresolved
                  </span>
                  <strong>
                    {data.findings.length - resolved - inReview - stale}
                  </strong>
                </div>
              </div>
              <p className="subtle-note">
                Resolving a finding does not correct the engine or authorize
                filing.
              </p>
            </>
          ) : (
            <EmptyState
              title="Review metrics unavailable"
              description="They require an entire-engagement practice assignment."
            />
          )}
        </SectionCard>
      </div>
      <div className="dashboard-columns lower">
        <SectionCard
          title="Recent activity"
          description="Authorized changes from your live feed."
          action={
            <button className="text-button" onClick={openActivity}>
              Activity log <ArrowRight size={14} />
            </button>
          }
        >
          {activity.length ? (
            <ActivityTimeline
              events={[...activity]
                .sort((a, b) => b.created_at.localeCompare(a.created_at))
                .slice(0, 5)
                .map((e) => ({
                  id: e.id,
                  title: `${humanize(e.category.replace(/^p_/, ""))} · ${humanize(e.action)}`,
                  actor: e.actor_id,
                  at: e.created_at,
                  detail: (
                    <small className="activity-resource">{e.resource_id}</small>
                  ),
                }))}
            />
          ) : (
            <EmptyState
              title="You’re up to date"
              description="New authorized changes will appear here. Your checkpoint is personal."
            />
          )}
        </SectionCard>
        <SectionCard
          title="Continue your review"
          description="Every shortcut opens a supported workspace."
        >
          <div className="quick-actions">
            {[
              {
                title: "Review source evidence",
                description: "Documents, fields and provenance",
                view: "documents",
                icon: FolderOpen,
              },
              {
                title: "Investigate discrepancies",
                description: "Independent reconciliation and evidence",
                view: "reconciliation",
                icon: Flag,
              },
              {
                title: "Open adjustment ledger",
                description: "Drafts, independent approvals and audit",
                view: "adjustments",
                icon: CheckCheck,
              },
              {
                title: "Review sign-offs",
                description: "Current approvals and invalidation history",
                view: "signoffs",
                icon: ShieldAlert,
              },
            ]
              .filter(() => fullAccess && !admin)
              .map((a) => (
                <button key={a.view} onClick={() => navigate(a.view)}>
                  <span>
                    <a.icon size={17} />
                  </span>
                  <div>
                    <strong>{a.title}</strong>
                    <small>{a.description}</small>
                  </div>
                  <ArrowUpRight size={15} />
                </button>
              ))}
            {(!fullAccess || admin) && (
              <button onClick={() => navigate("operations")}>
                <span>
                  <ClipboardList size={18} />
                </span>
                <div>
                  <strong>Open firm operations</strong>
                  <small>Authorized workload and deadlines</small>
                </div>
                <ArrowUpRight size={15} />
              </button>
            )}
          </div>
        </SectionCard>
      </div>
      {baseline && (
        <div className="baseline-strip">
          <span>
            <strong>Stored baseline {version}</strong>
            <small>
              Supplied engine results · not an authoritative corrected return
            </small>
          </span>
          {(["federal", "california"] as const).map((j) => (
            <div key={j}>
              <span>{humanize(j)} total tax</span>
              <strong>
                {typeof baseline.summary[j]?.total_tax === "number"
                  ? new Intl.NumberFormat("en-US", {
                      style: "currency",
                      currency: "USD",
                      maximumFractionDigits: 0,
                    }).format(baseline.summary[j].total_tax)
                  : "Not supplied"}
              </strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
function ChevronRightIcon() {
  return <ArrowRight size={15} className="queue-arrow" />;
}
