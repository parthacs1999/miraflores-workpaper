import type { Resolution } from "./evidence-types";
export type DocumentPage = { page: number; printed_content: string };
export type SourceDocument = { id: string; title: string; document_type: string; page_count: number; pages?: DocumentPage[] };
export type ReturnLine = { key: string; label: string; value: unknown; form: string; jurisdiction: string };
export type EvidenceSource = { ref: string; type: string; resolution?: Resolution; evidence?: { label: string; value: unknown; confidence: number }; document?: SourceDocument };
export type Lineage = { key: string; label: string; value: unknown; rule?: string; note?: string; missing?: boolean; cycle?: boolean; sources?: EvidenceSource[]; inputs?: Lineage[] };
export type Overview = { stats: { documents: number; extracted_values: number }; packet: { client_id: string } };
