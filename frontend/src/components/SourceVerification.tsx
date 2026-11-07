
"use client";

import { useEffect, useState } from "react";

const API =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type VerificationStatus =
    | "supported"
    | "unverified"
    | "missing_source";

type VerificationResult = {
    evidence_id: string;
    document_id: string | null;
    document_title: string | null;
    page: number | null;
    field: string | null;
    label: string | null;
    extracted_value: unknown;
    text_as_read: string | null;
    confidence: number | null;
    position: Record<string, number> | null;
    status: VerificationStatus;
    reason: string;
    match: {
        method: string;
        matched_text: string;
        start: number;
        end: number;
    } | null;
    printed_content: string | null;
};

type Props = {
    evidenceId: string;
    onClose: () => void;
    onOpenDocument?: (documentId: string) => void;
};

function displayValue(value: unknown): string {
    if (value === null || value === undefined) return "—";

    if (typeof value === "object") {
        return JSON.stringify(value);
    }

    return String(value);
}

function HighlightedSource({
    content,
    match,
}: {
    content: string;
    match: VerificationResult["match"];
}) {
    if (
        !match ||
        !Number.isInteger(match.start) ||
        !Number.isInteger(match.end) ||
        match.start < 0 ||
        match.end > content.length ||
        match.end <= match.start ||
        content.slice(match.start, match.end) !== match.matched_text
    ) {
        return (
            <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6 text-slate-700">
                {content}
            </pre>
        );
    }

    return (
        <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6 text-slate-700">
            {content.slice(0, match.start)}
            <mark
                data-testid="source-highlight"
                className="rounded bg-amber-200 px-0.5 font-semibold text-amber-950"
            >
                {content.slice(match.start, match.end)}
            </mark>
            {content.slice(match.end)}
        </pre>
    );
}

export default function SourceVerification({
    evidenceId,
    onClose,
    onOpenDocument,
}: Props) {
    const [result, setResult] =
        useState<VerificationResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const controller = new AbortController();

        async function load() {
            setLoading(true);
            setError("");
            setResult(null);

            try {
                const response = await fetch(
                    `${API}/api/source-verification/${encodeURIComponent(
                        evidenceId
                    )}`,
                    {
                        cache: "no-store",
                        signal: controller.signal,
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `Verification request failed (${response.status})`
                    );
                }

                const data =
                    (await response.json()) as VerificationResult;

                if (!controller.signal.aborted) {
                    setResult(data);
                }
            } catch (err) {
                if (!controller.signal.aborted) {
                    setError(
                        err instanceof Error
                            ? err.message
                            : "Unable to verify source"
                    );
                }
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        }

        void load();

        return () => controller.abort();
    }, [evidenceId]);

    const statusStyles: Record<VerificationStatus, string> = {
        supported: "bg-emerald-50 text-emerald-700",
        unverified: "bg-amber-50 text-amber-700",
        missing_source: "bg-red-50 text-red-700",
    };

    const statusLabels: Record<VerificationStatus, string> = {
        supported: "Supported",
        unverified: "Unverified",
        missing_source: "Missing Source",
    };

    return (
        <div
            data-testid="source-verification"
            className="space-y-5"
        >
            <div className="flex items-center justify-between gap-3">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
                        Source verification
                    </p>

                    <h3 className="mt-1 font-mono text-sm font-semibold">
                        {evidenceId}
                    </h3>
                </div>

                <button
                    type="button"
                    onClick={onClose}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium hover:bg-slate-50"
                >
                    Back to lineage
                </button>
            </div>

            {loading && (
                <p role="status" className="text-sm text-slate-500">
                    Verifying source evidence...
                </p>
            )}

            {error && (
                <p
                    role="alert"
                    className="rounded-lg bg-red-50 p-3 text-sm text-red-700"
                >
                    {error}
                </p>
            )}

            {result && (
                <>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <h4 className="text-sm font-semibold">
                            {result.label || result.field || "Extracted value"}
                        </h4>

                        <span
                            data-testid="verification-status"
                            className={`rounded-full px-3 py-1 text-xs font-semibold ${statusStyles[result.status] ??
                                "bg-slate-100 text-slate-700"
                                }`}
                        >
                            {statusLabels[result.status] ?? result.status}
                        </span>
                    </div>

                    <div className="rounded-xl border border-slate-200 p-4">
                        <p className="text-xs text-slate-500">
                            Extracted value
                        </p>

                        <p className="mt-2 break-all font-mono text-lg font-semibold">
                            {displayValue(result.extracted_value)}
                        </p>

                        <div className="mt-4 grid grid-cols-2 gap-3">
                            <div>
                                <p className="text-xs text-slate-500">
                                    Document
                                </p>

                                <p className="mt-1 text-sm font-medium">
                                    {result.document_id ?? "—"}
                                </p>
                            </div>

                            <div>
                                <p className="text-xs text-slate-500">
                                    Source page
                                </p>

                                <p className="mt-1 text-sm font-medium">
                                    {result.page ?? "—"}
                                </p>
                            </div>

                            <div>
                                <p className="text-xs text-slate-500">
                                    Extraction confidence
                                </p>

                                <p className="mt-1 text-sm font-medium">
                                    {typeof result.confidence === "number"
                                        ? `${Math.round(result.confidence * 100)}%`
                                        : "—"}
                                </p>
                            </div>

                            <div>
                                <p className="text-xs text-slate-500">
                                    Match method
                                </p>

                                <p className="mt-1 break-words text-xs font-medium">
                                    {result.match?.method ?? "No match"}
                                </p>
                            </div>
                        </div>

                        {result.text_as_read && (
                            <div className="mt-4 border-t border-slate-100 pt-3">
                                <p className="text-xs text-slate-500">
                                    Extraction text
                                </p>

                                <p className="mt-1 break-all font-mono text-sm">
                                    {result.text_as_read}
                                </p>
                            </div>
                        )}
                    </div>

                    <div
                        className={`rounded-xl p-4 text-sm ${statusStyles[result.status] ??
                            "bg-slate-100 text-slate-700"
                            }`}
                    >
                        <p className="font-semibold">
                            {statusLabels[result.status] ?? result.status}
                        </p>

                        <p className="mt-2 leading-6">
                            {result.reason}
                        </p>
                    </div>

                    <div className="rounded-xl border border-slate-200">
                        <div className="border-b border-slate-200 bg-slate-50 p-4">
                            <p className="text-sm font-semibold">
                                Simulated printed source
                            </p>

                            <p className="mt-1 text-xs text-slate-500">
                                {result.document_title ??
                                    result.document_id ??
                                    "Source document"}
                                {result.page !== null
                                    ? ` · Page ${result.page}`
                                    : ""}
                            </p>
                        </div>

                        <div className="max-h-[400px] overflow-auto p-4">
                            {result.printed_content !== null ? (
                                <HighlightedSource
                                    content={result.printed_content}
                                    match={result.match}
                                />
                            ) : (
                                <p className="text-sm text-slate-500">
                                    Printed source content is unavailable.
                                </p>
                            )}
                        </div>
                    </div>

                    {result.match && (
                        <div className="rounded-lg bg-slate-50 p-3">
                            <p className="text-xs text-slate-500">
                                Matched source text
                            </p>

                            <p className="mt-1 break-all font-mono text-sm font-semibold">
                                {result.match.matched_text}
                            </p>
                        </div>
                    )}

                    {result.document_id && onOpenDocument && (
                        <button
                            type="button"
                            onClick={() =>
                                onOpenDocument(result.document_id!)
                            }
                            className="w-full rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-semibold text-indigo-700 hover:bg-indigo-100"
                        >
                            Open full source document
                        </button>
                    )}

                    <p className="text-xs leading-5 text-slate-500">
                        Verification uses deterministic text matching.
                        Matching text alone does not establish that the
                        extraction belongs to the correct tax field.
                    </p>
                </>
            )}
        </div>
    );
}
