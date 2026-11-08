"use client";
import { useEffect, useState } from "react";
import type { Lineage } from "./workpaper-types";
import { evidenceRequest, type Resolution } from "./evidence-types";
import { EmptyState, StatusBadge } from "./ui/primitives";
type Finding = {
  id: string;
  title: string;
  status: string;
  refs: string[];
  issue_key: string;
  reconciliations: string[];
};
type Check = { id: string; target: string | null; conclusion: string };
/** Reads stored values and reference relationships; performs no tax computation. */
export default function ReturnLineContext({
  lineage,
  version,
  onFinding,
  onReference,
}: {
  lineage: Lineage;
  version: string;
  onFinding: (id: string) => void;
  onReference: (ref: string) => void;
}) {
  const [prior, setPrior] = useState<Resolution | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [checks, setChecks] = useState<Check[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([
      evidenceRequest<Resolution>(
        `/api/evidence-resolution?ref=${encodeURIComponent("py:/return_2024/lines/" + lineage.key)}&version=${version}`,
      ),
      evidenceRequest<{ findings: Finding[]; checks: Check[] }>(
        `/api/unified-findings?version=${version}`,
      ),
    ])
      .then(([p, f]) => {
        if (!active) return;
        setPrior(p);
        const checks = f.checks.filter((c) => c.target === lineage.key);
        setChecks(checks);
        setFindings(
          f.findings.filter(
            (item) =>
              item.refs.includes(lineage.key) ||
              item.reconciliations.some((id) =>
                checks.some((c) => c.id === id),
              ),
          ),
        );
      })
      .catch(() => {
        if (active)
          setError(
            "Related review or prior-year information could not be loaded. No verification is implied.",
          );
      });
    return () => {
      active = false;
    };
  }, [lineage.key, version]);
  const refs = new Set<string>();
  function collect(n: Lineage) {
    n.sources?.forEach((s) => refs.add(s.ref));
    n.inputs?.forEach(collect);
  }
  collect(lineage);
  return (
    <section className="line-context" data-testid="return-line-context">
      <div className="line-context-metrics">
        <div>
          <small>Supporting references</small>
          <strong>{refs.size}</strong>
        </div>
        <div>
          <small>Related findings</small>
          <strong>{findings?.length ?? "—"}</strong>
        </div>
      </div>
      <div className="prior-year-comparison">
        <span>Prior-year reported value</span>
        <strong>
          {prior?.status === "resolved" && typeof prior.value === "number"
            ? new Intl.NumberFormat("en-US", {
                maximumFractionDigits: 2,
              }).format(prior.value)
            : prior?.status === "resolved"
              ? String(prior.value)
              : "Not supplied"}
        </strong>
        {prior?.status === "resolved" ? (
          <button
            className="text-button"
            onClick={() => onReference(prior.ref)}
          >
            Inspect prior-year evidence
          </button>
        ) : (
          <small>{prior?.reason ?? "Loading prior-year reference…"}</small>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      <h4>Independent reconciliation</h4>
      {checks.length ? (
        <div className="badge-stack">
          {checks.map((c) => (
            <StatusBadge key={c.id} value={c.conclusion} />
          ))}
        </div>
      ) : (
        <p className="muted">
          No targeted independent check for this line. Engine output is not
          assumed correct.
        </p>
      )}
      {findings?.length ? (
        <div className="related-findings">
          {findings.slice(0, 5).map((f) => (
            <button key={f.id} onClick={() => onFinding(f.id)}>
              <span>{f.title}</span>
              <StatusBadge value={f.status} />
            </button>
          ))}
          {findings.length > 5 && (
            <button onClick={() => onFinding(findings[0].id)}>
              Open all {findings.length} related findings
            </button>
          )}
        </div>
      ) : (
        findings && (
          <EmptyState
            title="No linked finding"
            description="This is not proof that the line has been verified."
          />
        )
      )}
    </section>
  );
}
