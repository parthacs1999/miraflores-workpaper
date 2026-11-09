# Public MiraFlores demo — Render Free + Vercel

A reviewer opens one HTTPS URL and immediately enters the fictional workpaper. **No login, reviewer token, custom domain or authentication provider is required.** This is a separate, explicitly non-production `public-demo` profile. Nothing has been deployed automatically.

## What visitors get

- A fresh private sandbox, initially using Priya's simulated preparer role.
- A clearly labeled **Switch simulated demo role** menu offering Priya, Daniel and Helen. These are simulated roles, not authenticated people or legally valid approvals.
- Interactive return exploration, evidence tracing, CPA-verification simulation, reconciliation, receipts adjustments, review decisions, diligence/notes/sign-offs, version comparison, scenarios and timeline inspection.
- Normal adjustment rules inside the simulation: preparers cannot approve their own work, and partner-required adjustments require the simulated partner. Approved changes affect only that visitor's workpaper; engine values remain unchanged.
- A persistent **PUBLIC DEMO / FILING BLOCKED** notice and **Reset my demo** control.

Uploads, protected-original downloads/reveals, administrative writes, client/colleague communication writes and all filing/post-filing mutations are disabled server-side. Those screens remain inspectable, and attempted restricted actions return an explicit public-demo denial. No actual filing, payment, client delivery or external message occurs. The secure and token-protected profiles retain their existing functionality.

## Fictional data and isolation

The original [Instructions.json](backend/data/Instructions.json) explicitly states in `readme.all_data_is_invented` that the people, companies, numbers and identifiers are fictional. The original [case-study PDF](<docs/Case_Study_Redesign_the_Tax_Workpaper l MiraFlores AI.pdf>) describes the household as invented on page 2. Its full three pages were inspected. The JSON also says there are no original page images: source views are rendered representations of `printed_content`.

The public launcher verifies the original packet's SHA-256 (`ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`) before starting. It never edits the packet. Existing sensitive-field masking is retained even for fictional identifiers. The current tracked tree contains environment examples, not credential files or runtime databases; frontend public assets are SVG assets, not uploaded client documents.

Each process creates its own empty migrated baseline from this original packet, including normal packet-backed assignments/tasks. **It never imports the historical SQLite database, local review records, private attachments or protected originals.** Each visitor gets a separate SQLite copy. Request-local context selects that file, including the policy reader and FastAPI worker threads; no request changes a process-wide database environment variable. Reviews, notes, adjustments, change-feed checkpoints and audit records cannot appear in another visitor's sandbox. Existing database connection defaults remain unchanged when this context is absent, preserving the other profiles.

Automatic HttpOnly, Secure, SameSite Strict cookies identify the sandbox and its simulated session; they are not staff authentication or a credential that a reviewer must obtain. A copied session cookie alone cannot select another sandbox. Do not enter genuine client or personal information: the public demonstration is not a confidential records service.

**State is temporary:** each sandbox expires after one hour; Reset discards only that visitor's simulation. Expired inactive sandboxes are removed on subsequent requests. Render sleep, restart or redeployment also discards state. Audit events remain append-only only within that sandbox lifetime. There is no common authoritative database for anonymous visitors to modify.

## 1. Publish the reviewed source

Review and publish these changes to `main` using your usual Git process. This task does not push, create hosting resources or deploy. Keep the original `render.yaml`, `render.assignment-demo.yaml`, secure launcher and token configuration unchanged; use the new files/settings below for a **separate project/service**.

## 2. Create the Render Free backend

In Render, create a **Web Service** from this repository:

| Setting | Value |
|---|---|
| Name | A unique name, e.g. `miraflores-public-demo-YOURSUFFIX` |
| Branch | `main` |
| Root directory | `backend` |
| Runtime | Python |
| Python version | `3.13.18` |
| Build command | `pip install -r requirements.txt` |
| Start command | `python run_public_demo.py` |
| Instance | **Free**, one instance/worker |
| Health check | `/health` |
| Disk | None |
| Auto-deploy | Off until you choose otherwise |

Set these environment variables:

```dotenv
PYTHON_VERSION=3.13.18
WORKPAPER_PROFILE=public-demo
WORKPAPER_ORIGINS=https://YOUR-VERCEL-PROJECT.vercel.app
```

`WEB_CONCURRENCY=1` is optional; the launcher always starts exactly one worker and rejects a conflicting worker count. Render supplies `PORT`; the launcher binds `0.0.0.0:$PORT`, without reload or request access logging.

Use the intended Vercel project hostname initially, then replace it with Vercel's exact assigned production hostname in step 4. **Do not set** `REVIEW_DB_PATH`, `WORKPAPER_DISK_ROOT`, `WORKPAPER_MODE`, `WORKPAPER_CREDENTIALS`, `WORKPAPER_HOSTED`, Access-provider settings or assignment-reviewer settings. This launcher refuses inherited secure database/credential settings rather than weakening them.

[render.public-demo.yaml](render.public-demo.yaml) contains equivalent reviewed configuration if you prefer a Blueprint. Creating/importing a service can deploy it; do that only when you choose to. Copy the assigned `https://YOUR-SERVICE.onrender.com` origin after creation.

## 3. Create the Vercel frontend

Create a **separate** Vercel project from the same repository:

| Setting | Value |
|---|---|
| Branch | `main` |
| Root directory | `frontend` |
| Framework | Next.js |
| Node | 22.x |
| Install | `npm ci` |
| Build | `npm run build -- --webpack` |
| Output | Default Next.js output; no static export |
| Domain | Free assigned `YOUR-PROJECT.vercel.app` hostname |
| Git auto-deployment | Enabled by default; connect the intended repository and production branch `main` |

Set these five build/runtime environment values:

```dotenv
WORKPAPER_PROFILE=public-demo
NEXT_PUBLIC_PUBLIC_DEMO=1
NEXT_PUBLIC_API_URL=
WORKPAPER_PUBLIC_ORIGIN=https://YOUR-PROJECT.vercel.app
WORKPAPER_BACKEND_ORIGIN=https://YOUR-SERVICE.onrender.com
```

`NEXT_PUBLIC_API_URL` must have an **explicitly empty value**, not localhost. The profile uses a fixed native Next.js external `/api` rewrite to the configured Render origin, preserving same-origin Secure cookies, CSRF, no-store and long polling. Noncanonical preview/alias hosts redirect to the selected production hostname. There is no open proxy, secret frontend environment variable or authentication fallback.

Leave `WORKPAPER_HOSTED`, assignment flags and all test-only flags unset. Missing/mixed settings fail the build. The example is [frontend/.env.public-demo.example](frontend/.env.public-demo.example). Do not add a paid domain or authentication integration.

Vercel Hobby is appropriate only if this use qualifies under its [personal/non-commercial terms](https://vercel.com/docs/limits/fair-use-guidelines). A public demo and absence of revenue do not automatically establish eligibility for a hiring assignment. Confirm plan eligibility if uncertain; no paid trial is required or provisioned by this implementation. The code does not impose an additional eligibility token/flag. Hosting-plan terms are separate from application access.

## 4. Match the two origins and manually verify

Copy Vercel's exact production origin into Render's `WORKPAPER_ORIGINS`, with no trailing slash. Copy Render's exact service origin into Vercel's `WORKPAPER_BACKEND_ORIGIN`. Ensure Vercel's `WORKPAPER_PUBLIC_ORIGIN` matches its canonical production hostname, then rebuild/restart the affected service.

Before sharing, open that Vercel URL in two separate browsers or incognito contexts:

1. Both enter the Dashboard automatically as the simulated preparer, without credentials.
2. Both show the public-demo notice and **FILING BLOCKED**.
3. Create a review note or receipts adjustment in browser A. Browser B must not contain it. Switch A to reviewer/partner; B must retain its own role/state.
4. Use Return Explorer → business receipts → reconciliation/evidence → proposed adjustment. Submit as preparer; self-approval must fail. Switch to reviewer and confirm partner-required approval fails; switch to partner to demonstrate the approved result in **this sandbox only**.
5. Confirm version comparison/evidence tracing, masked source fields and the authorized change feed work. Original-download, upload, administrative and filing actions must be denied.
6. Reset A and confirm only A's changes disappear. Check cookie Secure/HttpOnly/Strict attributes, no-store responses, CSRF rejection and absence of console errors.

No provider account, real Render/Vercel request path or live public URL has been created or certified by local tests. This final platform smoke test remains yours after manual deployment.

## Free-tier and security limits

[Render Free](https://render.com/docs/free) sleeps after inactivity and has ephemeral storage. A cold start can take roughly a minute or longer; wait and use **Retry public demo** if the frontend gets a loading/error response. The app does not run an uptime monitor or sleep-prevention cron. Render Free has limited CPU and 512 MB RAM; use this for a small hiring review, not production traffic. A local two-visitor probe across representative workpaper routes peaked at 162.2 MiB process RSS; each fresh baseline database was 290,816 bytes. This is a local measurement, not a Render/Linux load or cold-start guarantee.

To bound anonymous resource use, the process allows 24 simultaneous visitor sandboxes, each with a one-hour lifetime, a soft 8 MiB database-storage ceiling, 180 requests/minute and 150 attempted mutations per lifetime. Limits return explicit 429/503/507 responses. Expired inactive slots are reclaimed. These controls bound ordinary resource use but do not prevent denial of service or quota exhaustion by determined public traffic. Private mutations can only affect disposable copies. No uploads are accepted. Do not promise persistent audit retention, availability or authenticated independent review.

All genuine external operations remain disabled. Read-only filing screens describe the existing simulation; public mutations under `/api/lifecycle` are denied, so visitors cannot make the case filing-ready or record filing/client-authorization outcomes. New/unknown write routes are denied by default until explicitly reviewed for the public allowlist. There are no administrative demo roles. Sensitive reveal headers and original-file/package access are denied regardless of simulated clearance.

To take the demo down, suspend/delete only these public Render/Vercel resources. Do not delete the real local database, secure services, token-protected services or their histories. Public sandbox data is disposable; no manual backup/import is necessary.

## Implementation and verification

The public boundary is in `backend/app/public_demo.py`, launched only by `backend/run_public_demo.py`. Existing authorization/business services are reused inside it with automatic simulated sessions. Database isolation uses a new optional `request_database_path` ContextVar in the central connection and policy reader; secure/default paths behave as before. No schema migration, tax computation change, external identity service or new production dependency was needed.

**677 tests passed, zero final failures**, preserving all previous 627: 570 backend + 67 browser + 40 configuration. The public tests cover anonymous entry, concurrent visitor isolation, scoped policy reads, private receipts approval/review state, blocked actions, masking, CSRF, cookies, reset, expiration/capacity and deployment configuration.

| Check | Result |
|---|---|
| Full backend pytest | 570 passed (536 existing + 34 public-demo), zero failures |
| Existing signed-gateway HTTPS proxy browser tests | 7 passed |
| Existing token-protected assignment browser tests | 3 passed |
| Existing legacy browser tests | 14 passed |
| Existing strict browser tests | 40 passed |
| New public HTTPS browser tests | 3 passed |
| Configuration tests | 40 passed (15 secure + 12 assignment + 13 public) |
| TypeScript / ESLint | Passed |
| Public-profile webpack production build | Passed with placeholder provider origins; no deployment |
| Render Free Blueprint schema | Validated, zero errors |
| Existing SQLite integrity / foreign keys | `ok` / zero violations, checked read-only |
| Packet checksum | Original SHA-256 unchanged |

The backend suite took 101.48 seconds and reported one existing Starlette TestClient deprecation warning. The public HTTPS browser suite took 16.6 seconds. An initial new browser-isolation fixture rotated a session behind its UI, correctly clearing that UI; the fixture was corrected to reuse the UI bootstrap rather than bypass session-generation behavior. No existing assertions or business rules were weakened. PDF text extraction produced font-map warnings but the relevant invented-household text was readable, and the JSON's fictional-data statement is explicit.

Reproduce backend checks from `backend`: `.venv/bin/python -m pytest -q`. From `frontend`, run `npm run test:public-config`, `npm run test:assignment-config`, `npm run test:deployment-config`, `npm run test:public`, `npm run test:deployment`, `npm run test:assignment`, `npm run test:e2e`, `npm run test:e2e -- --config=playwright.workflow.config.ts`, `npx tsc --noEmit`, and `npm run lint`. Run the browser suites sequentially; their private test servers reuse ports. No test opens a public tunnel or deploys a provider service.

Created:

- `PUBLIC_DEMO_DEPLOYMENT.md`
- `render.public-demo.yaml`
- `backend/app/public_demo.py`
- `backend/run_public_demo.py`
- `backend/run_public_e2e.py`
- `backend/tests/test_public_demo.py`
- `frontend/.env.public-demo.example`
- `frontend/public-hosting-config.mjs`
- `frontend/public-hosting-config.d.mts`
- `frontend/public-hosting-config.test.mjs`
- `frontend/playwright.public.config.ts`
- `frontend/public-tests/public-demo.spec.ts`

Modified: `README.md`, `backend/app/security_context.py`, `backend/app/services/review_service.py`, `backend/app/services/firm_policy.py`, `frontend/.gitignore`, `frontend/next.config.ts`, `frontend/package.json`, `frontend/src/components/FirmWorkflow.tsx`, and `frontend/src/components/shell/AppShell.tsx`. Temporary Next.js generated-type includes may be written during builds; no TypeScript checks are relaxed. Secure/assignment launchers and configurations, existing database records, Instructions.json, computation rules, adjustment approval rules and filing-readiness logic are unchanged.

**Status:** implemented and locally verified; not deployed. The remaining manual steps are publishing reviewed source, creating the two services, matching exact origins, confirming the chosen Vercel plan's eligibility and running step 4 against the actual public URL. No additional login/token setup or fictional-packet approval gate is required.

## FastAPI integration and automatic Git deployment

The repository no longer disables Vercel Git deployments. `npm run build -- --webpack` automatically runs a postbuild check rejecting unexpected Supabase/Vite assets and a missing/wrong public FastAPI rewrite. See [API_INTEGRATION.md](API_INTEGRATION.md) for the production artifact mismatch evidence, exact route mapping, two sandbox allowlist corrections, current configuration and regression results. Correct project/domain assignment is still required; a Git push cannot change which unrelated project owns a hostname. Render auto-deployment is a separate setting; manually deploy the updated backend for the narrow public allowlist corrections if it remains disabled.
