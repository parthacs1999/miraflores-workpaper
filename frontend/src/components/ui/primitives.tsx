"use client";

import {
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileSearch,
  Info,
  ShieldCheck,
  X,
} from "lucide-react";

export function humanize(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
export function StatusBadge({
  value,
  children,
}: {
  value: string;
  children?: ReactNode;
}) {
  const tone =
    /invalid|stale|reassess|critical|high|exact_mismatch|material_discrepancy|blocked|reject|error|missing|unresolved|revoked/.test(
      value,
    )
      ? "danger"
      : /pending|submitted|unverified|unextracted|requires_review|in_review|open|draft|hypothetical|simulation|unsupported|ambiguous/.test(
            value,
          )
        ? "warning"
        : /approved|resolved|confirmed|valid|complete|reviewed|accepted|\bused\b/.test(
              value,
            )
          ? "success"
          : "neutral";
  return (
    <span className={`status-badge ${tone}`}>
      <span className="status-dot" />
      {children ?? humanize(value)}
    </span>
  );
}
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}
export function StatCard({
  label,
  value,
  description,
  icon,
  action,
}: {
  label: string;
  value: ReactNode;
  description?: string;
  icon?: ReactNode;
  action?: () => void;
}) {
  const body = (
    <>
      <div className="stat-heading">
        <span>{label}</span>
        {icon}
      </div>
      <div className="stat-value">{value}</div>
      {description && <p>{description}</p>}
      {action && <ArrowRight size={15} className="stat-arrow" />}
    </>
  );
  return action ? (
    <button className="stat-card" onClick={action}>
      {body}
    </button>
  ) : (
    <div className="stat-card">{body}</div>
  );
}
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <FileSearch size={23} />
      </span>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div role="alert" className="error-state">
      <AlertCircle size={18} />
      <div>
        <strong>We couldn’t complete that request</strong>
        <p>{message}</p>
        {retry && <button onClick={retry}>Try again</button>}
      </div>
    </div>
  );
}
export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div
      className="skeleton-stack"
      role="status"
      aria-label="Loading workspace"
      aria-busy="true"
    >
      {Array.from({ length: rows }, (_, i) => (
        <div
          className="skeleton"
          style={{ width: i === 0 ? "44%" : i % 2 ? "100%" : "82%" }}
          key={i}
        />
      ))}
    </div>
  );
}
export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "warning" | "danger";
}) {
  return (
    <div className={`notice ${tone}`}>
      <Info size={16} />
      <div>{children}</div>
    </div>
  );
}
export function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="form-field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function SectionCard({
  title,
  description,
  action,
  children,
  className = "",
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`section-card ${className}`}>
      {(title || action) && (
        <header className="section-heading">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="section-body">{children}</div>
    </section>
  );
}
export function DetailDrawer({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    else if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`detail-drawer ${wide ? "wide" : ""}`}
      aria-labelledby={id}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="drawer-surface">
        <header className="drawer-heading">
          <div>
            <h2 id={id}>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button
            className="icon-button"
            aria-label={`Close ${title}`}
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </header>
        <div className="drawer-body">{children}</div>
      </div>
    </dialog>
  );
}
type Confirmation = {
  title: string;
  description: string;
  confirmLabel?: string;
  danger?: boolean;
};
const ConfirmationContext = createContext<
  (options: Confirmation) => Promise<boolean>
>(async () => false);
export function useConfirm() {
  return useContext(ConfirmationContext);
}
export function ConfirmationProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<Confirmation | null>(null);
  const resolver = useRef<((v: boolean) => void) | null>(null);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (options && !dialog?.open) dialog?.showModal();
    else if (!options && dialog?.open) dialog.close();
  }, [options]);
  useEffect(() => () => resolver.current?.(false), []);
  function finish(result: boolean) {
    resolver.current?.(result);
    resolver.current = null;
    setOptions(null);
  }
  return (
    <ConfirmationContext.Provider
      value={(o) =>
        new Promise((resolve) => {
          resolver.current?.(false);
          resolver.current = resolve;
          setOptions(o);
        })
      }
    >
      {children}
      <dialog
        ref={ref}
        className="confirm-dialog"
        role="alertdialog"
        aria-label="Confirm workpaper action"
        onCancel={() => finish(false)}
      >
        <span
          className={`confirmation-icon ${options?.danger ? "danger" : ""}`}
        >
          <ShieldCheck size={24} />
        </span>
        <h2>{options?.title}</h2>
        <p>{options?.description}</p>
        <div className="dialog-actions">
          <button className="ui-button secondary" onClick={() => finish(false)}>
            Cancel
          </button>
          <button
            className={`ui-button ${options?.danger ? "destructive" : "primary"}`}
            onClick={() => finish(true)}
          >
            Confirm action
          </button>
        </div>
      </dialog>
    </ConfirmationContext.Provider>
  );
}
export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pagination">
      <span>
        {total === 0
          ? "No results"
          : `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, total)} of ${total}`}
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="Previous page"
          disabled={page === 0}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft size={16} />
        </button>
        <span>
          {page + 1} / {pages}
        </span>
        <button
          className="icon-button"
          aria-label="Next page"
          disabled={page + 1 >= pages}
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty = "No matching records",
}: {
  columns: { key: string; label: string; render: (row: T) => ReactNode }[];
  rows: T[];
  rowKey: (r: T) => string;
  empty?: string;
}) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th scope="col" key={c.key}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)}>
              {columns.map((c) => (
                <td key={c.key}>{c.render(r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <EmptyState title={empty} />}
    </div>
  );
}
export function ActivityTimeline({
  events,
}: {
  events: {
    id: string | number;
    title: string;
    actor?: string;
    at?: string;
    detail?: ReactNode;
  }[];
}) {
  return (
    <ol className="activity-timeline">
      {events.map((e) => (
        <li key={e.id}>
          <span className="timeline-dot">
            <Check size={10} />
          </span>
          <div>
            <strong>{e.title}</strong>
            <p>
              {[e.actor, e.at ? new Date(e.at).toLocaleString() : null]
                .filter(Boolean)
                .join(" · ")}
            </p>
            {e.detail}
          </div>
        </li>
      ))}
    </ol>
  );
}

/** A structured, read-only presentation of backend evidence. Text is never HTML. */
export function RecordDetails({ value }: { value: unknown }) {
  if (value === null || value === undefined)
    return <span className="muted">Not supplied</span>;
  if (typeof value === "string") {
    if (
      (value.startsWith("{") || value.startsWith("[")) &&
      value.length < 100000
    ) {
      let parsed: unknown;
      try {
        parsed = JSON.parse(value);
      } catch {
        /* Narrative text stays text. */
      }
      if (parsed !== undefined) return <RecordDetails value={parsed} />;
    }
    return <span className="record-text">{value}</span>;
  }
  if (typeof value !== "object")
    return <span className="record-value">{String(value)}</span>;
  if (Array.isArray(value)) return <RecordArray values={value} />;
  return (
    <dl className="record-details">
      {Object.entries(value).map(([key, entry]) => (
        <div key={key}>
          <dt>{humanize(key)}</dt>
          <dd>
            {entry && typeof entry === "object" ? (
              <details>
                <summary>
                  Inspect{" "}
                  {Array.isArray(entry)
                    ? `${entry.length} records`
                    : humanize(key)}{" "}
                  <ChevronDown size={12} />
                </summary>
                <RecordDetails value={entry} />
              </details>
            ) : (
              <RecordDetails value={entry} />
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
function RecordArray({ values }: { values: unknown[] }) {
  const [limit, setLimit] = useState(12);
  return (
    <div className="record-array">
      {!values.length && <span className="muted">No records</span>}
      {values.slice(0, limit).map((v, i) => (
        <div key={i}>
          <RecordDetails value={v} />
        </div>
      ))}
      {values.length > limit && (
        <button
          className="ui-button secondary"
          onClick={() => setLimit((n) => n + 24)}
        >
          Show more ({values.length - limit} remaining)
        </button>
      )}
    </div>
  );
}
