
"use client";

import { useWorkpaperIdentity } from "@/components/session";
import { apiFetch } from "@/components/session";

import { useCallback, useEffect, useState } from "react";

const API =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ReviewFinding = {
    id: string;
    code?: string;
    title: string;
    description: string;
    severity: string;
    refs: string[];
    status: ReviewStatus;
    review_note: string;
    updated_by: string | null;
    updated_at: string | null;
};

type ReviewRole = "preparer" | "reviewer" | "partner";

type ReviewStatus =
    | "open"
    | "in_review"
    | "resolved"
    | "escalated";

type ReviewResponse = {
    version: string;
    total: number;
    findings: ReviewFinding[];
    status_counts: Record<ReviewStatus, number>;
};

type ReviewEvent = {
    id: number;
    previous_status: string;
    new_status: string;
    note: string;
    actor_role: string;
    actor_name: string;
    created_at: string;
};

type ReviewWorkspaceProps = {
    version: string;
    onSelectFinding?: (finding: ReviewFinding) => void;
    onOpenReference?: (ref: string) => void;
};

const statuses: {
    value: ReviewStatus;
    label: string;
}[] = [
        { value: "open", label: "Open" },
        { value: "in_review", label: "In Review" },
        { value: "resolved", label: "Resolved" },
        { value: "escalated", label: "Escalated" },
    ];

async function readResponse(response: Response) {
    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            typeof data.detail === "string"
                ? data.detail
                : `Request failed (${response.status})`
        );
    }

    return data;
}

export default function ReviewWorkspace({
    version,
    onSelectFinding,
    onOpenReference,
}: ReviewWorkspaceProps) {
    const [data, setData] = useState<ReviewResponse | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(
        null
    );

    const identity = useWorkpaperIdentity();
    const [legacyRole, setRole] = useState<ReviewRole>("reviewer");
    const role = (identity?.role ?? legacyRole) as ReviewRole;
    const [legacyReviewerName, setReviewerName] = useState(
        "Demo Reviewer"
    );
    const reviewerName = identity?.name ?? legacyReviewerName;
    const [status, setStatus] = useState<ReviewStatus>("open");
    const [note, setNote] = useState("");
    const [history, setHistory] = useState<ReviewEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    const refresh = useCallback(async () => {
        const result = (await apiFetch(
            `${API}/api/reviews?version=${encodeURIComponent(version)}`,
            { cache: "no-store" }
        ).then(readResponse)) as ReviewResponse;

        setData(result);
        return result;
    }, [version]);

    useEffect(() => {
        let active = true;

        async function loadReviews() {
            setLoading(true);
            setSelectedId(null);
            setHistory([]);
            setMessage("");
            setError("");
            setData(null);

            try {
                const result = (await apiFetch(
                    `${API}/api/reviews?version=${encodeURIComponent(
                        version
                    )}`,
                    { cache: "no-store" }
                ).then(readResponse)) as ReviewResponse;

                if (active) {
                    setData(result);
                }
            } catch (err) {
                if (active) {
                    setError(
                        err instanceof Error
                            ? err.message
                            : "Unable to load reviews"
                    );
                }
            } finally {
                if (active) {
                    setLoading(false);
                }
            }
        }

        void loadReviews();

        return () => {
            active = false;
        };
    }, [version]);

    const selected = data?.findings.find(
        (finding) => finding.id === selectedId
    );

    async function loadHistory(findingId: string) {
        const result = await apiFetch(
            `${API}/api/review-history?version=${encodeURIComponent(
                version
            )}&finding_id=${encodeURIComponent(findingId)}`,
            { cache: "no-store" }
        ).then(readResponse);

        setHistory(result.events ?? []);
    }

    async function selectFinding(finding: ReviewFinding) {
        setSelectedId(finding.id);
        setStatus(finding.status);
        setNote(finding.review_note ?? "");
        setHistory([]);
        setMessage("");
        setError("");

        onSelectFinding?.(finding);

        try {
            await loadHistory(finding.id);
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Unable to load audit history"
            );
        }
    }

    async function saveReview() {
        if (!selectedId) return;

        setSaving(true);
        setError("");
        setMessage("");

        try {
            await apiFetch(
                `${API}/api/review-decision?version=${encodeURIComponent(
                    version
                )}&finding_id=${encodeURIComponent(selectedId)}`,
                {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        status,
                        note,
                        actor_role: role,
                        actor_name: reviewerName,
                    }),
                }
            ).then(readResponse);

            await refresh();
            await loadHistory(selectedId);

            setMessage("Review saved successfully.");
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Unable to save review"
            );
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="p-5">
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h3 className="text-lg font-semibold">
                        CPA Review Queue
                    </h3>

                    <p className="mt-1 text-sm text-slate-500">
                        Version {version} · Persistent review decisions
                    </p>
                </div>

                <div className="flex flex-wrap gap-3">
                    <div>
                        <label className="mb-1 block text-xs font-medium text-slate-500">
                            Demo role
                        </label>

                        <select
                            aria-label="Demo role"
                            disabled={!!identity}
                            value={role}
                            onChange={(event) => {
                                const nextRole = event.target.value as ReviewRole;
                                setRole(nextRole);

                                if (
                                    nextRole === "preparer" &&
                                    status === "resolved"
                                ) {
                                    setStatus("in_review");
                                }
                            }}
                            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                        >
                            <option value="preparer">Preparer</option>
                            <option value="reviewer">Reviewer</option>
                            <option value="partner">Partner</option>
                        </select>
                    </div>

                    <div>
                        <label className="mb-1 block text-xs font-medium text-slate-500">
                            Reviewer name
                        </label>

                        <input
                            aria-label="Reviewer name"
                            disabled={!!identity}
                            value={reviewerName}
                            onChange={(event) =>
                                setReviewerName(event.target.value)
                            }
                            maxLength={120}
                            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                    </div>
                </div>
            </div>

            {error && (
                <p
                    role="alert"
                    className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700"
                >
                    {error}
                </p>
            )}

            {message && (
                <p
                    role="status"
                    className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700"
                >
                    {message}
                </p>
            )}

            {loading ? (
                <p className="text-sm text-slate-500">
                    Loading reviews...
                </p>
            ) : !data ? (
                <p className="text-sm text-slate-500">
                    Review data is unavailable.
                </p>
            ) : (
                <>
                    <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                        {statuses.map((item) => (
                            <div
                                key={item.value}
                                className="rounded-xl border border-slate-200 bg-slate-50 p-3"
                            >
                                <p className="text-xs text-slate-500">
                                    {item.label}
                                </p>

                                <p className="mt-1 text-2xl font-semibold">
                                    {data.status_counts[item.value] ?? 0}
                                </p>
                            </div>
                        ))}
                    </div>

                    {data.findings.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center">
                            <h4 className="font-semibold">
                                No findings to review
                            </h4>

                            <p className="mt-2 text-sm text-slate-500">
                                No findings were returned by the current
                                validation checks. This does not mean the
                                return is fully verified.
                            </p>
                        </div>
                    ) : (
                        <div className="grid gap-5 lg:grid-cols-2">
                            <div className="max-h-[650px] space-y-2 overflow-auto">
                                {data.findings.map((finding) => (
                                    <button
                                        key={finding.id}
                                        onClick={() =>
                                            void selectFinding(finding)
                                        }
                                        className={`w-full rounded-xl border p-4 text-left transition ${selectedId === finding.id
                                                ? "border-indigo-400 bg-indigo-50"
                                                : "border-slate-200 hover:bg-slate-50"
                                            }`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <span className="text-sm font-semibold">
                                                {finding.title}
                                            </span>

                                            <span className="text-xs font-medium uppercase text-slate-500">
                                                {finding.severity}
                                            </span>
                                        </div>

                                        <p className="mt-2 line-clamp-2 text-xs text-slate-500">
                                            {finding.description}
                                        </p>

                                        <p className="mt-2 text-xs font-medium text-indigo-600">
                                            {finding.status.replace("_", " ")}
                                        </p>
                                    </button>
                                ))}
                            </div>

                            <div className="rounded-xl border border-slate-200 p-4">
                                {!selected ? (
                                    <p className="py-12 text-center text-sm text-slate-500">
                                        Select a finding to begin reviewing.
                                    </p>
                                ) : (
                                    <>
                                        <h4 className="font-semibold">
                                            {selected.title}
                                        </h4>

                                        <p className="mt-2 text-sm text-slate-600">
                                            {selected.description}
                                        </p>

                                        <div className="mt-3 flex flex-wrap gap-2 break-all font-mono text-xs text-slate-400">
                                            {(selected.refs ?? []).map(ref => onOpenReference ? <button key={ref} aria-label={`Open reference ${ref}`} className="text-left text-indigo-700 underline" onClick={() => onOpenReference(ref)}>{ref}</button> : <span key={ref}>{ref}</span>)}
                                        </div>

                                        <p className="mt-3 text-xs text-indigo-600">
                                            Supporting evidence is displayed in the
                                            Evidence Inspector.
                                        </p>

                                        <label className="mt-5 block text-sm font-medium">
                                            Review status
                                        </label>

                                        <select
                                            aria-label="Review status"
                                            value={status}
                                            onChange={(event) =>
                                                setStatus(
                                                    event.target.value as ReviewStatus
                                                )
                                            }
                                            className="mt-2 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm"
                                        >
                                            {statuses
                                                .filter(
                                                    (item) =>
                                                        role !== "preparer" ||
                                                        item.value !== "resolved"
                                                )
                                                .map((item) => (
                                                    <option
                                                        key={item.value}
                                                        value={item.value}
                                                    >
                                                        {item.label}
                                                    </option>
                                                ))}
                                        </select>

                                        <label className="mt-5 block text-sm font-medium">
                                            Reviewer note
                                        </label>

                                        <textarea
                                            aria-label="Reviewer note"
                                            value={note}
                                            onChange={(event) =>
                                                setNote(event.target.value)
                                            }
                                            rows={4}
                                            maxLength={4000}
                                            placeholder="Describe the evidence checked and the reason for your decision."
                                            className="mt-2 w-full rounded-lg border border-slate-200 p-3 text-sm"
                                        />

                                        <button
                                            onClick={() => void saveReview()}
                                            disabled={
                                                saving ||
                                                !note.trim() ||
                                                !reviewerName.trim() ||
                                                (role === "preparer" &&
                                                    status === "resolved")
                                            }
                                            className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                                        >
                                            {saving ? "Saving..." : "Save Review"}
                                        </button>

                                        <div className="mt-6 border-t border-slate-200 pt-5">
                                            <h5 className="text-sm font-semibold">
                                                Audit History
                                            </h5>

                                            {history.length === 0 ? (
                                                <p className="mt-3 text-xs text-slate-500">
                                                    No recorded decisions yet.
                                                </p>
                                            ) : (
                                                <div className="mt-3 space-y-3">
                                                    {history.map((event) => (
                                                        <div
                                                            key={event.id}
                                                            className="rounded-lg bg-slate-50 p-3"
                                                        >
                                                            <p className="text-xs font-semibold">
                                                                {event.previous_status} →{" "}
                                                                {event.new_status}
                                                            </p>

                                                            <p className="mt-1 text-xs text-slate-600">
                                                                {event.note}
                                                            </p>

                                                            <p className="mt-2 text-xs text-slate-400">
                                                                {event.actor_name} (
                                                                {event.actor_role}) ·{" "}
                                                                {new Date(
                                                                    event.created_at
                                                                ).toLocaleString()}
                                                            </p>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
