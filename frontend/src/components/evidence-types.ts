import { apiFetch } from "@/components/session";
export type Resolution = {
  ref: string;
  version: string;
  type: string;
  status: "resolved" | "unresolved";
  reason_code: string | null;
  reason: string;
  label: string | null;
  value: unknown;
  location: string | null;
  related_refs: string[];
  document_ids: string[];
};
export type EvidenceGraph = {
  resolution: Resolution;
  nodes: Resolution[];
  unresolved: Resolution[];
  cycles: { from: string; to: string }[];
  document_ids: string[];
};
export type MatchCandidate = {
  method: string;
  matched_text: string;
  start: number;
  end: number;
  field_supported?: boolean;
  field_anchor?: string | null;
  context?: string;
  line?: number;
  column?: number;
};
export type VerificationEvent = {
  id: number;
  sequence: number;
  verifier_id: string;
  verifier_name: string;
  credential: string | null;
  assurance: string;
  method: string;
  source_ref: string;
  status: string;
  notes: string;
  created_at: string;
  stale: boolean;
  currently_confirmed: boolean;
  snapshot: {
    quote: { start: number; end: number; text: string } | null;
    source: Resolution;
  };
};
export type VerificationHistory = {
  sequence: number;
  latest: VerificationEvent | null;
  events: VerificationEvent[];
};
export const EVIDENCE_API =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const evidenceControl = "ui-control w-full";
export const evidenceButton = "ui-button secondary";
export async function evidenceRequest<T>(
  path: string,
  body?: object,
): Promise<T> {
  const response = await apiFetch(
    `${EVIDENCE_API}${path}`,
    body
      ? {
          method: "POST",
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
