# FastAPI integration and deployment-artifact audit

## Diagnosis

The production hostname `https://miraflores-workpaper.vercel.app/` was rechecked during this change. It still returned the same legacy artifact observed in the previous investigation:

- A 466-byte HTML shell with `/vite.svg`, `<div id="root">`, and `/assets/index-BYaW_yl4.js` instead of Next.js `/_next/` scripts.
- HTML SHA-256: `82c0152873959ebce04b8e7b2293286942d45c832281510b77ea3150b6c4827e`.
- That served bundle contains `erzenpyxxvqzsmqdqyps.supabase.co`, `review_notes`, `audit_log`, and the old “Return Summary” / “Review & Sign-off” interface. It inserts notes and audit rows directly through the legacy SDK.
- The previous direct `/api/workflow/session` request on that hostname returned Vercel 404, not FastAPI JSON. Cache-bypassed reads returned the same HTML; this is not merely browser cache.

The repository's starting commit is `4a901c3f0453b6411cd302b18d8e6a8be3b34a01`. Its `frontend` root contains the redesigned Next.js application. There is no old Vite frontend, Supabase SDK dependency, Supabase environment lookup, `createClient` integration, or `review_notes` / `audit_log` REST call in browser source. Earlier searches across all eight reachable commits found no such frontend either. The planning documentation mentions an unused remote database option; new negative regression fixtures mention forbidden signatures intentionally. Neither is application integration.

**Confirmed cause at the artifact boundary:** the public hostname serves a legacy Vite/Supabase application, not the normal Next.js output of this repository's `frontend` directory. A correct source commit shown in a Vercel dashboard does not establish that its output is the deployment currently served by this hostname.

**Not verified:** the private Vercel project ID, immutable deployment URL, alias owner, dashboard build/output overrides and routing settings are not accessible from this workspace. Therefore it would be speculation to declare a particular project, team, root override or promotion setting the exact private-account cause. Inspect those entries using the procedure below; no deployment or domain assignment was changed here.

A separate concrete repository configuration issue existed: `frontend/vercel.json` had `git.deploymentEnabled: false`. That has been removed. It explained why commits were explicitly excluded from automatic Git deployment, but it does not independently prove which deployment owns the existing hostname.

## Minimal changes

1. Removed only the Git deployment-disabling property from `frontend/vercel.json`; kept Next.js, `npm ci`, and `npm run build -- --webpack`, with no output override.
2. Added `postbuild: node scripts/verify-build.mjs`. Every normal `npm run build -- --webpack` now verifies real Next.js metadata, scans generated browser JS/CSS/maps and prerendered HTML for unexpected Supabase/Vite/legacy-table signatures, and checks the existing public `/api` rewrite against the configured Render origin. It fails the build without printing source snippets or credentials. It is not a second proxy.
3. Auditing the real UI requests found two public-sandbox allowlist mismatches: the review editor sends `PATCH /api/review-decision`, and change-impact reassessment sends `POST /api/change-impact/reassess`. Those endpoints already exist in FastAPI. The public allowlist now admits those exact paths instead of the nonexistent POST `/api/change-impact` path. Existing authorization, CSRF, independent review, contributor checks, validation, private databases and filing restrictions still run. No new endpoint, database, schema or tax rule was introduced.
4. Added artifact/source/configuration regressions, public-backend tests for the actual aliases, and real UI browser tests for note creation, audit retrieval and finding-review saving through the native HTTPS rewrite.

No URLs were blindly replaced. The existing shared API client and Next.js rewrite already implement the intended connectivity and were retained.

## Complete frontend network boundary

`frontend/src/components/session.tsx::apiFetch` is the only direct browser `fetch` call in application source. All components reach it through:

| Caller / helper | Responsibility |
|---|---|
| `src/app/page.tsx` | Workpaper overview, documents, lines, lineage, review/accountability overlays |
| `FirmWorkflow.tsx::request` | Bootstrap/role selection, dashboard workflow state, diligence, notes, sign-offs, tasks, audits, demo reset |
| `evidence-types.ts::evidenceRequest` | Documents/evidence, reconciliation, analysis, collaboration, firm operations and lifecycle components |
| `ReviewWorkspace.tsx` | Finding review list, PATCH decision, history |
| `AdjustmentWorkspace.tsx::request` | Adjustment metadata, ledger, revisions/actions, history and summaries |
| `SourceVerification.tsx` | Simulated source verification |
| `LiveUpdates.tsx` | Existing authorized long polling and persistent checkpoints |
| `ProductWorkspace.tsx` | Existing authorized original-download request path (intentionally denied in public demo) |

`API_BASE` is centralized in `src/lib/api-config.ts`. Public/hosted build configuration requires `NEXT_PUBLIC_API_URL` to be explicitly empty, so application requests are relative `/api/...`. Local development and isolated regression servers retain the documented localhost override. Cookies, CSRF, no-store, sensitive-access headers and stale-response handling remain centralized. There is no Axios, Supabase, direct browser-to-Render production call or duplicate proxy.

## Frontend → FastAPI mapping

All paths below are relative to the frontend origin and forwarded to the same `/api` path on Render. GET parameters are query strings; POST/PATCH bodies are JSON. IDs/references are URL-encoded by the callers. Methods and schemas were checked against actual FastAPI route definitions and the existing integration suites.

| Feature | Real method and endpoint | Request → response |
|---|---|---|
| Public entry / role options | GET `/api/workflow/session`; GET `/api/workflow/session/staff` | No login input → simulated staff, CSRF token, expiry; three-role list |
| Simulated role switch | POST `/api/workflow/session` | `{staff_id, credential:""}` + CSRF/Origin → rotated simulated session |
| Reset private demo | POST `/api/public-demo/reset` | `{}` + CSRF/Origin → `{reset:true, public_demo:true}`, cleared sandbox cookies |
| Dashboard / return summary | GET `/api/overview`; GET `/api/workflow/overview`; GET `/api/workpaper-summary?version=v3` | Packet/current version, workflow projections, original and approved-adjustment summary |
| Versions / return lines | GET `/api/return-versions`; GET `/api/return-lines?version=v3` | Version list; return-line list |
| Documents | GET `/api/documents`; GET `/api/documents/{id}` | Document summaries; printed-content representation |
| Document accountability | GET `/api/document-accountability?version=v3` | Document dispositions, coverage and unresolved provenance |
| Reverse tracing / source fields | GET `/api/documents/{id}/destinations?version=v3`; GET `/api/documents/{id}/evidence` | Destinations/dependencies; `{values:[...]}` |
| Line lineage / calculations | GET `/api/lineage/{line_key}?version=v3` | Traceable calculation/evidence graph |
| Evidence resolution | GET `/api/evidence-resolution?ref=...&version=v3`; GET `/api/evidence-graph?...` | Typed resolution/graph, explicit unresolved reasons |
| Printed-source matching | GET `/api/source-verification/{evidence_id}?version=v3` | Simulated source match and ambiguity information |
| Verification metadata/history | GET `/api/verification-metadata`; GET `/api/field-verifications/{id}?version=v3` | Staff/method choices; sequence/latest/events |
| Verification decision | POST `/api/field-verifications/{id}?version=v3` | Verifier, method, source_ref, status, notes, expected sequence and optional quote → persisted event/history |
| Diagnostics / validation | GET `/api/validation?version=v3`; GET `/api/reviews?version=v3` | Findings, review state and counts |
| Finding review editor | PATCH `/api/review-decision?version=v3&finding_id=...` | `{status,note,actor_role,actor_name}` → persisted review; existing PATCH `/api/reviews/{id}` remains compatible |
| Review audit | GET `/api/review-history?version=v3&finding_id=...` | `{events:[...]}`; existing GET `/api/reviews/{id}/history` remains compatible |
| Unified reconciliation | GET `/api/reconciliations?version=v3`; GET `/api/unified-findings?version=v3` | Deterministic/unsupported checks; unified findings and review state |
| Reconciliation history | GET `/api/unified-findings/{id}/history?version=v3` | Decision/link events |
| Reconciliation decision | POST `/api/reconciliation-decision?version=v3&finding_id=...` | `{actor_id,status,disposition,note,authority,refs,adjustment_id}` → documented decision |
| Linked correction | POST `/api/reconciliations/{id}/adjustment?version=v3`; POST `/api/reconciliation-links?...` | `{actor_id,note,authority}` → draft adjustment; `{actor_id,adjustment_id,note,action}` → link/unlink |
| Adjustment workspace | GET `/api/adjustment-metadata?version=v3`; GET `/api/adjustments?version=v3` | Metadata/demo assumptions; `{adjustments:[...]}` |
| Adjustment draft / revision | POST `/api/adjustments?version=v3`; POST `/api/adjustments/{id}/revisions` | Existing target/proposed-value/reason/evidence/actor schema, expected sequence on revision → ledger item |
| Adjustment approval/reversal | POST `/api/adjustments/{id}/actions` | `{actor_id,action,expected_sequence,note,...}` → validated state transition; original independence/partner rules enforced |
| Adjustment audit | GET `/api/adjustments/{id}/history` | `{events:[...]}` with immutable revisions/actions |
| Blocking review notes | POST `/api/workflow/notes` | `{id?,area,action,title,note,owner_id,expected_revision}` → workflow note entity |
| **Note/general audit log** | GET `/api/workflow/history?entity_id=...` or without filter | `{events:[...]}`; this is the real audit route, not a Supabase `audit_log` table |
| Diligence / elections / judgment | POST `/api/workflow/records`; POST `/api/workflow/records/{id}/actions` | Existing record schema/refs/authority/revision; `{action,expected_revision,note}` → workflow entity |
| Sign-offs | GET `/api/workflow/signoff-preview?area=...&level=...`; POST `/api/workflow/signoffs`; POST `/api/workflow/signoffs/{id}/revoke` | Preview digest; `{area,level,expected_digest,note}`; `{note}` → dependency-bound **simulated** sign-off |
| Tasks / notifications | POST `/api/workflow/tasks` | `{id,state,assignee?,due_date?,expected_revision}` → validated private workflow entity |
| Readiness | GET `/api/workflow/readiness` | `{filing_ready:false,blockers,label}`; public POST readiness recording remains deliberately blocked |
| Version comparison | GET `/api/version-comparison?before=v1&after=v3` | Changed/added/removed lines, evidence and status differences |
| What-if | GET `/api/what-if?version=v3`; POST `/api/what-if/compare` | `{version,scenario_ids}` → stored-engine alternatives/effects/conflicts, no invented recomputation |
| Saved scenario comparison | POST `/api/what-if/analyses`; GET `/api/what-if/analyses` | Existing selection/note/revision schema → private hypothetical analysis/history |
| Timeline / historical evidence | GET `/api/timeline-replay?at=...`; GET `/api/timeline-replay/evidence?at=...&ref=...&version=...` | Historical snapshot or typed historical graph with future visibility boundaries |
| Change impact | GET `/api/change-impact?ref=...`; POST `/api/change-impact/reassess` | `{version,refs,note}` → scoped impact/assessment; mutation requires an independent reviewer/partner |
| Live changes / checkpoint | GET `/api/product/changes?after=...&wait_seconds=...`; POST `/api/product/checkpoint` | Existing bounded long polling → cursor/events; checkpoint payload → reviewer checkpoint |
| Collaboration / bulk / attachment metadata | GET `/api/product/overview`; GET `/api/product/bulk/catalog`; GET `/api/product/bulk/history`; GET `/api/product/history/{id}` | Existing typed workflow projections/catalog/history. Public communication, bulk-command and attachment writes/downloads are intentionally denied, not missing endpoints |
| Firm operations | GET `/api/product/operations?q=...` | Existing fictional engagement/workload/time/budget summary. Public POST `/api/product/time`, `/api/product/budgets` and administrative changes are intentionally denied |
| Security / administration | GET workflow overview/history/access-history (role checked); existing POST `/api/workflow/assignments`, `/api/workflow/policies`, `/api/workflow/engagement` | Public has no administrator role and cannot mutate assignments/policies/ownership; sensitive reveals remain denied |
| Filing / post-filing | GET `/api/lifecycle/overview`, history, snapshots/comparisons/client-review views where a record exists | Existing read schemas. All public lifecycle mutations and package/original access remain denied. No filing/delivery/payment/notice endpoint was added or enabled |

No required FastAPI endpoint was missing. The two public allowlist mismatches above were the only source-level integration gaps found. Public-denied Phase 6/7 operations remain supported in the secure profiles; they were not weakened to make browser requests succeed.

## Required deployment configuration

Vercel project must use the intended repository, production branch `main`, root **`frontend`**, Next.js, Node 22.x, install `npm ci`, build `npm run build -- --webpack`, and default Next.js output. Remove any dashboard `dist`/Vite/custom legacy output override. Keep the build command as specified so the npm postbuild verification runs. The Git integration must be installed/connected and no ignored-build rule should skip main.

Production variables:

```dotenv
WORKPAPER_PROFILE=public-demo
NEXT_PUBLIC_PUBLIC_DEMO=1
NEXT_PUBLIC_API_URL=
WORKPAPER_PUBLIC_ORIGIN=https://miraflores-workpaper.vercel.app
WORKPAPER_BACKEND_ORIGIN=https://miraflores-workpaper-xwip.onrender.com
```

No Supabase variables or credentials are needed. Remove stale Supabase/Vite-specific variables from this project if present, but doing that alone cannot change the old artifact into the new application.

Render already uses the public-demo architecture. Retain:

```dotenv
WORKPAPER_PROFILE=public-demo
WORKPAPER_ORIGINS=https://miraflores-workpaper.vercel.app
```

Start command stays `python run_public_demo.py`, root `backend`, one Free instance/worker, no disk and no configured historical DB path. No new backend variable, CORS wildcard, database service or security exception is required. After the commit is published, **manually deploy the latest commit on Render** to activate the two small allowlist corrections if Render auto-deploy remains off. This task does not deploy it.

Normal browsers call Vercel `/api`; the native rewrite preserves the frontend Origin, CSRF headers and cookies when forwarding to Render. Direct Render preflight was checked using the exact Vercel Origin and expected headers; no cross-origin browser connection workaround is needed. Existing credentialed CORS allows configured origins only and was not modified.

## Manual Vercel artifact/alias correction

1. Open the project actually owning `miraflores-workpaper.vercel.app` and inspect its **Current** production deployment, not just a deployment labeled with commit `4a901c3`.
2. Verify the connected Git repository/branch, root, build/install commands and default output settings above.
3. Open that deployment's immutable URL. The intended app has a public-demo banner, simulated-role menu, Next.js `/_next/` scripts and working `/api/workflow/session` JSON. A `/vite.svg` / `/assets/index-*.js` shell identifies the wrong artifact.
4. If the immutable URL is correct while the public hostname is wrong, correct the hostname's project/domain/production assignment and manually promote the correct deployment to Current. If the immutable URL is also Vite, correct the project's build root/output/routing overrides before rebuilding. Do not guess which case applies without comparing that URL.
5. Push the reviewed commit once the project/Git settings are correct. The repository now permits Git-triggered deployment. Domain assignment and project-level skip/promotion settings cannot be repaired by deleting SDK URLs from source where those URLs do not exist.
6. Verify note creation, audit loading, private visitor isolation and FILING BLOCKED on the actual public URL. No promotion, domain reassignment, push or deployment was performed by this task.

## Verification and file manifest

**692 tests passed, zero final failures**, preserving all previous 677: 571 backend + 69 browser + 52 configuration/build-guard tests.

| Check | Result |
|---|---|
| Complete backend pytest | 571 passed, 0 failed |
| Public HTTPS browser suite | 5 passed, including two new actual-UI API integration tests |
| Signed-gateway proxy browser suite | 7 passed |
| Token-protected assignment browser suite | 3 passed |
| Legacy browser suite | 14 passed |
| Strict browser suite | 40 passed |
| Configuration/artifact/source tests | 52 passed (15 secure + 12 assignment + 13 public + 12 new guards) |
| TypeScript | Passed |
| ESLint | Passed |
| Production webpack build with the exact supplied origins | Passed, including postbuild verification of 21 browser assets |
| Original SQLite integrity / foreign keys | `ok` / zero violations, checked read-only |
| Original packet | SHA-256 unchanged |

The backend run took 109.21 seconds with one existing Starlette TestClient deprecation warning. Public browser tests took 17.2 seconds; the proxy suite took 23.7 seconds; assignment rerun took 16.2 seconds; legacy took 35.4 seconds. A broader regression exposed a pre-existing logout-test race: workspace unmount occurs before the server logout request completes. The test now awaits that response before retaining its original 401 authorization assertion. No application logout/authentication behavior was changed. An initial new impact test incorrectly attempted a reviewer-only action as preparer; it now asserts preparer rejection and switches to the independent reviewer, preserving the existing rule.

Every production build exercised by these browser suites runs the new postbuild gate. Negative tests reject SDK/host/table signatures, Vite-only output, missing Next.js metadata, missing/wrong API rewrites and a legacy root page. Source AST inspection confirms only the shared session module directly calls fetch; application source has no alternative SDK/XHR/WebSocket/EventSource client.

Created files:

- `API_INTEGRATION.md` — this source/network mapping, evidence, settings and verification report.
- `frontend/scripts/verify-build.mjs` — fail-closed artifact verification after Next.js builds.
- `frontend/scripts/verify-build.test.mjs` — build, deployment configuration and single-network-boundary regressions.
- `frontend/public-tests/api-integration.spec.ts` — actual note/audit UI and finding-review endpoint tests through HTTPS Next.js → FastAPI.

Modified files:

- `frontend/vercel.json` — removed automatic Git deployment disablement.
- `frontend/package.json` — added postbuild verification and its test command; no dependency changes.
- `backend/app/public_demo.py` — two narrow allowlist path corrections; all inner permissions remain enforced.
- `backend/tests/test_public_demo.py` — actual review alias and impact route, CSRF, independent role, history isolation and blocked-policy regression.
- `frontend/assignment-tests/assignment.spec.ts` — wait for server logout before asserting the existing unauthorized-response check.
- `PUBLIC_DEMO_DEPLOYMENT.md` — current auto-deployment/build verification instructions and integration link.
- `README.md` — link to the integration report.

No frontend runtime client, database, migration, tax computation, core approval rule, packet, secure launcher or CORS code was changed. Source mentions of forbidden services in the new guard/negative tests are diagnostic strings, not application dependencies or network calls.

Run backend checks from `backend`: `.venv/bin/python -m pytest -q`. From `frontend`, run `npm run test:integration-config`, the existing deployment/assignment/public configuration suites, `npm run test:public`, `npm run test:deployment`, `npm run test:assignment`, `npm run test:e2e`, and `npm run test:e2e -- --config=playwright.workflow.config.ts` sequentially; then `npx tsc --noEmit`, `npm run lint`, and the configured production build. Test servers and data are isolated; no live notes or audit rows were written.

After reviewing the diff, from repository root:

```sh
git add API_INTEGRATION.md PUBLIC_DEMO_DEPLOYMENT.md README.md backend/app/public_demo.py backend/tests/test_public_demo.py frontend/vercel.json frontend/package.json frontend/scripts/verify-build.mjs frontend/scripts/verify-build.test.mjs frontend/public-tests/api-integration.spec.ts frontend/assignment-tests/assignment.spec.ts
git commit -m "Verify FastAPI frontend builds and enable Vercel Git deployments"
git push origin main
```

These commands were not executed by the agent. A push may trigger Vercel deployment once the correct project is connected; that is the intended behavior requested by the owner. It cannot fix an unrelated project's alias or skipped production assignment. Render may separately require a manual deployment of the same reviewed commit for the allowlist corrections. The live-domain mismatch is not claimed resolved before those manual account checks and deployment verification.
