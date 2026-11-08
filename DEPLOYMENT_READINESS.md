# Deployment readiness report

**BLOCKED — SECURITY OR INFRASTRUCTURE REQUIREMENTS REMAIN**

Implementation is prepared and verified locally. Nothing was deployed, pushed, billed or provisioned. The original packet remains filing-blocked. The proposed Cloudflare Access approach awaits owner approval; no insecure fallback is enabled.

## Implemented

- Explicit hosted launcher: production-only verified identity mode, public bind using Render PORT, no reload, one worker, graceful shutdown, no request access logging.
- Signed Access JWT validation on backend requests, fixed subject-to-packet-role mapping, immutable session binding, secure cookies, explicit expiration and no public staff switching.
- Same-origin native Next.js external API rewrite to one configured Render origin. Canonical protected-domain redirects; production configuration rejects localhost and missing settings.
- Persistent disk preflight, additive migration 007, WAL/integrity checks, restrictive permissions and exclusive lifetime service lock.
- Consistent backup and guarded offline restore, checksum verification, preserved pre-restore state and repeated-restore protection.
- Environment examples, reviewed Render/Vercel configuration, dependency patch, operational and security runbooks.
- Frontend protected-state clearing on expiry, unauthorized responses and gateway HTML; fixed identity UX retains demonstration/signature limitations.

## Database and API compatibility

Migration `007_hosted_identity.sql` adds `hosted_schema_migrations` and `hosted_session_bindings(token_hash, subject_hash, created_at)` with immutable update/delete triggers. Existing tables and records are not rewritten. Existing migration initialization remains in place.

No public API route was removed or renamed. Session responses add `expires_at` and the new `access` mode; access-mode staff options intentionally expose only the authenticated mapped profile. Existing demo, credential and isolated regression behavior remains for its previous contexts; hosted startup rejects those modes. Health stays public and minimal. There is no public backup, restore, token-minting or identity-mapping endpoint.

## Verification results

| Check | Result |
|---|---|
| Complete backend pytest suite | **510 passed, 0 failed** (474 existing + 36 new) |
| Existing legacy Playwright suite | **14 passed, 0 failed** |
| Existing strict Playwright suite | **40 passed, 0 failed** |
| New actual HTTPS Next.js proxy Playwright suite | **7 passed, 0 failed** |
| New deployment configuration Node tests | **15 passed, 0 failed** |
| Total automated test cases | **586 passed, 0 failed**; all previous 528 retained |
| TypeScript `tsc --noEmit` | Passed |
| ESLint | Passed, no lint rules weakened |
| Hosted webpack production build | Passed with explicit same-origin configuration |
| Render official Blueprint schema | Passed, zero instance errors |
| Vercel official configuration schema | Passed, zero instance errors |
| Built canonical-domain redirect | HTTP 307 to configured origin; canonical Host serves HTTP 200 |
| Existing SQLite integrity / foreign keys | `ok` / zero violations (read-only check) |
| npm vulnerability audit | Zero known vulnerabilities, including development dependencies |
| Git whitespace check | Passed |

Backend run: 510 passed in 102.78 seconds, one existing Starlette/httpx TestClient deprecation warning. Legacy browser run: 14 passed in 37.4 seconds. Strict browser run: 40 passed in approximately 2.2 minutes. New proxy run: 7 passed in 23.8 seconds. Node config run: 15 passed. Platform Node NO_COLOR/FORCE_COLOR warnings were non-failing.

Initial sandbox attempts could not bind browser test ports or fetch existing Google Fonts during webpack compilation; authorized reruns succeeded. An initial new proxy assertion used a nonexistent readiness label; it was corrected to assert the existing authoritative blocker code without modifying readiness logic. Official YAML schema validation caught YAML 1.1 interpreting unquoted `off` as false; the configuration now quotes that enum. These intermediate failures are resolved; no existing test was weakened or deleted.

Security regressions cover forged/unsigned/wrong issuer/audience/expired/oversized identity input, provider failure, invalid/copied sessions, profile impersonation, CSRF/Origin, roles, masking, bounded session bodies, immutable bindings, audit persistence, concurrent database writes, startup/restore locking, corrupt storage and restart/migration behavior. Proxy coverage verifies the original full 5 MiB attachment transport, audited download/hash, long polling, no-store, session expiry and real filing blockers. Test identity keys, certificates and database records are isolated temporary fixtures, not deployed authentication or genuine engagement events.

Original `Instructions.json` SHA-256 remains:

```text
ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19
```

No tax calculations, adjustment approval rules or filing-readiness rules were changed. The local database was not migrated or used for writable tests; its original records remain on disk. Hosted migrations and security tests used isolated databases.

## Remaining release gates and risks

1. Owner approval of Cloudflare Access (or a separately engineered approved IdP), a custom domain, named reviewers, MFA policy and explicit subject mappings. Do not deploy publicly with demonstration staff selection.
2. Review the historical database in Git and packet/repository visibility. One old blob contains one review/four events; no historical session tables were present. No history rewrite was performed.
3. Review and publish the prepared source to remote `main` deliberately. Local `main` contains the completed product baseline; deployment changes remain uncommitted for review and remote main has not been updated by this task.
4. Create paid Render disk/service and Vercel project only after approval. Qualify pinned Python 3.13.18 on Render; local tests used Python 3.13.5. Confirm actual Node 22 patch/runtime and install logs.
5. Run the deployed Cloudflare→Vercel→Render smoke tests in DEPLOYMENT.md: token/header and cookie forwarding, origin/CSRF, maximum attachment, long polling, aliases, redaction, no-cache and log sanitization. Local proxy tests cannot certify provider-edge behavior.
6. Set up encrypted off-disk backup scheduling/monitoring, retention, recovery ownership and restore rehearsal. Confirm audit persistence through actual redeployments.
7. Accept documented prototype limitations: single-instance downtime/capacity, partial CSP, bearer-token replay window, no independent penetration test, no legal identity/signature or real filing infrastructure.

## Exact hosting settings and estimated cost

Render: web/Python, root `backend`, branch `main`, Virginia, `1c-2g`, one instance, 5 GB `/var/data`, build `pip install -r requirements.txt`, start `python run_secure.py --hosted`, health `/health`, shutdown allowance 45 seconds, auto-deploy off. Vercel: root `frontend`, Next.js, Node 22.x, `npm ci`, `npm run build -- --webpack`, default output, manual deployment after review. Required environment names, placeholder replacement, provider identity configuration, token generation model and backup commands are in DEPLOYMENT.md and the two `.env.example` files.

Proposed backend baseline is approximately $26.25/month ($25 compute + $1.25 disk); with Vercel Pro approximately $46.25/month plus usage, domain, backup and identity-related extras. A theoretical smaller Render floor is $7.25/month, not qualified for this workload. Verify current provider prices and eligibility before purchasing; primary pricing links and assumptions are in DEPLOYMENT.md.

## Exact file manifest

### Created

- `DEPLOYMENT.md`
- `DEPLOYMENT_READINESS.md`
- `DEPLOYMENT_SECURITY.md`
- `backend/.env.example`
- `backend/app/access_identity.py`
- `backend/app/hosting.py`
- `backend/app/hosting_headers.py`
- `backend/app/migrations/007_hosted_identity.sql`
- `backend/run_proxy_e2e.py`
- `backend/scripts/backup_sqlite.py`
- `backend/scripts/restore_sqlite.py`
- `backend/tests/test_hosted_identity.py`
- `backend/tests/test_hosting.py`
- `frontend/.env.example`
- `frontend/deployment-tests/cleanup.mjs`
- `frontend/deployment-tests/https-proxy.mjs`
- `frontend/deployment-tests/proxy.spec.ts`
- `frontend/hosting-config.d.mts`
- `frontend/hosting-config.mjs`
- `frontend/hosting-config.test.mjs`
- `frontend/playwright.deployment.config.ts`
- `frontend/src/lib/api-config.ts`
- `frontend/vercel.json`
- `render.yaml`

### Modified

- `.gitignore`
- `README.md`
- `backend/app/main.py`
- `backend/app/security.py`
- `backend/app/workflow_api.py`
- `backend/requirements.txt`
- `backend/run_secure.py`
- `frontend/.gitignore`
- `frontend/README.md`
- `frontend/eslint.config.mjs`
- `frontend/next.config.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/src/app/page.tsx`
- `frontend/src/components/AdjustmentWorkspace.tsx`
- `frontend/src/components/FirmWorkflow.tsx`
- `frontend/src/components/ReviewWorkspace.tsx`
- `frontend/src/components/SourceVerification.tsx`
- `frontend/src/components/evidence-types.ts`
- `frontend/src/components/session.tsx`
- `frontend/src/components/shell/AppShell.tsx`
- `frontend/tsconfig.json`

Generated databases, private keys, certificates, test results, Next.js output and backup artifacts are excluded from this manifest and from Git. No deployment, final case-study hand-in documentation or video was produced.
