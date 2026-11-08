# MiraFlores frontend redesign

## Scope and boundaries

Implemented a shared application shell, engagement dashboard, and redesigned presentation of the Phase 1–7 workspaces. This is a frontend implementation against the existing FastAPI contracts, not a replacement tax engine or a set of mockups.

The three-page original case-study PDF, Instructions.json, PHASE1.md–PHASE7.md, frontend components, backend API/security boundaries, and existing browser assertions informed the screen inventory. The original horizontal navigation and permanent live-change panel are captured in `docs/ui-redesign/before.png`.

No backend code, migrations, tax calculation rules, or packet data changed. No database records were deleted or rewritten by the redesign. Browser regression runners continue to create isolated temporary databases. Local preview sessions create normal session/access audit entries; screenshots do not create adjustments, approvals, questions, or filing events.

Instructions.json remains byte-for-byte unchanged:

```
ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19
```

The real packet remains **FILING BLOCKED**. Simulated highlighting is not OCR verification; demonstration sessions, approvals, client statements, and filings do not establish authenticated identity, legal electronic signatures, or agency submission.

## Design system

- Geist sans and mono, using the existing Next font configuration.
- Background `#F8FAFC`, surface `#FFFFFF`, text `#0F172A`, secondary text `#64748B`, accent `#2563EB`, success `#059669`, warning `#D97706`, error `#DC2626`, border `#E2E8F0`.
- Compact financial tables, tabular numbers, restrained shadows, rounded surfaces, consistent spacing, semantic status labels, and Lucide icons. `lucide-react` is the only added runtime dependency.
- Shared primary/secondary/destructive buttons, labeled controls, skeletons, empty/error states, inline validation feedback, and live-region success notifications.
- Detailed backend objects are presented as structured read-only records with progressive disclosure and “Show more” controls instead of large serialized JSON walls. Raw audit/source representations remain available where preserving exact evidence is useful.

## Navigation architecture

The left sidebar has collapsible groups, a compact mode, an active-page indicator, and a mobile navigation overlay. The top bar includes engagement/year context, filing-blocked status, breadcrumbs, workflow search, a persistent DEMO indicator, masking state, activity access, and staff identity/session switching.

| Group | Screens and preserved capabilities |
| --- | --- |
| Overview | Dashboard; Filing Readiness with detailed blockers and recorded assessments; Tasks, assignment/deadline edits, completion/reopening and notification acknowledgments |
| Tax Workpaper | Return Explorer; Evidence & Documents; Reconciliation & Findings; Adjustments |
| Workpaper tools | Document Accountability; Evidence Resolver; persistent legacy Review Findings, available from the workpaper toolbar |
| Review & Collaboration | Diligence, applicability/authority/evidence, revisions/submission/independent approval/reopening; blocking Review Notes and responses/independent resolution; scoped demonstration Sign-offs, revocation and history; Collaboration; Supporting Attachments; Bulk Actions & Undo |
| Analysis | Version Comparison; What-if Scenarios; Timeline Replay; Change Impact |
| Filing | Finalization; Filing Status; Extensions & Payments; Client Authorization; Amendments; Notices & Examination; Carryovers & Planning |
| Firm | Assignments/ownership and administrator policy revisions; Firm Operations; Security & Access, sensitive-purpose controls and audit history |

Administrator navigation retains operational access and excludes tax-detail workspaces. Administrator deadline-assignment bulk operations remain available through Firm Operations → Bulk Actions. Area-restricted staff retain their backend-filtered diligence, review notes, scoped sign-off history, assignments and supported operational workspaces; a manually entered forbidden view displays an assignment/access explanation. Backend authorization remains decisive.

Navigation uses `?view=<screen>&ref=<identifier>`, supports browser back/forward, and does not put notes, source bodies, session credentials, or sensitive values into URLs. Example: `/?view=return&ref=SchC.1`. The original API routes and finding/resource IDs remain unchanged.

Workflow search (button or Cmd/Ctrl+K) searches actual application destinations. It does not pretend to search all evidence. Source search lives in the return/document explorers; the existing backend engagement search remains in Firm Operations.

## Component architecture

- `AppShell`: grouped sidebar, top bar, session popover, responsive navigation, workflow search and notification/activity drawer.
- `navigation` / `useNavigation`: typed navigation context, destination inventory, URL updates and browser-history subscription.
- `EngagementDashboard`: real authorized read models, summary/team, KPIs, priority queue, current finding-review progress, recent change metadata and workflow shortcuts.
- `ReturnLineContext`: stored prior-year values, independently sourced check conclusions, supporting-reference count and related-finding navigation.
- `LinkedAttachments`: authorized attachment metadata linked to a document, with navigation to purpose-audited original downloads.
- `ui/primitives`: PageHeader, StatCard, DataTable, StatusBadge, DetailDrawer, ActivityTimeline, EmptyState, ErrorState, Skeleton, Notice, FormField, SectionCard, ConfirmationProvider/useConfirm, Pagination and RecordDetails.
- `StateMachine`: read-only display of a recorded simulated filing stage. It does not create a transition or imply real-world acceptance.
- Existing domain components retain their API calls, revision/sequence checks, permission-dependent actions and persistence. Analysis and filing accept controlled section selection, preserving their working snapshot/form context while navigating between related sections.

## Screens and interactions

### Dashboard

The landing page shows the supplied engagement, year, baseline version and assigned preparer/reviewer/partner. KPIs use unified findings, document accountability, the adjustment ledger, workflow records/tasks, and collaboration questions. Missing metrics show an unavailable state; restricted metrics say “Restricted.”

“Pending approvals” explicitly means submitted workflow records plus submitted adjustments. It is not a fabricated count of every possible firm approval. “Blocking questions” includes unresolved blocking collaboration questions and unapproved practice-question records. Review progress counts current resolved finding decisions, distinguishes stale decisions, and does not claim return completion or filing readiness.

Priority items navigate to supported workspaces. Recent activity uses the existing authorized change feed. The full “Since I last looked” feed, personal checkpoint, pause/reconnect, missed-event recovery, and refresh controls now live in the activity drawer, which keeps the feed mounted when closed.

### Return Explorer and evidence

- Search, form and federal/California filters; 40 return lines per page.
- Separate engine, proposed and approved workpaper values. Approved values are taken only from current, non-stale approved ledger entries for the exact target. Draft alternatives are never summed. No downstream tax recomputation occurs in the frontend.
- An unavailable ledger is explicitly reported; it cannot silently masquerade as an approved workpaper value.
- Master/detail inspector with calculation lineage, direct sources, document navigation, prior-year evidence where supplied, reconciliation conclusions and related findings.
- Searchable documents, document-type and disposition filters; all six accountability distinctions remain available.
- Compact accountability table covering all 74 documents; reason references, page-level duplicates and unresolved provenance remain inspectable.
- Reverse tracing, extracted-field navigation, simulated source pages, exact/ambiguous source matches, CPA verification method/notes/source selection, revocation and append-only history remain functional.
- Linked supporting attachment metadata stays distinct from extracted/verified source evidence.

### Reconciliation, adjustments and review

Findings are filtered by area, jurisdiction and severity, searched, and paginated at 20 per page. A master/detail investigation layout exposes expected/reported/difference/tolerance, preserved inputs and computation steps, evidence references, review decisions, adjustment links and history. Matches and unsupported checks remain available in the check selector.

The adjustment ledger preserves drafts, revisions, submissions, independent/partner approval controls, rejection, reversal, supersession, conflict checks, approved summaries and immutable audit history. Consequential ledger transitions require a confirmation dialog; server-side controls remain authoritative.

The legacy CPA review queue also has search and pagination. Selecting a finding keeps its review form open while showing its corresponding evidence. This preserves the original review/persistence behavior.

### Collaboration, operations and diligence

Assignments, diligence, blocking notes, sign-offs and tasks share the same compact controls and surfaces. Collaboration and lifecycle forms use responsive grids, explicit empty states, structured record detail and contextual action controls. Discussion response controls appear once a question exists. Threading, staff-mediated client declarations, attachments, metadata revisions, independent resolution and history remain available.

Bulk selection, item revisions, exact idempotent retries, atomic execution and audited compensation remain intact. Firm Operations retains the single real supplied engagement search, packet versus revised budgets, actual time/revisions/voiding, workload/assignment tables, deadlines and blockers.

### Analysis and filing

The four analysis screens retain stored-version comparison, navigable lineage, scenario baseline/conflict warnings, hypothetical-analysis history, time-bounded historical evidence and scoped change-impact assessment.

All seven filing areas have dedicated sidebar destinations and consistent forms/record history. Recorded filing runs show a simulated state-machine rail. Finalization still distinguishes a demonstration freeze from blocked authoritative finalization. Extensions/payments, bound client authorization, rejection/correction/resubmission, client-copy packages/delivery, separate amendments, scripted notices/examination packages and carryover/planning provenance retain their existing controls.

## Session and security behavior

- A clear initial staff selector exposes the configured packet staff and role. Active-session switching lives in the identity popover; end-session remains available there.
- Initialization failures retain the backend URL/configuration explanation and retry controls rather than showing a silent empty dropdown.
- Identity changes unmount the prior authorized workspace, clear sensitive mode and invalidate in-flight reads. This happens before the server rotates the session cookie, preventing a stale unauthorized read from tearing down the newly selected session.
- Genuine 401 responses clear the visible workspace and show a recoverable session/access message. Aborted or old-epoch responses are discarded. Existing cross-tab and page-cache protections remain intact.
- Confirmation state is keyed to the current session, so a pending decision does not survive an identity change.
- Cookie credentials, CSRF headers, audited sensitive-purpose headers, `no-store` reads and backend redaction are preserved. No browser persistence or new client-side sensitive-data cache was introduced.
- Protected original downloads require a meaningful purpose and confirmation; the existing authorized download and content-hash verification remain mandatory. Originals are not rendered inline.

## Responsive and accessibility decisions

- Desktop sidebar and contextual inspector; compact sidebar option; off-canvas navigation and stacked inspection on smaller screens.
- Return lines and findings are paginated; tables scroll inside their surfaces rather than expanding the whole document. Mobile source selection scrolls the inspector into view.
- Native modal dialogs provide focus containment, Escape dismissal, focus restoration and accessible labels. Confirmation cancellation performs no mutation.
- Skip link, named icon buttons, keyboard focus indicators, semantic table headers, native form controls, live-region feedback, explicit state text and reduced-motion styling.
- Text uses the requested secondary-color contrast rather than pale decorative text for essential labels. Status meaning is also conveyed in words.
- Browser verification includes desktop and 390×844 mobile layouts, keyboard cancellation/focus, navigation/search, zero page overflow, and uncaught console/page-error checks on the full workspace navigation pass.

## Exact file manifest

### Created

```
UI_REDESIGN.md
frontend/src/components/LinkedAttachments.tsx
frontend/src/components/ReturnLineContext.tsx
frontend/src/components/shell/AppShell.tsx
frontend/src/components/shell/EngagementDashboard.tsx
frontend/src/components/shell/navigation.tsx
frontend/src/components/shell/useNavigation.ts
frontend/src/components/ui/primitives.tsx
frontend/src/components/ui/StateMachine.tsx
frontend/tests/ui-helpers.ts
frontend/workflow-tests/ui-redesign.spec.ts
docs/ui-redesign/before.png
docs/ui-redesign/dashboard.png
docs/ui-redesign/workpaper.png
docs/ui-redesign/reconciliation.png
docs/ui-redesign/collaboration.png
docs/ui-redesign/filing.png
docs/ui-redesign/mobile.png
```

### Modified

```
frontend/.gitignore
frontend/eslint.config.mjs
frontend/package.json
frontend/package-lock.json
frontend/src/app/globals.css
frontend/src/app/layout.tsx
frontend/src/app/page.tsx
frontend/src/components/AdjustmentWorkspace.tsx
frontend/src/components/ChangeAnalysisWorkspace.tsx
frontend/src/components/DocumentAccountability.tsx
frontend/src/components/DocumentInspector.tsx
frontend/src/components/EvidenceResolver.tsx
frontend/src/components/FieldVerification.tsx
frontend/src/components/FilingLifecycleWorkspace.tsx
frontend/src/components/FirmWorkflow.tsx
frontend/src/components/LiveUpdates.tsx
frontend/src/components/ProductWorkspace.tsx
frontend/src/components/ReconciliationDashboard.tsx
frontend/src/components/ReviewWorkspace.tsx
frontend/src/components/SourceVerification.tsx
frontend/src/components/evidence-types.ts
frontend/src/components/session.tsx
frontend/src/components/workpaper-types.ts
frontend/tests/adjustments.spec.ts
frontend/tests/evidence-phase2.spec.ts
frontend/tests/finding-evidence.spec.ts
frontend/tests/reconciliation.spec.ts
frontend/tests/review-persistence.spec.ts
frontend/tests/source-verification.spec.ts
frontend/tests/workpaper.spec.ts
frontend/workflow-tests/firm-workflow.spec.ts
frontend/workflow-tests/phase5.spec.ts
frontend/workflow-tests/phase6.spec.ts
frontend/workflow-tests/phase7.spec.ts
frontend/workflow-tests/session-initialization.spec.ts
```

Existing compressed component/test files were formatted to make the retained domain controls reviewable. Source/verification contracts are unchanged. The new verification build directory is ignored by Git and ESLint, just like the existing isolated browser-test builds. Source lint rules are unchanged. No build output, session secret, database or test fixture database is part of the manifest.

## Verification

| Check | Result |
| --- | --- |
| Pytest | 474 passed |
| Legacy Playwright regression | 14 passed |
| Strict Playwright, including redesign coverage | 40 passed (28 existing + 12 new) |
| TypeScript | Passed, no errors |
| ESLint | Passed, no errors or warnings in source/tests |
| Webpack production build | Passed; `/` and `/_not-found` generated successfully |
| SQLite integrity | `ok`; zero foreign-key violations |
| Instructions.json | Original SHA-256 unchanged |
| Desktop/mobile visual review | Six finished captures inspected; no uncaught page errors in capture pass |

**528 tests passed: all 516 existing tests plus 12 new browser tests. Zero tests failed in the final runs.** Twelve new browser tests supplement the original suite. Earlier verification exposed review-form navigation, session-switch/stale-response, selector, and populated mobile layout regressions; the implementation fixes and intentional selector corrections are retained. No assertion was relaxed and no source lint rule was disabled. The backend run reports one existing Starlette/TestClient deprecation warning; it has no test failures.

Commands:

```sh
# Repository root
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q

# frontend/
./node_modules/.bin/tsc --noEmit
npm run lint
npm run test:e2e
npm run test:e2e -- --config=playwright.workflow.config.ts
NEXT_DIST_DIR=.next-ui-verification NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build -- --webpack
```

The browser suites use their existing isolated legacy and strict-mode server/database configurations. Existing assertions were retained; intentional selector changes target grouped sidebar destinations, paginated finding search, the session menu, the activity drawer and the named budget table. A helper explicitly accepts visible confirmation dialogs where older flows now require confirmation; new tests separately verify cancel/no-mutation behavior.

New coverage includes real dashboard counts, all workspace navigation, live-drawer behavior, line deep links/back navigation and filters, finding pagination/calculations, confirmation cancellation/focus, scoped/admin access, immediate identity clearing, mobile layout, workflow search/sidebar collapse, expired access, unavailable-ledger honesty, stale-response identity-switch safety, and preservation of area-restricted diligence/review access.

## Demonstration walkthrough

1. Run the strict local demo backend: `cd backend && .venv/bin/python run_secure.py --demo`. In a second terminal run `cd frontend && npm run dev`. Keep the existing frontend API URL pointed at `http://localhost:8000` and use `http://localhost:3000` in the browser.
2. Select Priya (`st-01`) and **Start / switch session**. The Dashboard shows actual authorized metrics, assigned staff, priority discrepancies and current review progress.
3. Open **Return Explorer**, search `SchC.1`, and select Gross receipts. Inspect stored engine values, prior-year evidence and related findings. Follow a source into the simulated document and field verification. No value changes occur merely by inspecting it.
4. Open **Reconciliation & Findings**, search `business.receipts`, and select the duplicated-card-receipts finding. Compare 151300 expected versus 163700 reported and the 12400 difference; inspect the source references and computation method.
5. Use **Adjustments** for a documented proposed correction. Draft, submit and independently approve only through the existing workflow, switching staff through the top-right identity menu. Consequential actions require confirmation; the original engine is preserved.
6. Open **Supporting Attachments**, **Collaboration**, or **Bulk Actions & Undo** under Review & Collaboration. Link real supplied supporting files, ask an evidence-backed question or perform a supported bulk operation. Downloads require a purpose; question resolution remains independent; undo preserves history.
7. Use the bell to open **Activity & notifications**. Pause/reconnect, inspect recovered changes and mark the displayed checkpoint seen. Close the drawer to return to the workspace without stopping the feed.
8. Explore the four **Analysis** destinations. Stored versions, hypothetical alternatives and historical replay are explicitly distinguished.
9. Open **Filing Readiness** for the detailed authoritative blockers. Open **Finalization** and the other six Filing destinations for demonstration workflows. The real packet remains blocked throughout.
10. Open **Firm → Assignments**, **Firm Operations**, and **Security & Access** for ownership/policies, workload/budget/time and audited masking controls. Administrator views remain operational, not tax-detail access.
11. At a mobile viewport, open the menu icon to navigate; forms stack and the document/return inspector is brought into view after source selection.

## Finished screenshots

- [Dashboard](docs/ui-redesign/dashboard.png)
- [Return explorer](docs/ui-redesign/workpaper.png)
- [Reconciliation](docs/ui-redesign/reconciliation.png)
- [Collaboration](docs/ui-redesign/collaboration.png)
- [Filing](docs/ui-redesign/filing.png)
- [Mobile dashboard](docs/ui-redesign/mobile.png)

Captured from the local strict demonstration with masking enabled and actual supplied engagement data. The development framework overlay is excluded from the captures; no product content or metrics are fabricated.

## Known limitations

- This remains the supplied single-engagement prototype. No invented clients, decorative analytics, agency integrations, legal signatures or authenticated client portal were added.
- Search in the top bar is workflow navigation; evidence/return and engagement searches retain their existing scopes.
- Full-area tax views still require an entire-engagement assignment because the existing aggregate APIs are not area-filtered. The frontend does not bypass those APIs or expose their data to scoped staff.
- Prior-year values and reconciliation coverage are limited to packet-supported references/rules. Missing/unsupported data is explicit. Approved exact-target overlays are not a recomputed return.
- Large nested audit objects use progressive disclosure with bounded rendering; downloaded packages retain their original backend formats. Some technical identifiers remain visible for traceability.
- Accessibility decisions and Chromium desktop/mobile checks are implemented; this is not a claim of a complete WCAG certification, screen-reader audit, or Safari/Firefox compatibility certification.
- The existing long-poll feed and its 300-item retained window are preserved, with checkpoint/reconnect recovery supplied by the backend. No external notification delivery was added.
- Deployment, final hand-in material and video production remain outside this work.
