"use client";
import { API_BASE } from "@/lib/api-config";
import { useConfirm } from "./ui/primitives";
import {
  useEffect,
  useState,
  useRef,
  useCallback,
  type ReactNode,
} from "react";
import FilingLifecycleWorkspace from "./FilingLifecycleWorkspace";
import ChangeAnalysisWorkspace from "./ChangeAnalysisWorkspace";
import ProductWorkspace from "./ProductWorkspace";
import LiveUpdates from "./LiveUpdates";
import {
  apiFetch,
  sessionCredentials,
  sensitiveAccess,
  SessionContext,
  type StaffIdentity,
} from "./session";
import { AppShell } from "./shell/AppShell";
import {
  NavigationContext,
  workpaperViews,
  scopedViews,
  analysisViews,
  filingViews,
  viewInfo,
} from "./shell/navigation";
import { useNavigation } from "./shell/useNavigation";
import EngagementDashboard, {
  type ChangeEvent,
} from "./shell/EngagementDashboard";
import {
  ConfirmationProvider,
  PageHeader,
  RecordDetails,
  Skeleton,
  EmptyState,
  humanize,
} from "./ui/primitives";
const API = API_BASE;
type Session = {
  mode: string;
  staff: StaffIdentity | null;
  csrf_token: string;
  legacy_profile: boolean;
  identity_assurance: string;
  expires_at?: string;
  assignment_demo?: boolean;
  state_warning?: string;
};
type Item = {
  id: string;
  kind: string;
  area: string;
  state: string;
  revision: number;
  authors: string[];
  data: Record<string, unknown>;
};
type Overview = {
  engagement: Item;
  memberships: Item[];
  staff: StaffIdentity[];
  policy: { id: string; revision: number; policy: Record<string, unknown> };
  records: Item[];
  notes: Item[];
  tasks: Item[];
  notifications: Item[];
  signoffs: {
    id: string;
    area: string;
    level: string;
    staff_id: string;
    state: string;
    reason: string;
  }[];
  areas: string[];
  record_types: string[];
  available_verification_methods: string[];
};
type Readiness = {
  filing_ready: boolean;
  blockers: { code: string; resources: string[] }[];
  label: string;
};
const control = "ui-control";
const button = "ui-button secondary";
async function request<T>(path: string, body?: object): Promise<T> {
  let response: Response;
  try {
    response = await apiFetch(API + path, {
      ...(body
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }
        : {}),
      signal: AbortSignal.timeout(15000),
    });
  } catch (error) {
    if (error instanceof Error && error.message.includes("response discarded"))
      throw error;
    throw new Error(
      `Cannot reach the workpaper backend at ${API}. Check that it is running and NEXT_PUBLIC_API_URL points to it. Use localhost for both frontend and backend; check allowed Origin/CORS settings.`,
    );
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      `The backend at ${API} returned an invalid API response (${response.status}). Check NEXT_PUBLIC_API_URL; it must point to FastAPI, not the Next.js server.`,
    );
  }
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status})`,
    );
  return data;
}
// React development effects may mount twice. Share bootstrap until both session and
// staff are loaded so two simultaneous cookie/CSRF rotations cannot race each other.
let initialization: Promise<{
  session: Session;
  staff: StaffIdentity[];
}> | null = null;
function initializeSession() {
  if (!initialization)
    initialization = (async () => {
      const session = await request<Session>("/api/workflow/session");
      if (session.legacy_profile) return { session, staff: [] };
      if (session.mode === "locked")
        throw new Error(
          `Backend session provider is locked at ${API}. For local demonstration, stop the old backend and run from backend: .venv/bin/python run_secure.py --demo. Production requires a configured credential provider. Then retry initialization.`,
        );
      if (
        !["demo", "credential", "access"].includes(session.mode) ||
        !session.csrf_token
      )
        throw new Error(
          `Backend session configuration is invalid at ${API}. No identity selection is allowed until a valid demo or credential provider is configured.`,
        );
      const options = await request<{ staff: StaffIdentity[] }>(
        "/api/workflow/session/staff",
      );
      if (!Array.isArray(options.staff) || !options.staff.length)
        throw new Error(
          `No staff options were returned by ${API}. Check the session provider and original packet; identity selection remains disabled.`,
        );
      return { session, staff: options.staff };
    })().finally(() => {
      initialization = null;
    });
  return initialization;
}
export default function FirmWorkflow({ children }: { children: ReactNode }) {
  const tabId = useRef("");
  const [session, setSession] = useState<Session | null>(null);
  const [staff, setStaff] = useState<StaffIdentity[]>([]);
  const [selected, setSelected] = useState("st-01");
  const [credential, setCredential] = useState("");
  const [error, setError] = useState("");
  const [switching, setSwitching] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [initializationError, setInitializationError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    initializeSession()
      .then(({ session: s, staff: options }) => {
        if (!active) return;
        sessionCredentials(s.csrf_token ?? "");
        setSession(s);
        if (s.mode === "access" && s.staff) setSelected(s.staff.id);
        setStaff(options);
        setInitializationError("");
      })
      .catch((e) => {
        if (active) {
          sessionCredentials("");
          setStaff([]);
          setSession(null);
          setInitializationError(String(e));
        }
      })
      .finally(() => {
        if (active) setInitializing(false);
      });
    return () => {
      active = false;
    };
  }, [attempt]);
  useEffect(() => {
    tabId.current = crypto.randomUUID();
    const channel = new BroadcastChannel("miraflores-session");
    channel.onmessage = (event) => {
      if (event.data?.sender === tabId.current) return;
      sessionCredentials("");
      setSession(null);
      setError("Session changed in another tab. Reload before continuing.");
    };
    const hide = () => {
      sensitiveAccess(false, "");
      setSession(null);
    };
    const lost = () => {
      sessionCredentials("");
      setSession(null);
      setError(
        "Session or engagement assignment changed. Reload and select an authorized staff session.",
      );
    };
    window.addEventListener("workpaper:access-lost", lost);
    const show = (event: PageTransitionEvent) => {
      if (event.persisted) window.location.reload();
    };
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    return () => {
      channel.close();
      window.removeEventListener("workpaper:access-lost", lost);
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, []);
  useEffect(() => {
    if (!session?.staff || !session.expires_at) return;
    const expiry = Date.parse(session.expires_at);
    const timer = window.setTimeout(
      () => {
        sessionCredentials("");
        setSession(null);
        setError(
          "Session expired. Reload to reauthenticate through the configured session provider.",
        );
      },
      Number.isFinite(expiry) ? Math.max(0, expiry - Date.now()) : 0,
    );
    return () => window.clearTimeout(timer);
  }, [session]);
  async function select(id: string | null) {
    // Invalidate in-flight reads before the server rotates the cookie. Keep the
    // current CSRF secret solely for the authorized session-switch request.
    sessionCredentials(session?.csrf_token ?? "");
    setSwitching(true);
    setError("");
    try {
      const s = await request<Session>("/api/workflow/session", {
        staff_id: id,
        credential,
      });
      sessionCredentials(s.csrf_token);
      setSession(s);
      setCredential("");
      if (id === null && s.mode === "access") {
        window.location.assign(
          new URL("/cdn-cgi/access/logout", window.location.origin).href,
        );
        return;
      }
      const channel = new BroadcastChannel("miraflores-session");
      channel.postMessage({ sender: tabId.current });
      channel.close();
    } catch (e) {
      setError(String(e));
    } finally {
      setSwitching(false);
    }
  }
  if (session?.legacy_profile)
    return (
      <ConfirmationProvider>
        <LegacyFrame>{children}</LegacyFrame>
      </ConfirmationProvider>
    );
  const assignmentNotice =
    session?.assignment_demo ||
    process.env.NEXT_PUBLIC_ASSIGNMENT_DEMO === "1" ? (
      <div
        role="status"
        className="notice warning"
        data-testid="assignment-demo-warning"
      >
        NON-PRODUCTION ASSIGNMENT DEMO — review changes and audit history
        disappear on server restart. Temporary reviewer tokens do not establish
        authenticated staff identity. Use synthetic evidence only. Protected
        originals are unavailable. FILING BLOCKED.
      </div>
    ) : null;
  const sessionControls = (
    <div className="session-controls">
      {" "}
      {initializationError && (
        <div
          role="alert"
          data-testid="session-initialization-error"
          className="my-3 rounded border border-red-300 bg-red-50 p-3"
        >
          <p>{initializationError}</p>
          <p className="text-xs">API base URL: {API}</p>
          <button
            className={button}
            disabled={initializing}
            onClick={() => {
              setInitializing(true);
              setInitializationError("");
              setAttempt((v) => v + 1);
            }}
          >
            Retry session initialization
          </button>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <label>
          Session staff{" "}
          <select
            aria-label="Session staff"
            disabled={
              initializing ||
              !staff.length ||
              session?.mode === "access" ||
              (!!session?.assignment_demo && !!session?.staff)
            }
            className={control}
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            {!staff.length && (
              <option value="st-01">
                {initializing
                  ? "Loading staff…"
                  : "Staff unavailable — check session configuration"}
              </option>
            )}
            {staff.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} · {s.name} · {s.role}
              </option>
            ))}
          </select>
        </label>
        {session?.mode === "credential" && (
          <input
            aria-label="Configured credential"
            type="password"
            autoComplete="off"
            value={credential}
            onChange={(e) => setCredential(e.target.value)}
          />
        )}
        <button
          className="ui-button primary"
          disabled={initializing || switching || !staff.length}
          onClick={() => void select(selected)}
        >
          {session?.mode === "access"
            ? "Refresh bound session"
            : "Start / switch session"}
        </button>
        {session?.staff && (
          <button className={button} onClick={() => void select(null)}>
            End session
          </button>
        )}
        <span
          className="session-current"
          data-testid={!session?.staff ? "current-session" : undefined}
        >
          {session?.staff
            ? `${session.staff.name} (${session.staff.id}) · ${session.staff.role}`
            : "No active staff session"}
        </span>
      </div>
      {error && <p role="alert">{error}</p>}
    </div>
  );
  return (
    <ConfirmationProvider key={session?.csrf_token ?? "locked"}>
      {assignmentNotice}
      {session?.staff && !switching ? (
        <SessionContext.Provider value={session.staff}>
          <Workspace
            key={session.staff.id + session.csrf_token}
            identity={session.staff}
            sessionControls={sessionControls}
          >
            {children}
          </Workspace>
        </SessionContext.Provider>
      ) : (
        <main className="session-gate">
          <section className="login-story">
            <div className="sidebar-brand">
              <span className="brand-mark">
                <span />
                <span />
                <span />
              </span>
              <span className="brand-name">
                MiraFlores<span>WORKPAPER</span>
              </span>
            </div>
            <p className="eyebrow">Clarity at every step</p>
            <h1>
              Every number.
              <br />
              Every source.
              <br />
              Every decision.
            </h1>
            <p>
              An evidence-backed workspace for thoughtful tax preparation and
              independent review.
            </p>
            <div className="login-principles">
              <p>01 &nbsp; Trace the evidence</p>
              <p>02 &nbsp; Reconcile independently</p>
              <p>03 &nbsp; Review with accountability</p>
            </div>
          </section>
          <section className="login-panel">
            <div className="login-form">
              <p className="eyebrow">2025 · CL-20417</p>
              <h2>Open your workpaper</h2>
              <p>Select a configured staff session to access the engagement.</p>
              <div className="notice warning">
                DEMONSTRATION SESSION — selected staff identity is not
                authenticated identity assurance. Approvals are never legally
                valid electronic signatures.
              </div>
              {sessionControls}
              <p className="muted">
                {switching
                  ? "Switching identity; clearing the previous workspace…"
                  : initializing
                    ? "Loading session configuration…"
                    : initializationError
                      ? "Resolve the backend configuration above, then retry."
                      : "Access and sensitive information are controlled by the backend."}
              </p>
            </div>
          </section>
        </main>
      )}
    </ConfirmationProvider>
  );
}
function LegacyFrame({ children }: { children: ReactNode }) {
  const navigation = useNavigation("return");
  return (
    <NavigationContext.Provider value={{ ...navigation, legacy: true }}>
      <AppShell
        view={navigation.view}
        onNavigate={navigation.navigate}
        identity={null}
        activityOpen={false}
        onActivityOpen={() => {}}
        legacy
      >
        {children}
      </AppShell>
    </NavigationContext.Provider>
  );
}

function Workspace({
  identity,
  children,
  sessionControls,
}: {
  identity: StaffIdentity;
  children: ReactNode;
  sessionControls: ReactNode;
}) {
  const confirm = useConfirm();
  const [data, setData] = useState<Overview | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const navigation = useNavigation();
  const tab = navigation.view;
  const setTab = navigation.setView;
  const [activityOpen, setActivityOpen] = useState(false);
  const [activityEvents, setActivityEvents] = useState<ChangeEvent[]>([]);
  const [activityCount, setActivityCount] = useState(0);
  const [history, setHistory] = useState<unknown>(null);
  const [area, setArea] = useState("business");
  const [kind, setKind] = useState("preparation");
  const [title, setTitle] = useState("Business receipts review");
  const [answer, setAnswer] = useState("");
  const [authority, setAuthority] = useState("");
  const [refs, setRefs] = useState("D16");
  const [applicability, setApplicability] = useState("applicable");
  const [editing, setEditing] = useState<Item | null>(null);
  const [noteTitle, setNoteTitle] = useState("Business receipts discrepancy");
  const [note, setNote] = useState("");
  const [owner, setOwner] = useState("st-01");
  const [assignee, setAssignee] = useState("st-04");
  const [assignmentArea, setAssignmentArea] = useState("*");
  const [threshold, setThreshold] = useState("1000");
  const [percent, setPercent] = useState("10");
  const [varianceAmount, setVarianceAmount] = useState("1000");
  const [dueDate, setDueDate] = useState("");
  const [enabledMethods, setEnabledMethods] = useState<string[] | null>(null);
  const [reason, setReason] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [viewEpoch, setViewEpoch] = useState(0);
  const isAdmin = identity.role === "firm_administrator";
  const fullAccess = !!data?.memberships.some(
    (m) =>
      m.data.staff_id === identity.id &&
      m.state === "active" &&
      (m.data.areas as string[]).includes("*"),
  );
  const canView = isAdmin
    ? [
        "dashboard",
        "readiness",
        "tasks",
        "assignments",
        "operations",
        "security",
      ].includes(tab)
    : fullAccess || scopedViews.includes(tab);
  const manager = isAdmin || identity.role === "partner";
  const reviewer = ["reviewer", "partner"].includes(identity.role);
  const refresh = useCallback(async () => {
    const d = await request<Overview>("/api/workflow/overview");
    setData(d);
    const full =
      isAdmin ||
      d.memberships.some(
        (m) =>
          m.data.staff_id === identity.id &&
          m.state === "active" &&
          (m.data.areas as string[]).includes("*"),
      );
    if (full) setReadiness(await request<Readiness>("/api/workflow/readiness"));
    else
      setReadiness({
        filing_ready: false,
        blockers: [],
        label:
          "Area-restricted view; use Collaboration for assigned work. Full readiness requires an entire-engagement assignment",
      });
  }, [identity.id, isAdmin]);
  useEffect(() => {
    let active = true;
    request<Overview>("/api/workflow/overview")
      .then((d) => {
        if (active) setData(d);
        return d;
      })
      .then((d) =>
        isAdmin ||
        d.memberships.some(
          (m) =>
            m.data.staff_id === identity.id &&
            m.state === "active" &&
            (m.data.areas as string[]).includes("*"),
        )
          ? request<Readiness>("/api/workflow/readiness")
          : Promise.resolve({
              filing_ready: false,
              blockers: [],
              label:
                "Area-restricted view; use Collaboration for assigned work. Full readiness requires an entire-engagement assignment",
            }),
      )
      .then((r) => active && setReadiness(r))
      .catch((e) => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, [identity.id, isAdmin]);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const update = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(
        () => void refresh().catch((e) => setError(String(e))),
        150,
      );
    };
    window.addEventListener("workpaper:changes", update);
    return () => {
      window.removeEventListener("workpaper:changes", update);
      if (timer) clearTimeout(timer);
    };
  }, [refresh]);
  async function act(path: string, body: object) {
    if (
      /assignments|policies|\/(approve|reopen|resolve|revoke)$/.test(path) &&
      !(await confirm({
        title: "Confirm review change",
        description:
          "This changes engagement workflow records. The backend will validate your role, revision and independence; history will be preserved.",
      }))
    )
      return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await request(path, body);
      await refresh();
      setMessage("Saved with audit history.");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  function edit(r: Item) {
    setEditing(r);
    setArea(r.area);
    setKind(String(r.data.record_type));
    setTitle(String(r.data.title));
    setAnswer(String(r.data.answer ?? ""));
    setAuthority(String(r.data.authority ?? ""));
    setRefs(((r.data.refs as string[]) ?? []).join(", "));
    setApplicability(String(r.data.applicability ?? "unknown"));
    setTab("diligence");
  }
  async function sign() {
    if (
      !(await confirm({
        title: "Record demonstration sign-off?",
        description:
          "This binds your selected demonstration identity to the current dependency digest. Relevant changes permanently invalidate this sign-off. This is not a legal electronic signature.",
      }))
    )
      return;
    setBusy(true);
    setError("");
    try {
      const level = identity.role === "partner" ? "partner" : "reviewer";
      const p = await request<{ digest: string }>(
        "/api/workflow/signoff-preview?area=" + area + "&level=" + level,
      );
      await request("/api/workflow/signoffs", {
        area,
        level,
        expected_digest: p.digest,
        note:
          note || "Reviewed scoped workpaper dependencies as a demonstration.",
      });
      await refresh();
      setMessage(
        "Demonstration sign-off recorded. No legal electronic signature was created.",
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function audit(path: string) {
    try {
      setHistory(await request(path));
    } catch (e) {
      setError(String(e));
    }
  }
  async function toggleSensitive() {
    if (!revealed && reason.trim().length < 8) {
      setError("Enter a meaningful purpose before revealing sensitive fields.");
      return;
    }
    if (
      !revealed &&
      !(await confirm({
        title: "Access protected information?",
        description:
          "Your stated purpose and access will be audited. Protected content will be cleared when the identity changes.",
      }))
    )
      return;
    sensitiveAccess(!revealed, reason);
    setRevealed(!revealed);
    setHistory(null);
    setData(null);
    setViewEpoch((v) => v + 1);
    setBusy(true);
    try {
      await refresh();
    } catch (e) {
      sensitiveAccess(false, "");
      setRevealed(false);
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <NavigationContext.Provider value={navigation}>
      <AppShell
        view={tab}
        onNavigate={navigation.navigate}
        identity={identity}
        sessionControls={sessionControls}
        revealed={revealed}
        fullAccess={
          !!data?.memberships.some(
            (m) =>
              m.data.staff_id === identity.id &&
              m.state === "active" &&
              (m.data.areas as string[]).includes("*"),
          )
        }
        activityOpen={activityOpen}
        onActivityOpen={setActivityOpen}
        activityCount={activityCount}
        activity={
          !isAdmin ? (
            <>
              <LiveUpdates
                key={"live-" + viewEpoch}
                onActivity={setActivityEvents}
                onCount={setActivityCount}
                refresh={() => {
                  setViewEpoch((v) => v + 1);
                  void refresh().catch((e) => setError(String(e)));
                }}
              />
              <section className="assigned-notifications">
                <h3>Assigned notifications</h3>
                {data?.notifications.length ? (
                  data.notifications.map((n) => (
                    <article key={n.id}>
                      <strong>
                        {String(n.data.title ?? n.data.message ?? n.id)}
                      </strong>
                      <p>
                        {n.state} · {n.area}
                      </p>
                    </article>
                  ))
                ) : (
                  <p>No assigned notifications in this view.</p>
                )}
                <button
                  className="ui-button secondary"
                  onClick={() => {
                    setActivityOpen(false);
                    navigation.navigate("tasks");
                  }}
                >
                  Open tasks & notification acknowledgments
                </button>
              </section>
            </>
          ) : (
            <p>
              Administrative assignment notifications are available under Tasks.
            </p>
          )
        }
      >
        <div
          className="feature-workspace firm-workspace"
          data-loaded={data ? "true" : "false"}
        >
          {![
            "dashboard",
            ...workpaperViews,
            ...Object.keys(analysisViews),
            ...Object.keys(filingViews),
            "collaboration",
            "attachments",
            "bulk",
            "operations",
          ].includes(tab) && (
            <PageHeader
              title={viewInfo(tab).label}
              description="Evidence-backed review · Changes are recorded with append-only audit history."
            />
          )}
          {!data ? (
            <Skeleton />
          ) : !canView ? (
            <EmptyState
              title="This workspace requires a broader assignment"
              description="Your session has access to assigned operational areas only. Ask a partner or administrator to review engagement assignments."
            />
          ) : (
            <>
              {data && tab === "dashboard" && (
                <EngagementDashboard
                  workflow={data}
                  readiness={readiness}
                  fullAccess={data.memberships.some(
                    (m) =>
                      m.data.staff_id === identity.id &&
                      m.state === "active" &&
                      (m.data.areas as string[]).includes("*"),
                  )}
                  admin={isAdmin}
                  navigate={navigation.navigate}
                  activity={activityEvents}
                  openActivity={() => setActivityOpen(true)}
                />
              )}
              {error && (
                <p role="alert" className="rounded bg-red-100 p-3">
                  {error}
                </p>
              )}
              {message && (
                <p role="status" className="rounded bg-green-100 p-3">
                  {message}
                </p>
              )}
              {!data && <Skeleton />}
              {data && tab === "readiness" && (
                <section>
                  <h2 className="text-xl font-semibold">Filing Readiness</h2>
                  <p data-testid="filing-readiness" className="my-3 font-bold">
                    {readiness?.filing_ready
                      ? "Ready for workpaper review"
                      : "FILING BLOCKED"}
                  </p>
                  <p>
                    {readiness?.label}. The real packet requires actual
                    prerequisites; scripted future events do not clear blockers.
                  </p>
                  <button
                    className={button}
                    disabled={busy}
                    onClick={() => void act("/api/workflow/readiness", {})}
                  >
                    Record readiness assessment
                  </button>
                  {readiness?.blockers.map((b) => (
                    <details key={b.code} className="my-2 rounded border p-3">
                      <summary>
                        <span>{humanize(b.code)}</span>{" "}
                        <small className="block text-xs text-slate-500">
                          {b.code} · {b.resources.length} affected records
                        </small>
                      </summary>
                      <ul className="list-inside list-disc">
                        {b.resources.map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    </details>
                  ))}
                </section>
              )}
              {data && tab === "assignments" && (
                <section className="space-y-3">
                  <h2 className="text-xl font-semibold">
                    Assignments and firm standards
                  </h2>
                  <ul>
                    {data.memberships.map((m) => (
                      <li key={m.id}>
                        {String(m.data.staff_id)} ·{" "}
                        {String(m.data.responsibility)} ·{" "}
                        {(m.data.areas as string[]).join(", ")} · {m.state}
                      </li>
                    ))}
                  </ul>
                  {manager && (
                    <div className="flex flex-wrap gap-2">
                      <label>
                        Assign staff{" "}
                        <select
                          aria-label="Assign staff"
                          className={control}
                          value={assignee}
                          onChange={(e) => setAssignee(e.target.value)}
                        >
                          {data.staff.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.id} {s.name} ({s.role})
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Assignment areas{" "}
                        <input
                          aria-label="Assignment areas"
                          className={control}
                          value={assignmentArea}
                          onChange={(e) => setAssignmentArea(e.target.value)}
                        />
                      </label>
                      {["active", "inactive"].map((state) => (
                        <button
                          key={state}
                          className={button}
                          disabled={busy}
                          onClick={() =>
                            void act("/api/workflow/assignments", {
                              staff_id: assignee,
                              responsibility: data.staff.find(
                                (s) => s.id === assignee,
                              )?.role,
                              areas: assignmentArea
                                .split(",")
                                .map((v) => v.trim()),
                              state,
                              expected_revision:
                                data.memberships.find(
                                  (m) => m.data.staff_id === assignee,
                                )?.revision ?? 0,
                            })
                          }
                        >
                          {state === "active"
                            ? "Assign / activate"
                            : "Remove assignment"}
                        </button>
                      ))}
                    </div>
                  )}
                  {manager && (
                    <button
                      className={button}
                      disabled={busy}
                      onClick={() =>
                        void act("/api/workflow/engagement", {
                          owner_id: "st-03",
                          expected_revision: data.engagement.revision,
                        })
                      }
                    >
                      Confirm assigned partner ownership
                    </button>
                  )}
                  <RecordDetails value={data.policy} />
                  {isAdmin && (
                    <div className="space-y-2">
                      <p>
                        Policies are immutable revisions. Independence and
                        mandatory blockers cannot be waived.
                      </p>
                      <label>
                        Partner tax-effect threshold{" "}
                        <input
                          aria-label="Partner threshold"
                          className={control}
                          value={threshold}
                          onChange={(e) => setThreshold(e.target.value)}
                        />
                      </label>
                      <label>
                        Prior-year variance percent{" "}
                        <input
                          className={control}
                          aria-label="Variance percent"
                          value={percent}
                          onChange={(e) => setPercent(e.target.value)}
                        />
                      </label>
                      <label>
                        Prior-year variance amount{" "}
                        <input
                          className={control}
                          aria-label="Variance amount"
                          value={varianceAmount}
                          onChange={(e) => setVarianceAmount(e.target.value)}
                        />
                      </label>
                      <fieldset>
                        <legend>Allowed verification methods</legend>
                        {data.available_verification_methods.map((method) => (
                          <label className="mr-3 inline-block" key={method}>
                            <input
                              type="checkbox"
                              aria-label={`Allow ${method}`}
                              checked={(
                                enabledMethods ??
                                (data.policy.policy
                                  .verification_methods as string[])
                              ).includes(method)}
                              onChange={(e) => {
                                const current =
                                  enabledMethods ??
                                  (data.policy.policy
                                    .verification_methods as string[]);
                                setEnabledMethods(
                                  e.target.checked
                                    ? [...current, method]
                                    : current.filter((m) => m !== method),
                                );
                              }}
                            />
                            {method}
                          </label>
                        ))}
                      </fieldset>
                      <label>
                        Policy rationale{" "}
                        <input
                          aria-label="Policy rationale"
                          className={control}
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                        />
                      </label>
                      <button
                        className={button}
                        disabled={busy}
                        onClick={() =>
                          void act("/api/workflow/policies", {
                            expected_revision: data.policy.revision,
                            changes: {
                              partner_threshold: threshold,
                              verification_methods:
                                enabledMethods ??
                                data.policy.policy.verification_methods,
                              variance_review: {
                                compare_to: "prior_year",
                                flag_if_change_over_percent: Number(percent),
                                and_over_amount: Number(varianceAmount),
                              },
                            },
                            rationale: reason,
                          })
                        }
                      >
                        Publish policy revision
                      </button>
                    </div>
                  )}
                </section>
              )}
              {data && tab === "diligence" && !isAdmin && (
                <section className="space-y-3">
                  <h2 className="text-xl font-semibold">
                    Due diligence, elections, and professional questions
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    <label>
                      Tax area{" "}
                      <select
                        aria-label="Record area"
                        className={control}
                        value={area}
                        onChange={(e) => setArea(e.target.value)}
                      >
                        {data.areas.map((a) => (
                          <option key={a}>{a}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Record type{" "}
                      <select
                        aria-label="Record type"
                        className={control}
                        value={kind}
                        onChange={(e) => setKind(e.target.value)}
                      >
                        {data.record_types.map((a) => (
                          <option key={a}>{a}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Applicability{" "}
                      <select
                        aria-label="Record applicability"
                        className={control}
                        value={applicability}
                        onChange={(e) => setApplicability(e.target.value)}
                      >
                        {["unknown", "applicable", "not_applicable"].map(
                          (v) => (
                            <option key={v}>{v}</option>
                          ),
                        )}
                      </select>
                    </label>
                  </div>
                  <input
                    aria-label="Record title"
                    className={control + " w-full"}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                  <textarea
                    aria-label="Record answer"
                    placeholder="Document tax-practice conclusion or unresolved question"
                    className={control + " w-full"}
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                  />
                  <input
                    aria-label="Record authority"
                    placeholder="Authority and method"
                    className={control + " w-full"}
                    value={authority}
                    onChange={(e) => setAuthority(e.target.value)}
                  />
                  <input
                    aria-label="Record references"
                    className={control + " w-full"}
                    value={refs}
                    onChange={(e) => setRefs(e.target.value)}
                  />
                  <button
                    className={button}
                    disabled={busy}
                    onClick={() =>
                      void act("/api/workflow/records", {
                        id: editing?.id ?? null,
                        area,
                        record_type: kind,
                        title,
                        applicability,
                        answer,
                        authority,
                        refs: refs
                          .split(",")
                          .map((r) => r.trim())
                          .filter(Boolean),
                        expected_revision: editing?.revision ?? 0,
                      }).then(() => setEditing(null))
                    }
                  >
                    {editing
                      ? "Save record revision"
                      : "Create workflow record"}
                  </button>
                  {editing && (
                    <button className={button} onClick={() => setEditing(null)}>
                      Cancel editing
                    </button>
                  )}
                  <ul>
                    {data.records.map((r) => (
                      <li key={r.id} className="my-2 rounded border p-3">
                        <strong>{String(r.data.title)}</strong> · {r.area} ·{" "}
                        <span>{r.state}</span> · authors{" "}
                        {r.authors.join(", ") || "not attributed"}
                        <p>{String(r.data.answer ?? "")}</p>
                        <div className="flex flex-wrap gap-2">
                          <button className={button} onClick={() => edit(r)}>
                            Edit {r.id}
                          </button>
                          {(["submit", "approve", "reopen"] as const)
                            .filter((a) =>
                              a === "submit"
                                ? ["draft", "open"].includes(r.state)
                                : a === "approve"
                                  ? reviewer && r.state === "submitted"
                                  : reviewer && r.state === "approved",
                            )
                            .map((action) => (
                              <button
                                className={button}
                                key={action}
                                disabled={busy}
                                onClick={() =>
                                  void act(
                                    "/api/workflow/records/" +
                                      r.id +
                                      "/actions",
                                    {
                                      action,
                                      expected_revision: r.revision,
                                      note:
                                        note ||
                                        "Documented independent workflow review.",
                                    },
                                  )
                                }
                              >
                                {action} {r.id}
                              </button>
                            ))}
                          <button
                            className={button}
                            onClick={() =>
                              void audit(
                                "/api/workflow/history?entity_id=" +
                                  encodeURIComponent(r.id),
                              )
                            }
                          >
                            History {r.id}
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {data && tab === "notes" && !isAdmin && (
                <section className="space-y-3">
                  <h2 className="text-xl font-semibold">
                    Blocking review notes
                  </h2>
                  <p>
                    Every open, responded, or resolution-requested note blocks
                    filing. An independent reviewer must resolve it.
                  </p>
                  <label>
                    Note area{" "}
                    <select
                      aria-label="Note area"
                      className={control}
                      value={area}
                      onChange={(e) => setArea(e.target.value)}
                    >
                      {data.areas.map((a) => (
                        <option key={a}>{a}</option>
                      ))}
                    </select>
                  </label>
                  <input
                    aria-label="Note title"
                    className={control}
                    value={noteTitle}
                    onChange={(e) => setNoteTitle(e.target.value)}
                  />
                  <textarea
                    aria-label="Review note"
                    className={control + " w-full"}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                  <label>
                    Note owner{" "}
                    <select
                      aria-label="Note owner"
                      className={control}
                      value={owner}
                      onChange={(e) => setOwner(e.target.value)}
                    >
                      {data.staff.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.id} {s.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className={button}
                    disabled={busy}
                    onClick={() =>
                      void act("/api/workflow/notes", {
                        area,
                        action: "create",
                        title: noteTitle,
                        note,
                        owner_id: owner,
                        expected_revision: 0,
                      })
                    }
                  >
                    Create blocking note
                  </button>
                  {data.notes.map((n) => (
                    <article className="rounded border p-3" key={n.id}>
                      <strong>{String(n.data.title)}</strong> · {n.area} ·{" "}
                      {n.state}
                      <p>{String(n.data.note)}</p>
                      {(n.state === "open" || n.state === "reopened"
                        ? ["respond"]
                        : n.state === "responded"
                          ? ["request_resolution"]
                          : n.state === "resolution_requested" && reviewer
                            ? ["resolve"]
                            : n.state === "resolved" && reviewer
                              ? ["reopen"]
                              : []
                      ).map((action) => (
                        <button
                          className={button}
                          disabled={busy}
                          key={action}
                          onClick={() =>
                            void act("/api/workflow/notes", {
                              id: n.id,
                              area: n.area,
                              action,
                              title: n.data.title,
                              note: note || n.data.note,
                              owner_id: n.data.owner_id,
                              expected_revision: n.revision,
                            })
                          }
                        >
                          {action.replaceAll("_", " ")} {n.id}
                        </button>
                      ))}
                      <button
                        className={button}
                        onClick={() =>
                          void audit("/api/workflow/history?entity_id=" + n.id)
                        }
                      >
                        Note history
                      </button>
                    </article>
                  ))}
                </section>
              )}
              {data && tab === "signoffs" && !isAdmin && (
                <section className="space-y-3">
                  <h2 className="text-xl font-semibold">
                    Dependency-aware demonstration sign-offs
                  </h2>
                  <p>
                    Sign-offs bind current evidence, computations, reviews,
                    policy, and scoped assignments. Invalidation is permanent; a
                    fresh review is required.
                  </p>
                  <label>
                    Sign-off area{" "}
                    <select
                      aria-label="Sign-off area"
                      className={control}
                      value={area}
                      onChange={(e) => setArea(e.target.value)}
                    >
                      {data.areas.map((a) => (
                        <option key={a}>{a}</option>
                      ))}
                    </select>
                  </label>
                  {reviewer && (
                    <button
                      className={button}
                      disabled={busy}
                      onClick={() => void sign()}
                    >
                      Record demonstration {identity.role} sign-off
                    </button>
                  )}
                  {data.signoffs.map((s) => (
                    <article className="rounded border p-3" key={s.id}>
                      {s.area} · {s.level} · {s.staff_id} ·{" "}
                      <strong>{s.state}</strong>
                      <p>{s.reason}</p>
                      {reviewer && s.state === "valid" && (
                        <button
                          className={button}
                          onClick={() =>
                            void act(
                              "/api/workflow/signoffs/" + s.id + "/revoke",
                              {
                                note:
                                  note ||
                                  "Revoked for additional tax-practice review.",
                              },
                            )
                          }
                        >
                          Revoke {s.id}
                        </button>
                      )}
                    </article>
                  ))}
                </section>
              )}
              {data && tab === "tasks" && (
                <section className="space-y-3">
                  <h2 className="text-xl font-semibold">
                    Assignments, deadlines, and notifications
                  </h2>
                  <label>
                    New deadline (optional){" "}
                    <input
                      aria-label="Task deadline"
                      type="date"
                      className={control}
                      value={dueDate}
                      onChange={(e) => setDueDate(e.target.value)}
                    />
                  </label>
                  <label>
                    Task assignee{" "}
                    <select
                      aria-label="Task assignee"
                      className={control}
                      value={assignee}
                      onChange={(e) => setAssignee(e.target.value)}
                    >
                      {data.staff.map((s) => (
                        <option value={s.id} key={s.id}>
                          {s.id} {s.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {data.tasks.map((t) => (
                    <article key={t.id} className="rounded border p-3">
                      {String(t.data.title)} · {String(t.data.due_date)} ·{" "}
                      {String(t.data.assignee ?? "unassigned")} · {t.state}
                      {(manager || t.data.assignee === identity.id) && (
                        <>
                          <button
                            className={button}
                            disabled={busy}
                            onClick={() =>
                              void act("/api/workflow/tasks", {
                                id: t.id,
                                state:
                                  t.state === "complete" ? "open" : "complete",
                                assignee: manager ? assignee : t.data.assignee,
                                due_date: dueDate || null,
                                expected_revision: t.revision,
                              })
                            }
                          >
                            {t.state === "complete"
                              ? "Reopen task"
                              : "Complete task"}
                          </button>
                          {manager && (
                            <button
                              className={button}
                              disabled={busy}
                              onClick={() =>
                                void act("/api/workflow/tasks", {
                                  id: t.id,
                                  state: t.state,
                                  assignee,
                                  due_date: dueDate || null,
                                  expected_revision: t.revision,
                                })
                              }
                            >
                              Assign task
                            </button>
                          )}
                        </>
                      )}
                    </article>
                  ))}
                  {data.notifications.map((n) => (
                    <article key={n.id}>
                      {String(n.data.title)} · {n.state}
                      {n.state === "unread" && (
                        <button
                          className={button}
                          onClick={() =>
                            void act("/api/workflow/tasks", {
                              id: n.id,
                              state: "read",
                              expected_revision: n.revision,
                            })
                          }
                        >
                          Acknowledge {n.id}
                        </button>
                      )}
                    </article>
                  ))}
                </section>
              )}
              {tab === "security" && (
                <section className="space-y-3">
                  <h2 className="text-xl font-semibold">
                    Sensitive-data access controls
                  </h2>
                  <p>
                    Default: masked responses and simulated source documents.
                    Reveals require packet clearance, engagement access, a
                    purpose, and an append-only access event.
                  </p>
                  <p>
                    Session assurance: {identity.assurance}. Legal electronic
                    signature: never.
                  </p>
                  <input
                    aria-label="Sensitive access purpose"
                    className={control + " w-full"}
                    placeholder="Purpose for accessing sensitive information"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  <button
                    className={button}
                    disabled={
                      busy || !identity.sensitive_data_clearance || isAdmin
                    }
                    onClick={toggleSensitive}
                  >
                    {revealed
                      ? "Mask sensitive information"
                      : "Reveal sensitive information"}
                  </button>
                  <p data-testid="sensitive-mode">
                    {revealed
                      ? "Sensitive reveal active; each request is audited"
                      : "Sensitive information masked"}
                  </p>
                  {manager && (
                    <button
                      className={button}
                      onClick={() => void audit("/api/workflow/access-history")}
                    >
                      View sensitive access audit
                    </button>
                  )}
                  <button
                    className={button}
                    onClick={() => void audit("/api/workflow/history")}
                  >
                    View workflow audit
                  </button>
                </section>
              )}
              {history !== null && (
                <details open>
                  <summary>Audit history</summary>
                  <pre
                    data-testid="workflow-audit"
                    className="max-h-96 overflow-auto whitespace-pre-wrap text-xs"
                  >
                    {JSON.stringify(history, null, 2)}
                  </pre>
                  <button className={button} onClick={() => setHistory(null)}>
                    Close history
                  </button>
                </details>
              )}
              {filingViews[tab] && !isAdmin && (
                <FilingLifecycleWorkspace
                  key={viewEpoch}
                  section={filingViews[tab]}
                  onSectionChange={(name) =>
                    navigation.navigate(
                      Object.keys(filingViews).find(
                        (k) => filingViews[k] === name,
                      ) ?? "finalization",
                    )
                  }
                />
              )}
              {["collaboration", "attachments", "bulk"].includes(tab) &&
                !isAdmin && (
                  <ProductWorkspace
                    key={"collaboration-" + viewEpoch}
                    section={
                      tab === "collaboration"
                        ? "Questions & Responses"
                        : tab === "attachments"
                          ? "Evidence Attachments"
                          : "Bulk Actions"
                    }
                  />
                )}
              {tab === "operations" && (
                <ProductWorkspace
                  operationsOnly
                  key={"operations-" + viewEpoch}
                />
              )}
              {analysisViews[tab] && !isAdmin && (
                <ChangeAnalysisWorkspace
                  key={viewEpoch}
                  section={analysisViews[tab]}
                />
              )}
              {workpaperViews.includes(tab) && !isAdmin && (
                <div key={viewEpoch}>{children}</div>
              )}
            </>
          )}
        </div>
      </AppShell>
    </NavigationContext.Provider>
  );
}
