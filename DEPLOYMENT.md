# Restricted demonstration deployment

**Status: BLOCKED — SECURITY OR INFRASTRUCTURE REQUIREMENTS REMAIN.** Code is prepared for review; no service, identity policy, DNS record, deployment or paid resource has been created. Read [the security review](DEPLOYMENT_SECURITY.md) and [verification report](DEPLOYMENT_READINESS.md) before creating services.

## Architecture and original blockers

The original launcher listened only on loopback; database initialization was lazy; demo staff selection was not authenticated identity; frontend defaults targeted localhost; and cross-site Strict cookies would not work reliably between Vercel and Render domains. A Next.js Function proxy would also conflict with the existing 5 MiB attachment transport: Base64 JSON exceeds Vercel's [4.5 MB Function payload limit](https://vercel.com/docs/functions/limitations).

Prepared path:

```text
Named reviewer + identity-provider MFA
  → Cloudflare Access protected custom HTTPS domain
  → Vercel Next.js native external /api rewrite
  → Render FastAPI (verifies signed Access JWT on every non-health request)
  → one SQLite database on /var/data persistent disk
```

Cloudflare Access is a proposed integration awaiting owner approval, not an already configured provider. There is no password-only production fallback. Verified Access subjects map server-side to one fixed demonstration packet staff profile each. Role controls, independent approval, masking and filing blockers remain enforced. These are not legally valid signatures or actual agency submissions.

The native [Next/Vercel external rewrite](https://vercel.com/docs/routing/rewrites) avoids a Function body handler and preserves cookies, CSRF headers, protected download headers and bounded long polling. Its 5 MiB round trip passed locally through an actual HTTPS Next.js production proxy. **Vercel edge forwarding, payload limits and Cloudflare behavior still require live qualification.**

## Before creating resources

1. Review changes and the historical database finding in the security report. Keep the repository restricted where appropriate. App authentication cannot protect files already published in Git.
2. Approve an identity provider, custom domain and named reviewers. Configure an Access self-hosted application protecting the entire custom hostname, including `/api/*`. Require MFA and an explicit people allowlist. Do not use Bypass, public allow rules or service-token access.
3. Configure a short Access session (recommended 15 minutes; backend rejects tokens whose total lifetime exceeds one hour). Obtain its exact issuer, application audience and cryptographically verified user subjects. Assign each reviewer exactly one packet profile; preserve preparer/reviewer independence.
4. Review and commit changes on local `main`, then deliberately publish `main` after checking remote auto-deployment settings. At preparation time local `main` was advanced to the completed product; remote `origin/main` was older. Nothing was pushed by this task.
5. Disable connected auto-deployments until approved. Importing a Render Blueprint or creating a Vercel project can itself deploy/create billable resources; configuration files do not prevent that initial action.

## Render settings

Use [render.yaml](render.yaml) as a reviewed blueprint, not an instruction to apply it now.

| Setting | Value |
|---|---|
| Service / runtime | Web service / Python |
| Branch / root | `main` / `backend` |
| Python | `3.13.18` (pin; target runtime must be qualified) |
| Region | Virginia; colocate Vercel execution region where practical |
| Instance | `1c-2g`, one instance, no autoscaling |
| Build | `pip install -r requirements.txt` |
| Start | `python run_secure.py --hosted` |
| Health | `/health` (minimal public response) |
| Shutdown allowance | 45 seconds; Uvicorn graceful timeout 30 seconds |
| Disk | 5 GB mounted at `/var/data` |
| Automatic deployment | Off |

Required backend environment:

```dotenv
PYTHON_VERSION=3.13.18
PYTHONDONTWRITEBYTECODE=1
WEB_CONCURRENCY=1
WORKPAPER_ENV=production
WORKPAPER_MODE=access
WORKPAPER_DISK_ROOT=/var/data
REVIEW_DB_PATH=/var/data/workpaper.db
WORKPAPER_ORIGINS=https://workpaper.YOUR-DOMAIN.example
WORKPAPER_ACCESS_ISSUER=https://YOUR-TEAM.cloudflareaccess.com
WORKPAPER_ACCESS_AUDIENCE=YOUR_APPLICATION_AUDIENCE
WORKPAPER_ACCESS_STAFF={"YOUR_VERIFIED_USER_SUBJECT":"st-01","ANOTHER_VERIFIED_USER_SUBJECT":"st-02","PARTNER_VERIFIED_USER_SUBJECT":"st-03"}
```

Replace every placeholder. `WORKPAPER_CREDENTIALS` must remain unset. Render supplies `PORT`; the launcher binds `0.0.0.0:$PORT`, one worker, no reload, no access request logging. Missing identity settings, demo mode, extra workers, absent disk mounts, invalid paths, migration failures or integrity errors stop startup. The health endpoint does not bypass authenticated data access.

Staff IDs must come from the packet, not invented users. `st-01`, `st-02`, `st-03` are the existing Priya, Daniel and Helen profiles. Additional profiles must retain their existing permissions. Do not give one person multiple roles for self-approval.

The pinned target Python is a patched release; local automated tests ran on Python 3.13.5. Successful Render installation and the same tests on 3.13.18 remain an explicit release gate. See [Python release](https://www.python.org/downloads/release/python-31318/) and [Render version configuration](https://render.com/docs/python-version).

## Vercel settings

| Setting | Value |
|---|---|
| Source branch / root | `main` / `frontend` |
| Framework / Node | Next.js / 22.x |
| Install | `npm ci` |
| Build | `npm run build -- --webpack` |
| Output | Next.js default; no static export or output override |
| Git deployment | Disabled in `frontend/vercel.json` pending review |

Set production environment variables (and equivalent build/runtime values):

```dotenv
WORKPAPER_HOSTED=1
NEXT_PUBLIC_API_URL=
WORKPAPER_BACKEND_ORIGIN=https://YOUR-SERVICE.onrender.com
WORKPAPER_PUBLIC_ORIGIN=https://workpaper.YOUR-DOMAIN.example
```

`NEXT_PUBLIC_API_URL` must exist with an **empty value**: browser calls use `/api`, never localhost. The other three values configure server-side hosting behavior; no JWT, password, staff mapping or session secret belongs in frontend variables. Do not set `WORKPAPER_LOCAL_BUILD` on Vercel. Missing production configuration fails the build.

The proxy destination is fixed to the configured HTTPS `*.onrender.com` origin; user input cannot choose another host. Noncanonical hosts, including default Vercel aliases, redirect to the protected custom origin. Configure the domain using the exact DNS records Vercel supplies, Cloudflare TLS Full (strict), Access protection and explicit API cache bypass. Do not use Flexible TLS. Validate that Cloudflare forwards its signed assertion through Vercel to Render; missing assertions fail closed.

## Sessions and secrets

Cloudflare manages signing keys; obtain issuer/audience/subject mappings through the provider's administrative tooling. Never generate production assertions manually or substitute email headers. The application generates session tokens and CSRF tokens using its cryptographic random generator; only hashed session tokens persist. There is no application session signing secret to put in JavaScript.

Access tokens are verified for signature, issuer, audience, type and time. The app session expires at the earlier of 30 minutes or JWT expiry. The `mf_session` cookie is Secure, HttpOnly, host-only, path `/`, SameSite Strict. Logout revokes the current app session and navigates to Access logout. Removing a mapped identity and restarting invalidates sessions via the configuration epoch. Secure backup encryption keys should be generated with an approved tool such as `age-keygen`, stored separately from backups and Git; provider/admin account credentials belong in the provider secret manager with MFA.

## Persistent data, backup and restore

[Render disks](https://render.com/docs/disks) require a paid single-instance service. Only mounted disk contents survive redeployments; the normal filesystem is ephemeral. Disks are unavailable at build time. Disk-backed services have restart/deploy downtime and cannot use ordinary horizontal scaling. Hosted startup checks the real mount, initializes an empty database and applies existing migrations plus additive migration 007. It enables WAL, checks integrity/foreign keys, applies restrictive file permissions, and holds an exclusive service lock. No records are deleted. A fresh deployment does **not** automatically import local records.

To preserve existing local records, create a consistent backup before deployment and transfer it over an approved encrypted administrative channel to the mounted disk. Never commit the database or upload it through a public application endpoint.

From repository root, local backup example:

```sh
backend/.venv/bin/python backend/scripts/backup_sqlite.py --source backend/data/reviews.db --destination /PRIVATE/BACKUP/DIRECTORY/workpaper-UNIQUE.backup
```

From Render's backend working directory, online backup:

```sh
python scripts/backup_sqlite.py --source /var/data/workpaper.db --destination /var/data/backups/workpaper-UNIQUE.backup
```

The tool uses SQLite's consistent online backup API, refuses overwrite, verifies integrity and writes a SHA-256 manifest. Use a unique timestamp per run. Schedule and monitor encrypted off-disk copies to an owner-controlled backup destination; this repository does not provision an external backup scheduler or storage account. Define an RPO/RTO, backup daily or more frequently as needed, rehearse recovery and restrict administrative access. Disk/provider snapshots alone are not a consistent SQLite backup strategy.

Restore only while the application is stopped. A shell attached to a live service will be refused by the shared lock. One approach is a reviewed, temporary Render start command, executed after the old process stops:

```sh
python scripts/restore_sqlite.py --offline --backup /var/data/backups/workpaper-UNIQUE.backup --database /var/data/workpaper.db --sha256 VERIFIED_SHA256 && python run_secure.py --hosted
```

The tool validates checksum/integrity, saves the entire existing state in a pre-restore backup, replaces the active database under lock, and records a restore receipt. Repeating the same backup is refused to prevent accidental repeated rollback. Immediately restore the normal start command after success. Newer audit records remain preserved in the pre-restore backup but are not magically merged into an older restored state. Reconcile recovery explicitly; do not edit or concatenate audit tables. Preserve all recovery artifacts under retention policy.

Monitor disk growth, SQLite lock errors, memory, backup age and availability. Expand the disk before capacity is exhausted; do not prune audit history to save space. A larger paid instance may be necessary under load. If budget cannot support persistent disk/single-instance operation, deployment is blocked; the smallest alternative is an approved paid durable database migration project, not ephemeral SQLite or an unreviewed PostgreSQL rewrite.

## Costs and assumptions

As verified during preparation, [Render pricing](https://render.com/pricing) lists `1c-2g` at $25/month and disk at $0.25/GB/month: the proposed 5 GB backend is approximately **$26.25/month**. A low-load `0.5c-512mb` $7 instance with 1 GB disk would start around **$7.25/month**, but that is not a capacity recommendation for Base64 uploads and snapshot-heavy work. [Vercel Pro](https://vercel.com/docs/plans/pro-plan) starts at $20/month plus usage, yielding approximately **$46.25/month** for the proposed baseline. Hobby eligibility is limited; do not assume commercial use is free. [Cloudflare Access](https://www.cloudflare.com/plans/) offers a free tier for up to 50 users subject to its current terms. Domain, identity provider, encrypted offsite backup, taxes, seats and usage overages are additional. Confirm current prices before purchasing.

## Release gates and actual-platform smoke test

After approval and before inviting reviewers:

- Verify the exact target Python/Node build, disk mount, one worker and no reload. Review logs for secret/header/body leakage.
- Confirm anonymous/forged/expired JWT requests fail on both the custom domain and direct Render origin. Public `/health` must disclose no packet data.
- Confirm default Vercel aliases redirect to the protected domain. A signed reviewer sees only their mapped staff profile; cross-role requests and arbitrary switching fail.
- Confirm cookie attributes, CSRF and wrong-Origin rejection through the deployed proxy; identity changes/expiration must immediately clear protected UI state.
- Exercise masked D71, sensitive-purpose download auditing, a 5 MiB attachment round trip with matching hash, and long polling/reconnect. Do not weaken limits or convert to a Function proxy if an edge limit fails; investigate hosting compatibility first.
- Confirm the real packet is still filing-blocked, independent approval remains enforced and no real submission/delivery controls exist.
- In an isolated deployment test database, create audited records, restart/redeploy and verify persistence; rehearse checksum-verified offline restore. Do not fabricate records in the real engagement.
- Confirm Access policy, MFA, allowlist, API no-cache behavior and revocation procedure with a second independent reviewer.

Do not open access until these gates pass. This is a restricted prototype demonstration, not production tax-processing or legal e-signature infrastructure.

## Local development and verification

Local behavior remains explicit demonstration mode:

```sh
cd backend
.venv/bin/python run_secure.py --demo
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

No hosted variables should be exported locally. For a local production preview use `WORKPAPER_LOCAL_BUILD=1 npm run build -- --webpack` and the same setting for `npm start`; that escape hatch is not honored as a hosted deployment override.

Verification commands:

```sh
cd backend
.venv/bin/python -m pytest -q
```

```sh
cd frontend
npm run test:deployment-config
npm run test:e2e
npm run test:e2e -- --config=playwright.workflow.config.ts
npm run test:deployment
npx tsc --noEmit
npm run lint
WORKPAPER_HOSTED=1 NEXT_PUBLIC_API_URL= WORKPAPER_BACKEND_ORIGIN=https://review-only.onrender.com WORKPAPER_PUBLIC_ORIGIN=https://workpaper.example.test npm run build -- --webpack
```

The placeholder build verifies configuration only; it does not create or contact a hosting account. See the readiness report for measured results and remaining manual gates.
