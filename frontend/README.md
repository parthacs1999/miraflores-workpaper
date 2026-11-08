# MiraFlores frontend

The Next.js interface for the MiraFlores Tax Workpaper application. For project features, screenshots, backend installation, security boundaries, and full setup instructions, see the [repository README](../README.md).

## Local development

Install dependencies with `npm ci`. Start the backend in a separate terminal:

```sh
# From the repository root
cd backend
.venv/bin/python run_secure.py --demo
```

Then start the frontend:

```sh
# From frontend/
npm run dev
```

Open **http://localhost:3000** and select a demonstration staff session. Use the identity menu to switch or end a session; the bell opens live activity and notifications.

The API defaults to `http://localhost:8000`. Override it with `NEXT_PUBLIC_API_URL` in `.env.local`, then restart Next.js. Use `localhost` consistently for browser and API hosts. Backend cookie, CSRF, Origin, assignment, and clearance checks remain mandatory.

The application preserves the supplied engine packet and displays approved adjustments separately. The real case remains **FILING BLOCKED**. Demo identity selection is not authenticated identity assurance, and simulated lifecycle actions do not create legal signatures or real tax-agency submissions.

## Checks

```sh
npx tsc --noEmit
npm run lint
npm run build -- --webpack
```

For browser tests, install Chromium once with `npx playwright install chromium`, then run these suites sequentially:

```sh
npm run test:e2e
npm run test:e2e -- --config=playwright.workflow.config.ts
```

Both suites start isolated servers and disposable backend databases. See the root README for prerequisites and required ports.

## Code and design

- `src/app/`: application entry point, layout, and design-system styles.
- `src/components/shell/`: navigation, app shell, dashboard, and URL state.
- `src/components/ui/`: shared controls, tables, dialogs, statuses, and state-machine presentation.
- `src/components/`: evidence, reconciliation, adjustments, review, collaboration, analysis, and filing workspaces.
- `tests/`: legacy browser behavior.
- `workflow-tests/`: strict sessions, permissions, workflows, and redesign coverage.

See [UI_REDESIGN.md](../UI_REDESIGN.md) for the component architecture, screenshots, exact implementation manifest, accessibility decisions, and known limitations.
