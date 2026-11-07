
"use client";

import { useCallback, useEffect, useState } from "react";

const API =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Role = "preparer" | "reviewer" | "partner";
type Status = "open" | "in_review" | "resolved" | "escalated";

type Finding = {
    id: string;
    code: string;
    title: string;
    description: string;
    severity: string;
    refs: string[];
    status: Status;
    review_note: string;
    updated_by: string | null;
    updated_at: string | null;
};

type ReviewResponse = {
    version: string;
    total: number;
    findings: Finding[];
    status_counts: Record<Status, number>;
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

const statuses: { value: Status; label: string }[] = [
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
}: {
    version: string;
}) {
    const [data, setData] = useState<ReviewResponse | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [role, setRole] = useState<Role>("reviewer");
    const [reviewerName, setReviewerName] = useState("Demo Reviewer");
    const [status, setStatus] = useState<Status>("open");
    const [note, setNote] = useState("");
    const [history, setHistory] = useState<ReviewEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    const refresh = useCallback(async () => {
        const result = await fetch(
            `${API}/api/reviews?version=${encodeURIComponent(version)}`,
            { cache: "no-store" }
        ).then(readResponse);

        setData(result);
        return result as ReviewResponse;
    }, [version]);

    useEffect(() => {
        let active = true;

        fetch(
            `${API}/api/reviews?version=${encodeURIComponent(version)}`,
            { cache: "no-store" }
        )
            .then(readResponse)
            .then((result: ReviewResponse) => {
                if (!active) return;
                setData(result);
                setSelectedId(null);
                setHistory([]);
                setError("");
            })
            .catch((err) => {
                if (active) setError(err.message);
            })
            .finally(() => {
                if (active) setLoading(false);
            });

        return () => {
            active = false;
        };
    }, [version]);

    const selected = data?.findings.find(
        (item) => item.id === selectedId
    );

    async function loadHistory(findingId: string) {
        const result = await fetch(
            `${API}/api/reviews/${encodeURIComponent(findingId)}/history?version=${encodeURIComponent(version)}`
        ).then(readResponse);

        setHistory(result.events);
    }

    async function selectFinding(finding: Finding) {
        setSelectedId(finding.id);
        setStatus(finding.status);
        setNote(finding.review_note);
        setMessage("");
        setError("");
        setHistory([]);

        try {
            await loadHistory(finding.id);
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Unable to load history"
            );
        }
    }

    async function saveReview() {
        if (!selectedId) return;

        setSaving(true);
        setError("");
        setMessage("");

        try {
            await fetch(
                `${API}/api/reviews/${encodeURIComponent(selectedId)}?version=${encodeURIComponent(version)}`,
                {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
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
                err instanceof Error ? err.message : "Unable to save review"
            );
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="p-5">
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h3 className="text-lg font-semibold">CPA Review Queue</h3>
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
                            value={role}
                            onChange={(e) => setRole(e.target.value as Role)}
                            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
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
                            value={reviewerName}
                            onChange={(e) => setReviewerName(e.target.value)}
                            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                    </div>
                </div>
            </div>

            {error && (
                <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                    {error}
                </p>
            )}

            {message && (
                <p role="status" className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700">
                    {message}
                </p>
            )}

            {loading ? (
                <p className="text-sm text-slate-500">Loading reviews...</p>
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
                                <p className="text-xs text-slate-500">{item.label}</p>
                                <p className="mt-1 text-2xl font-semibold">
                                    {data.status_counts[item.value] ?? 0}
                                </p>
                            </div>
                        ))}
                    </div>

                    {data.findings.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center">
                            <h4 className="font-semibold">No findings to review</h4>
                            <p className="mt-2 text-sm text-slate-500">
                                The current independent checks returned no findings.
                                This does not mean the tax return is fully verified.
                            </p>
                        </div>
                    ) : (
                        <div className="grid gap-5 lg:grid-cols-2">
                            <div className="space-y-2">
                                {data.findings.map((finding) => (
                                    <button
                                        key={finding.id}
                                        onClick={() => selectFinding(finding)}
                                        className={`w-full rounded-xl border p-4 text-left ${selectedId === finding.id
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
                                    <div>
                                        <h4 className="font-semibold">{selected.title}</h4>
                                        <p className="mt-2 text-sm text-slate-600">
                                            {selected.description}
                                        </p>

                                        <p className="mt-3 break-all font-mono text-xs text-slate-400">
                                            {selected.refs.join(" · ")}
                                        </p>

                                        <label className="mt-5 block text-sm font-medium">
                                            Review status
                                        </label>
                                        <select
                                            aria-label="Review status"
                                            value={status}
                                            onChange={(e) =>
                                                setStatus(e.target.value as Status)
                                            }
                                            className="mt-2 w-full rounded-lg border border-slate-200 p-3 text-sm"
                                        >
                                            {statuses
                                                .filter(
                                                    (item) =>
                                                        role !== "preparer" ||
                                                        item.value !== "resolved"
                                                )
                                                .map((item) => (
                                                    <option key={item.value} value={item.value}>
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
                                            onChange={(e) => setNote(e.target.value)}
                                            rows={4}
                                            maxLength={4000}
                                            placeholder="Describe what was checked, supporting evidence, and the reason for this decision."
                                            className="mt-2 w-full rounded-lg border border-slate-200 p-3 text-sm"
                                        />

                                        <button
                                            onClick={saveReview}
                                            disabled={
                                                saving ||
                                                !note.trim() ||
                                                !reviewerName.trim() ||
                                                (role === "preparer" && status === "resolved")
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
                                                                {event.previous_status} → {event.new_status}
                                                            </p>
                                                            <p className="mt-1 text-xs text-slate-600">
                                                                {event.note}
                                                            </p>
                                                            <p className="mt-2 text-xs text-slate-400">
                                                                {event.actor_name} ({event.actor_role})
                                                                {" · "}
                                                                {new Date(event.created_at).toLocaleString()}
                                                            </p>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
