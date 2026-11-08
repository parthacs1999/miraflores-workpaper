# $0 assignment demonstration profile

**NON-PRODUCTION. NOT YET VERIFIED ON PUBLIC HOSTING. No services or tunnels have been provisioned or deployed. There is no live reviewer URL yet.**

This profile is deliberately separate from [the secure hosted profile](DEPLOYMENT.md). The existing persistent-disk/verified-identity launcher, security settings and `render.yaml` are unchanged. Do not replace their configuration with these settings.

## Decision

A disposable, token-restricted demonstration is feasible for a **scheduled review**, provided the owner first confirms that the packet may be shared and contains no confidential real-client material. It cannot offer durable audit retention, verified named staff identity, unattended availability or authoritative filing readiness at $0 with the current SQLite architecture.

The proposed Render Free + Vercel Hobby combination is **conditional**, not certified eligible. [Vercel's fair-use rules](https://vercel.com/docs/limits/fair-use-guidelines) restrict Hobby to personal non-commercial use and broadly define financial gain. This hiring assignment could fall within that definition. Do not select Hobby merely because the app has no payments. Establish eligibility with Vercel if uncertain. The frontend fails closed unless its operator explicitly confirms eligibility. An environment flag does not override provider terms.

If eligibility cannot be established, the recommended $0 alternative is a **scheduled local HTTPS tunnel**, using the same restricted assignment profile and redesigned Next.js frontend. It needs no Vercel account, paid custom domain or paid authentication provider. Quick Tunnels are for testing, not production; see [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/). Current Quick Tunnel tooling also supports an explicit email allowlist with one-time PIN authentication. Use that additional edge gate and retain the private app token for role binding; the random URL itself is not access control. No tunnel has been opened by this task.

## Platform assessment

| Constraint | Finding |
|---|---|
| Render Free | One free web service, 512 MB RAM, limited CPU; no persistent disk. Use Free explicitly, not a paid trial. |
| Storage | [Render Free](https://render.com/docs/free) loses filesystem changes on restart/redeploy/sleep; starts sleeping after 15 minutes without inbound traffic. Expect cold starts around a minute, possibly longer under load. |
| Cost | Free quotas can suspend service/builds. Do not attach a payment method, enable paid instances, autoscaling, add-ons or an automatic upgrade. If signup requires a card for your account, stop and use the local alternative. |
| Vercel | Hobby eligibility is unresolved for this assignment; no Pro trial or paid protection/domain required by the code. |
| Authentication | No external paid provider. Unique 256-bit temporary bearer token per assigned packet profile, stored only as a SHA-256 digest server-side. Recipient identity is not independently verified. |
| Domain | Conditional cloud URL is the project's free `https://NAME.vercel.app` hostname; fallback is a generated `https://RANDOM.trycloudflare.com` hostname. |
| Attachments | Synthetic uploads remain available. Existing original-download and sensitive-reveal operations are denied in this disposable profile; private evidence must not be uploaded. The secure profile retains its original functionality. |
| Live changes | Existing bounded long polling is retained. No cron, uptime pings or sleep-prevention service is introduced. Close the reviewer tab after the session; active UI polling is user-driven, not a monitoring workaround. |

The backend starts with a **new temporary directory on every process start**, runs existing migrations, checks SQLite integrity/foreign keys and uses one worker/WAL. It does not open, restore, copy, delete or seed from `backend/data/reviews.db`, historical Git databases or old temporary directories. Audit records, approval histories and state changes remain append-only within that database lifetime. Sessions and all mutations are lost when that lifetime ends. Old local test/tunnel directories may remain on your own machine until you explicitly dispose of them.

Temporary state is adequate for showing the duplicate-receipts investigation and independent approval live, with separate reviewers and no server restart. It is **inadequate** if the assessment requires durable progress across days, durable audit exports, or asynchronous handoffs surviving sleep. In that case use the local scheduled session and retain the local database for the running session, or separately approve a durable persistence project. Do not describe ephemeral records as retained audit history.

## Seed and packet approval — mandatory

`backend/assignment_demo/seed.json` is a reviewable **empty workflow seed specification**, not a binary database. It imports no reviews, files, sessions, adjustments, authorizations or snapshots. Existing migrations initialize normal application structures and packet-supported assignments/tasks. This does not fabricate tax results.

`Instructions.json` remains immutable and contains the case-study data. **A hash is an integrity check, not sanitization or evidence of consent.** The code does not claim to sanitize all names, narrative text or documents. The owner must review the complete packet, sharing rights and screenshot/document content, and establish that it is approved synthetic/sanitized assignment material. Existing sensitive-field redaction remains enabled; protected originals are excluded even for cleared profiles. If genuine confidential records remain, do not set the approval flag or deploy. A separately reviewed sanitized packet artifact would require a scoped follow-up; silently modifying the original packet is prohibited.

After review, compute the exact hashes from repository root:

```sh
shasum -a 256 backend/data/Instructions.json backend/assignment_demo/seed.json
```

Set the two resulting digests in backend configuration. Only after reviewing both, set:

```dotenv
WORKPAPER_ASSIGNMENT_DATA_APPROVAL=reviewed-sanitized-assignment-only
```

Startup refuses missing/mismatched hashes, a modified seed format, a historical DB path, shared credential fallback, extra workers, another profile or missing approval. Nothing in this implementation sets the owner's deployment approval automatically.

## Reviewer access

Generate access material on your own computer, outside the repository:

```sh
backend/.venv/bin/python backend/scripts/create_assignment_tokens.py --directory /PRIVATE/NEW/DIRECTORY/miraflores-review-access --staff st-01 st-02 st-03
```

Replace the directory with a private absolute path that does not yet exist. The helper refuses paths inside the repository and creates private files:

- `tokens.json`: original random tokens; deliver exactly one profile/token to each independent named reviewer using a confidential channel, separately from the URL.
- `reviewers.json`: SHA-256 digests; copy its JSON into the backend environment variable `WORKPAPER_ASSIGNMENT_REVIEWERS`.

The helper does not print tokens. Do not commit, screenshot, email publicly, put in a URL/query string, put in frontend variables or log either file. Use Priya `st-01` for preparation, Daniel `st-02` for independent review and Helen `st-03` for partner review. Provision other existing profiles only when necessary. A single reviewer must not receive multiple profiles to self-approve. Tokens are bearer capabilities, can be forwarded, and provide no independent named-person authentication or legal signature assurance. Operator-controlled delivery is the restricted temporary-access boundary.

Set an explicit UTC expiration no more than seven days ahead (a few hours is recommended). Example to calculate, not deploy, a four-hour deadline:

```sh
backend/.venv/bin/python -c 'from datetime import datetime,timezone,timedelta; print((datetime.now(timezone.utc)+timedelta(hours=4)).isoformat())'
```

Application sessions remain Secure/HttpOnly/SameSite Strict, expire within two hours and never outlive the assignment deadline. Exact Origin and CSRF checks remain. A signed-in profile cannot switch directly to another role, even with another token; ending the session clears the workspace first. Supplying a stored digest instead of its original token does not log in. Session attempts are rate limited. At the assignment deadline, all non-health access fails closed. To revoke earlier, suspend the service or remove the token digest and restart; restart also intentionally resets the database. Do not extend access without re-reviewing participants and data.

## Conditional Render Free setup

**Do not create services until the approval and frontend-eligibility gates above are satisfied.** Dashboard creation itself may deploy resources. Review [render.assignment-demo.yaml](render.assignment-demo.yaml); leave the original `render.yaml` alone.

| Dashboard field | Exact setting |
|---|---|
| Service | New Web Service / Python |
| Source | Reviewed `main` |
| Root directory | `backend` |
| Region | Virginia |
| Instance | **Free**, one instance, no disk, no autoscaling |
| Build | `pip install -r requirements.txt` |
| Start | `python run_assignment_demo.py` |
| Health check | `/health` |
| Auto deploy | Off |
| Python | `PYTHON_VERSION=3.13.18` |

Backend environment:

```dotenv
WORKPAPER_PROFILE=assignment-demo
WORKPAPER_ENV=production
WEB_CONCURRENCY=1
WORKPAPER_ORIGINS=https://YOUR-ASSIGNMENT.vercel.app
WORKPAPER_ASSIGNMENT_EXPIRES_AT=REVIEWED_UTC_TIMESTAMP_WITHIN_SEVEN_DAYS
WORKPAPER_ASSIGNMENT_REVIEWERS=CONTENTS_OF_PRIVATE_REVIEWERS_JSON
WORKPAPER_ASSIGNMENT_PACKET_SHA256=REVIEWED_PACKET_SHA256
WORKPAPER_ASSIGNMENT_SEED_SHA256=REVIEWED_SEED_SHA256
WORKPAPER_ASSIGNMENT_DATA_APPROVAL=reviewed-sanitized-assignment-only
```

Leave `REVIEW_DB_PATH`, `WORKPAPER_DISK_ROOT`, `WORKPAPER_MODE`, `WORKPAPER_CREDENTIALS`, `WORKPAPER_HOSTED` and Access-provider settings **unset**. Render supplies `PORT`. This launcher binds `0.0.0.0`, one worker, no reload, sanitized startup failures and no Uvicorn request access logging. No startup command prints credentials. Use the final exact frontend hostname in the allowed Origin, not a wildcard or multiple preview aliases.

## Conditional Vercel Hobby setup

Use only if this assignment's use has been established eligible under current terms. Otherwise skip this section and use the tunnel workflow.

| Dashboard field | Setting |
|---|---|
| Plan | Hobby; no Pro trial/payment method/paid add-on |
| Repository branch | Reviewed `main` |
| Root / framework | `frontend` / Next.js |
| Node | 22.x |
| Install | `npm ci` |
| Build | `npm run build -- --webpack` |
| Output | Default Next.js output; no static export |
| Domain | Free project `NAME.vercel.app` |
| Git deployment | Off pending manual approval |

Frontend build/runtime environment:

```dotenv
WORKPAPER_PROFILE=assignment-demo
WORKPAPER_ASSIGNMENT_VERCEL_ELIGIBILITY=personal-noncommercial-confirmed
NEXT_PUBLIC_ASSIGNMENT_DEMO=1
NEXT_PUBLIC_API_URL=
WORKPAPER_BACKEND_ORIGIN=https://YOUR-ASSIGNMENT.onrender.com
WORKPAPER_PUBLIC_ORIGIN=https://YOUR-ASSIGNMENT.vercel.app
```

Do not set `WORKPAPER_HOSTED`, local test flags or backend access tokens on Vercel. The only public settings are the warning flag and explicitly empty API base. Canonical-host redirects and a native external `/api` rewrite preserve same-origin cookies, CSRF, no-store semantics, sensitive headers and bounded polling. The destination is a fixed HTTPS Render origin, never request-selected. No Function proxy, cross-site cookie weakening or wildcard credentialed CORS is added. Confirm default/preview aliases redirect to the chosen hostname.

Vercel/Render actual payload forwarding, cookies, cold-start behavior and polling **have not been tested in provider accounts**, because service creation/deployment is explicitly prohibited. Native production Next.js HTTPS tests passed locally, including a 5 MiB upload with a matching hash; this is not a claim about a live Vercel edge limit. A reviewer URL becomes available only after your manual approved deployment. No URL is fabricated here.

## Recommended $0 fallback: scheduled local HTTPS tunnel

This avoids unresolved Vercel eligibility and Render cold-start/memory constraints. It still requires packet approval and privately issued tokens. It requires your computer to remain awake and the application to remain running; no hosting SLA is implied.

1. Install `cloudflared` from [official downloads](https://developers.cloudflare.com/tunnel/downloads/) on your machine. Review its terms. Do not install a paid trial or publish an unauthenticated `--demo` server.
2. Reserve a local frontend port, for example 3002, then start a temporary tunnel (only when you explicitly choose to share):

   ```sh
   cloudflared tunnel --url http://127.0.0.1:3002 --allowed-mail FIRST_REVIEWER@example.com --allowed-mail SECOND_REVIEWER@example.com
   ```

   Replace the two addresses with explicitly approved reviewer emails; repeat the flag for each person and never use a domain wildcard. Check that your installed current `cloudflared` supports `--allowed-mail` before starting. The documented flow requires an email one-time PIN and does not require reviewer Cloudflare accounts. If the flag is unavailable, update from official releases or stop; do not silently remove email protection.

   It prints a random HTTPS `trycloudflare.com` URL. No application is listening yet, so early requests fail. Never expose backend port 8000 directly. Quick Tunnels have no SLA and do not support SSE; this app uses bounded long polling instead. Email verification is an extra edge restriction, not a backend-verified mapping of that email to a packet staff role; the separately delivered token still controls the assigned profile, and no authenticated CPA identity or legal signature is claimed. Stop and investigate if that provider transport fails.

3. In the backend terminal, set the same approved token/hash/expiry variables above, with `WORKPAPER_ORIGINS=https://ACTUAL-RANDOM.trycloudflare.com`, then run:

   ```sh
   cd backend
   .venv/bin/python run_assignment_demo.py --local-tunnel
   ```

   This binds backend loopback port 8000. Keep it running for the full session; restarting starts a new disposable database. Ensure another local backend is not already using that port.

4. In the frontend terminal, set only these frontend variables, using the actual generated hostname:

   ```sh
   export WORKPAPER_PROFILE=assignment-demo
   export WORKPAPER_ASSIGNMENT_TUNNEL=1
   export NEXT_PUBLIC_ASSIGNMENT_DEMO=1
   export NEXT_PUBLIC_API_URL=
   export WORKPAPER_PUBLIC_ORIGIN=https://ACTUAL-RANDOM.trycloudflare.com
   export WORKPAPER_BACKEND_ORIGIN=http://127.0.0.1:8000
   npm ci
   npm run build -- --webpack
   npm start -- --hostname 127.0.0.1 --port 3002
   ```

   Run these commands from `frontend`. Leave `WORKPAPER_HOSTED`, Vercel platform flags and test overrides unset. The tunnel profile allows only fixed loopback backend port 8000 and the exact free tunnel hostname. Direct localhost frontend requests redirect to that canonical HTTPS hostname so Secure cookies work correctly. Use HTTPS for all reviewer access.

5. Verify the email PIN challenge from an allowed reviewer and rejection of an unlisted address, then perform the smoke test below before privately sharing the URL. Deliver each token separately, schedule reviewers close together, and explain the state-loss warning. The tunnel URL's randomness is not the credential.

## Reviewer walkthrough

1. Open the provided HTTPS URL. Expect an unmistakable non-production/state-loss banner. A cold Render service may show a loading page or the app's recoverable backend error; wait, then use Retry session initialization. Do not assume errors mean the app has bypassed authentication.
2. Select only the assigned temporary profile and enter the private token in the credential field. No real staff authentication or signature is claimed.
3. Explore Dashboard → Return Explorer → Reconciliation & Findings → business receipts discrepancy → evidence → proposed adjustment. A different reviewer profile must independently approve where required; partner thresholds remain unchanged.
4. Review collaboration, evidence verification, version/scenario/timeline analysis and filing/post-filing simulations. Use synthetic uploads only. Original downloads and reveals return a clear denial in this profile.
5. Inspect filing readiness: the original case remains **FILING BLOCKED**. Nothing submits to IRS/FTB, makes a payment, sends a client copy or establishes legal authorization.
6. End the session. Do not enter genuine tax/client data, leave tokens in screenshots or assume work will persist after restart. Tell the owner if a cold start resets progress; do not treat a new lifetime as an audit continuation.

## Capacity and durable alternatives

The isolated local benchmark (`backend/.venv/bin/python backend/scripts/benchmark_assignment.py`) exercised overview, documents, reconciliations, readiness, version comparison, changes and a maximum 5 MiB synthetic upload. Measured peak process RSS was **232.3 MiB**, with local preflight/login **0.15 seconds** after Python module imports. This includes TestClient rather than Render's Linux container/CPU quota and is not a load guarantee. Uploads are serialized in this profile; overlapping uploads fail quickly with 429 rather than buffering multiple maximum payloads. Normal polling/health requests are not serialized behind uploads. Limit participation to a small scheduled group. Check Render metrics and exercise the maximum attachment before inviting reviewers; if memory approaches 512 MB or requests time out, stop and use the local alternative rather than buying capacity or shrinking existing feature limits silently.

If durable state is an assessment requirement, a free remote datastore could avoid sleep loss, but is **not a drop-in SQLite filename**:

- [Turso](https://turso.tech/pricing) advertises a no-card free tier. Its [Python SDK](https://docs.turso.tech/sdk/python/quickstart) requires replacing/adapting sqlite3 connection semantics, migrations, row factories, transactions, triggers, error handling and concurrency. Local replicas with occasional sync would risk losing the exact audit/approval writes being demonstrated. Estimated engineering work: **4–8 working days**, including durable transactional writes and all security/regression tests; not a commitment or measured implementation result.
- [Supabase Free](https://supabase.com/pricing) provides a PostgreSQL option, with quotas and inactivity pausing. Changing from SQLite entails a broader schema/SQL/transaction adapter and migration project: approximately **1–2 working weeks**, subject to a detailed spike. Free capacity is not a guaranteed backup/uptime service.
- Render Free Postgres expires after 30 days; it is not an acceptable long-term audit-retention solution merely because it is temporarily free.

No remote database, sync mechanism or persistence-layer rewrite was introduced. If data must survive independently of your machine, approve a separate durable backend scope; this profile cannot honestly satisfy that guarantee.

## Release smoke tests and shutdown

Before calling any cloud or tunnel URL ready, manually verify:

- Anonymous/invalid/expired access cannot read tax APIs, document text, histories or attachments. `/health` is the only public operational data; session bootstrap exposes no packet roster beyond generic configured role aliases.
- Token-to-role restrictions, wrong token/digest denial, administrator tax-detail denial, logout clearing, cookie Secure/HttpOnly/Strict, wrong-Origin/CSRF rejection and default masking.
- Maximum synthetic attachment upload/hash, protected-original denial, long polling/reconnect, real filing blockers and independent review controls.
- A restart resets sessions/state; no historical database is read. Audit events remain immutable within a lifetime. Document the reset to reviewers.
- Actual free-tier metrics, no sensitive platform logs/caches, no credit card/trial/add-on/paid disk, and no service keeping the backend artificially awake.

**Shutdown:** end reviewer sessions; suspend/delete the assignment Render service and Vercel project if created, revoke/remove token digests, then delete private token files according to your local policy. For local review, stop `cloudflared` first (revokes URL reachability), then stop Next.js and backend. Do not remove the real local database or the secure hosted configuration. Dispose only of explicitly identified assignment temporary directories and synthetic attachments after the review; do not erase authoritative histories. Remove exported assignment variables before returning to local `--demo` or secure hosted work. A future tunnel hostname changes Origin and requires a fresh frontend configuration/build.

## Verification and file manifest

All prior 586 tests are preserved. **627 tests passed, zero final failures** (536 backend + 64 browser + 27 configuration). Verification results for this change:

| Check | Result |
|---|---|
| Backend pytest | 536 passed, 0 failed (510 existing + 26 assignment tests), one existing TestClient deprecation warning |
| Existing legacy Playwright | 14 passed, 0 failed |
| Existing strict Playwright | 40 passed, 0 failed |
| Existing signed-gateway HTTPS proxy | 7 passed, 0 failed |
| New assignment HTTPS browser suite | 3 passed, 0 failed |
| Existing hosted configuration tests | 15 passed, 0 failed |
| New assignment configuration tests | 12 passed, 0 failed |
| TypeScript / ESLint | Passed |
| Explicit assignment webpack production build | Passed with placeholder free-tier origins; no deployment |
| Render Free Blueprint schema | Passed, zero errors |
| Original local SQLite integrity / foreign keys | `ok` / zero violations; read-only check |
| Instructions.json | Unchanged SHA-256 `ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19` |

Initial new-test failures were fixture/selector issues (Origin port, existing route prefix, native summary accessible label and sanitized login-error wording), and were corrected without weakening existing assertions or changing business rules. An added concurrent-upload test verifies fail-fast isolation while health remains responsive. The final backend run took 106.80 seconds; the assignment browser run took 17.4 seconds. No live cloud or tunnel verification is claimed.

Reproduce from `backend`: `.venv/bin/python -m pytest -q`. From `frontend`: `npm run test:deployment-config`, `npm run test:assignment-config`, `npm run test:deployment`, `npm run test:e2e`, `npm run test:e2e -- --config=playwright.workflow.config.ts`, `npm run test:assignment`, `npx tsc --noEmit`, `npm run lint`. Run browser suites sequentially because the isolated HTTPS suites reuse private test ports. The assignment suite generates ephemeral TLS keys, synthetic tokens and database fixtures; it never opens a public tunnel.

Assignment-specific files created:

- `FREE_DEPLOYMENT.md`
- `render.assignment-demo.yaml`
- `backend/app/assignment_demo.py`
- `backend/assignment_demo/seed.json`
- `backend/assignment_demo/.env.example`
- `backend/run_assignment_demo.py`
- `backend/run_assignment_e2e.py`
- `backend/scripts/create_assignment_tokens.py`
- `backend/scripts/benchmark_assignment.py`
- `backend/tests/test_assignment_demo.py`
- `frontend/.env.assignment.example`
- `frontend/assignment-hosting-config.mjs`
- `frontend/assignment-hosting-config.d.mts`
- `frontend/assignment-hosting-config.test.mjs`
- `frontend/playwright.assignment.config.ts`
- `frontend/assignment-tests/assignment.spec.ts`

Existing files modified for this profile: `.gitignore`, `README.md`, `frontend/.gitignore`, `frontend/next.config.ts`, `frontend/package.json`, and `frontend/src/components/FirmWorkflow.tsx`. Next.js may update `frontend/tsconfig.json` generated-type includes during verification; no compiler checks were relaxed. No additional migrations, remote database driver or production dependencies were added. The prior secure deployment changes remain separate; its launcher, identity adapter, policy and disk configuration were not modified by this assignment-profile work.

**Remaining gates:** approve packet/seed sharing rights and sanitization; issue private tokens to independent reviewers; establish Vercel Hobby eligibility or select the tunnel alternative; qualify the actual target runtime/memory/HTTPS forwarding; perform the manual smoke tests above. No public service can be called ready before those steps. All tax/approval logic is unchanged and the original packet remains filing-blocked.
