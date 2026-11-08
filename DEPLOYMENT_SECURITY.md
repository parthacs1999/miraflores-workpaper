# Deployment security review

## Decision and scope

**BLOCKED — SECURITY OR INFRASTRUCTURE REQUIREMENTS REMAIN.** The fail-closed integration is implemented, but an approved identity gateway, real policy, DNS, target-runtime qualification and hosted smoke testing are still required. No accounts, policies or services were created. Automated tests do not establish production-grade security.

The original demo selector authenticates nobody; per-profile shared passwords are not adequate staff identity assurance. Hosted startup therefore requires signed Cloudflare Access identity, rejects demo/credential modes, and offers no fallback. Local demo selection remains available on loopback. An explicitly isolated legacy test profile preserves historical contract tests without exposing it through hosted startup.

## Trust boundaries and identity

A named reviewer authenticates at the owner's identity provider through Access. Render independently verifies the assertion using the configured issuer's fixed certificate endpoint, with RS256 only, required `kid`, issuer/audience/time validation, `type=app`, nonempty subject and maximum one-hour lifetime. JWT-selected URLs and untrusted email/staff headers are never trusted. See [Cloudflare JWT validation](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/).

Only allowlisted verified subjects map to fixed packet staff IDs. Session bindings store a subject hash and cannot be updated or deleted. A copied app cookie paired with another signed user is rejected. Staff roster and session creation cannot impersonate another profile. A verified gateway identity mapped to a fictional packet role is still a **demonstration profile**, not proof of CPA licensure, client identity, employment or a legally compliant signature. Existing demonstration sign-offs and client authorizations retain their limitations.

The public Render URL is not an authentication bypass: every non-health request requires a verified assertion. There is no reliance on an unverified proxy-secret or source IP alone. The canonical custom domain must be Access-protected; Vercel aliases redirect there. The Cloudflare policy must cover all paths, enforce MFA and explicitly name people. Do not use broad domain allow rules, Bypass or service tokens.

Certificate cache lifetime is five minutes; upstream fetch failures fail closed. Fetches have bounded response sizes/timeouts and a cooldown, preventing unknown-key requests from continually hammering the provider. Availability depends on the IdP, Access, DNS, Vercel, Render and certificate endpoint. Logout cannot globally revoke an already issued bearer JWT; short lifetimes limit exposure. Emergency response: remove the subject mapping, redeploy/restart (configuration changes invalidate old app sessions), and revoke identity-provider access. Gateway logout and current app-session revocation are both used.

## Browser, cookie and CSRF controls

- Same-origin `/api` external rewrite, not cross-site cookie relaxation or a Function body proxy.
- Secure, HttpOnly, host-only, SameSite Strict `mf_session`; expires at the earlier of JWT expiration and 30 minutes. Session tokens are generated cryptographically and stored hashed.
- Mutations retain independent CSRF tokens and exact allowed Origin checks. Credentialed wildcard CORS is not introduced.
- Browser session expiry and unauthorized/gateway-HTML responses clear protected state. Role selection is disabled in hosted access mode. Existing session-generation checks discard stale responses after identity changes.
- Existing role/area/clearance checks cover nested evidence, downloads, histories and errors. Original attachment access still requires clearance and a recorded purpose.
- Hosted API responses, including errors/bootstrap/health, have private no-store, Pragma, appropriate Vary, nosniff, no-referrer, frame restrictions and HSTS. Frontend headers add Permissions-Policy and framing/object/base restrictions. The CSP is partial, not a comprehensive script/XSS policy.
- Session bootstrap bodies are bounded to 16 KiB. Existing general request and attachment checks remain; upload signatures, safe paths, size limits and content hashes are preserved.

Native HTTPS Next.js proxy tests exercise cookie forwarding, CSRF headers, masking, 5 MiB attachment upload/download, audit access, long polling, role restrictions and expiry. Actual Cloudflare/Vercel edge routing and caches are not locally reproducible and remain release gates. Configure cache bypass for API paths and never log assertion/cookie/CSRF headers or request bodies in edge tooling.

## Persistence and audit

The hosted launcher requires a real mounted disk, absolute contained database path, no symlink traversal, one worker and one instance. It holds an exclusive disk lock for its entire lifetime. It initializes and migrates before accepting traffic, enables WAL and validates integrity/foreign keys. Existing audit records remain intact. Migration 007 adds only a migration marker and immutable subject/session bindings; it does not rewrite existing tables.

Existing business transactions retain concurrency, independent approval, dependency invalidation and audit controls. Backup uses SQLite's online backup API. Offline restore shares the service lock, verifies content and preserves a full pre-restore copy before replacement. It prevents accidental replay of the same restore. Recovery still requires an operator-owned retention, encryption, monitoring and reconciliation process. Provider snapshots are not the sole database backup.

SQLite contents are not encrypted by the application. Protect Render disk/admin access and offsite backups; platform encryption does not replace an application-managed encryption/key-rotation design. Single-instance disk hosting has downtime and capacity limits. These are acceptable only if explicitly accepted for a restricted demo.

## Repository and dependency audit

Current tracked files contain no runtime database, `.env` secrets, PEM/private-key files or matches for the inspected credential patterns. A scan of 204 historical text blobs found no matches for the inspected private-key/GitHub/AWS credential patterns. Pattern scans cannot prove the absence of secrets.

Git history **does contain an old `backend/data/reviews.db`**. Two historical SQLite blobs were inspected without printing review contents: one had one review and four review events; another had zero. Neither contained session/credential tables. The file was subsequently removed from tracking. No history was rewritten and no records were deleted. The owner must assess review-note sensitivity and repository visibility before publishing or expanding access. If history remediation is needed, it requires a separate approved, coordinated procedure. The case-study packet itself remains in Git and is not protected by application login.

A development dependency advisory affecting minimatch was resolved with a scoped override to 11.0.5 under `@typescript-eslint/typescript-estree`, preserving Next.js and lint rules. `npm audit` reports zero known vulnerabilities at verification time; see [the advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249). That is not an independent security audit. Python 3.13.18 is pinned for Render; local tests used 3.13.5, so target-runtime verification remains mandatory.

## Operational responsibilities and remaining risks

Owner approval is required for the proposed Cloudflare integration. No real user identity mapping, MFA policy, domain or provider access is provisioned. All placeholders must be replaced through administrative configuration. Do not put secrets or mappings in browser-public variables. Example files contain placeholders only and are not automatically loaded by the backend launcher.

Use separate named administrative accounts with MFA for GitHub, Render, Vercel, Cloudflare and backup storage. Restrict project membership, debug tooling and log retention. Uvicorn access logging is disabled by the hosted launcher, but platform/edge logging must also be reviewed. App failures and validation errors are sanitized; do not enable debug tracebacks or log packet payloads.

Remaining limitations include no penetration test, no live SSO/edge validation, no managed offsite backup scheduling, no multi-instance failover, incomplete script CSP, short-lived bearer-token replay risk, dependence on owner-operated access/recovery controls and no legal tax-filing/e-signature assurance. The real case remains filing-blocked. Actual agency submission, payment processing and client delivery are not enabled.
