"use client";
import { useEffect, useState, type ReactNode } from "react";
import {
  Bell,
  ChevronDown,
  ChevronRight,
  Command,
  LockKeyhole,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import type { StaffIdentity } from "../session";
import { DetailDrawer, EmptyState, StatusBadge } from "../ui/primitives";
import {
  navigationGroups,
  viewInfo,
  workpaperViews,
  scopedViews,
} from "./navigation";

export function AppShell({
  view,
  onNavigate,
  identity,
  children,
  sessionControls,
  activity,
  activityCount = 0,
  activityOpen,
  onActivityOpen,
  fullAccess = true,
  legacy = false,
  revealed = false,
}: {
  view: string;
  onNavigate: (view: string) => void;
  identity: StaffIdentity | null;
  children: ReactNode;
  sessionControls?: ReactNode;
  activity?: ReactNode;
  activityCount?: number;
  activityOpen: boolean;
  onActivityOpen: (open: boolean) => void;
  fullAccess?: boolean;
  legacy?: boolean;
  revealed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [groups, setGroups] = useState<Record<string, boolean>>({});
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const admin = identity?.role === "firm_administrator";
  const info = viewInfo(view);
  const allowed = (id: string, isAdmin?: boolean) =>
    legacy
      ? workpaperViews.includes(id)
      : admin
        ? !!isAdmin
        : fullAccess || scopedViews.includes(id);
  const visibleGroups = navigationGroups
    .map((g) => ({
      ...g,
      items: g.items.filter((i) => allowed(i.id, i.admin)),
    }))
    .filter((g) => g.items.length);
  function navigate(id: string) {
    onNavigate(id);
    setMobile(false);
    setSearchOpen(false);
  }
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  return (
    <div
      className={`app-shell ${collapsed ? "sidebar-collapsed" : ""} ${mobile ? "mobile-nav-open" : ""}`}
    >
      <a href="#main-content" className="skip-link">
        Skip to workpaper content
      </a>
      {mobile && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation overlay"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className="app-sidebar" aria-label="Primary sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span className="brand-name">
            MiraFlores<span>WORKPAPER</span>
          </span>
          <button
            className="icon-button mobile-only"
            aria-label="Close navigation"
            onClick={() => setMobile(false)}
          >
            <X size={18} />
          </button>
        </div>
        <div className="engagement-switch">
          <span className="engagement-avatar">OL</span>
          <div>
            <strong>Okafor–Lindqvist</strong>
            <small>2025 · Individual return</small>
          </div>
        </div>
        <nav aria-label="Main navigation" className="sidebar-navigation">
          {visibleGroups.map((g) => {
            const expanded =
              groups[g.label] ??
              (["Overview", "Tax Workpaper"].includes(g.label) ||
                info.group === g.label);
            return (
              <div className="nav-group" key={g.label}>
                <button
                  className="nav-group-heading"
                  aria-expanded={expanded}
                  onClick={() =>
                    setGroups((old) => ({ ...old, [g.label]: !expanded }))
                  }
                >
                  <span>{g.label}</span>
                  <ChevronRight
                    size={12}
                    className={expanded ? "rotate-90" : ""}
                  />
                </button>
                {expanded && (
                  <div className="nav-group-items">
                    {g.items.map((i) => (
                      <button
                        title={i.label}
                        data-view={i.id}
                        aria-current={view === i.id ? "page" : undefined}
                        key={i.id}
                        className={`sidebar-link ${view === i.id ? "active" : ""}`}
                        onClick={() => navigate(i.id)}
                      >
                        <i.icon size={17} strokeWidth={1.7} />
                        <span>{i.label}</span>
                        {i.id === "readiness" && (
                          <span className="nav-warning-dot" />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
        <footer className="sidebar-footer">
          <div>
            <ShieldCheck size={16} />
            <span>
              Demonstration workspace
              <small>No legal signatures or agency filing</small>
            </span>
          </div>
          <button
            className="collapse-button"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <PanelLeftOpen size={17} />
            ) : (
              <PanelLeftClose size={17} />
            )}
            <span>Collapse sidebar</span>
          </button>
        </footer>
      </aside>
      <div className="app-frame">
        <header className="app-topbar">
          <div className="topbar-leading">
            <button
              className="icon-button mobile-only"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <div className="breadcrumbs">
              <span>{info.group}</span>
              <ChevronRight size={13} />
              <strong>{info.label}</strong>
            </div>
            <div className="engagement-context">
              <span>CL-20417</span>
              <span>TY 2025</span>
              <StatusBadge value="blocked">Filing blocked</StatusBadge>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="demo-indicator">DEMO</span>
            <button
              className="workflow-search"
              onClick={() => setSearchOpen(true)}
              aria-label="Search workflows"
            >
              <Search size={15} />
              <span>Find a workflow…</span>
              <kbd>
                <Command size={10} /> K
              </kbd>
            </button>
            <span
              className={`mask-indicator ${revealed ? "revealed" : ""}`}
              title={
                revealed
                  ? "Sensitive reveal active; each access is audited"
                  : "Sensitive information masked"
              }
            >
              <LockKeyhole size={14} />
              <span>{revealed ? "Audited reveal" : "Masked"}</span>
            </span>
            {activity && (
              <button
                className="icon-button notification-button"
                aria-label="Open activity and notifications"
                onClick={() => onActivityOpen(true)}
              >
                <Bell size={18} />
                {activityCount > 0 && (
                  <span>{activityCount > 99 ? "99+" : activityCount}</span>
                )}
              </button>
            )}
            <details className="identity-popover">
              <summary aria-label="Switch staff session">
                <span className="staff-avatar">
                  {identity?.name
                    .split(" ")
                    .map((n) => n[0])
                    .join("") ?? "MF"}
                </span>
                <span className="identity-name" data-testid="current-session">
                  {identity
                    ? `${identity.name} (${identity.id}) · ${identity.role}`
                    : "Isolated regression profile"}
                </span>
                <ChevronDown size={13} />
              </summary>
              <div className="session-popover">
                <p className="eyebrow">Session & identity</p>
                {identity && (
                  <>
                    <h3>{identity.name}</h3>
                    <p>
                      {identity.role} · {identity.assurance}
                    </p>
                  </>
                )}
                <div className="notice warning">
                  Demo identity selection does not establish authenticated
                  identity or a legally valid signature.
                </div>
                {sessionControls}
              </div>
            </details>
          </div>
        </header>
        <main id="main-content" className="app-main" tabIndex={-1}>
          {children}
        </main>
        <footer className="app-footer">
          <span>MiraFlores · Tax workpaper</span>
          <span>Original engine packet preserved · Demonstration only</span>
        </footer>
      </div>
      <DetailDrawer
        open={activityOpen}
        onClose={() => onActivityOpen(false)}
        title="Activity & notifications"
        description="Authorized changes, personal checkpoints, and assigned notifications."
      >
        {activity}
      </DetailDrawer>
      <DetailDrawer
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        title="Find a workflow"
        description="Navigate the engagement. Search source documents and return lines within their explorers."
      >
        <div className="command-search">
          <Search size={17} />
          <input
            aria-label="Search application workflows"
            autoFocus
            placeholder="Type a workflow name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="command-results">
          {visibleGroups.flatMap((g) =>
            g.items
              .filter((i) =>
                `${g.label} ${i.label}`
                  .toLowerCase()
                  .includes(query.toLowerCase()),
              )
              .map((i) => (
                <button key={i.id} onClick={() => navigate(i.id)}>
                  <i.icon size={18} />
                  <span>
                    <strong>{i.label}</strong>
                    <small>{g.label}</small>
                  </span>
                  <ChevronRight size={14} />
                </button>
              )),
          )}
        </div>
        {!visibleGroups.some((g) =>
          g.items.some((i) =>
            i.label.toLowerCase().includes(query.toLowerCase()),
          ),
        ) && (
          <EmptyState
            title="No matching workflow"
            description="Try documents, review, payments or assignments."
          />
        )}
      </DetailDrawer>
    </div>
  );
}
