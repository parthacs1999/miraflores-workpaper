/** Empty base means the same-origin /api rewrite. No credential belongs here. */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
