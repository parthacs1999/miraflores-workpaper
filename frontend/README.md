This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

Start the FastAPI backend first, in a separate terminal from the repository root:

```bash
cd backend
.venv/bin/python run_secure.py --demo
```

`--demo` explicitly enables **local development** staff selection (Priya, Daniel,
Helen). It is not authentication, a legal signature or real filing. The server
binds to `127.0.0.1:8000`. The ordinary `uvicorn app.main:app` launch deliberately
defaults to locked mode; it does not configure a session provider. Stop an old
server using port 8000 before starting the demo launcher. Explicit production or
conflicting security environment settings are rejected by `--demo`.

The existing database is retained and migrations are additive. To use a separate
demo database instead, prefix the command with
`REVIEW_DB_PATH=/private/tmp/miraflores-local-demo.db`.

Then, from `frontend`, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

Use **localhost for both browser and API**. The frontend's `.env.local` should
contain `NEXT_PUBLIC_API_URL=http://localhost:8000`; restart Next.js if it changes
(production builds capture this value at build time). The backend allows
`http://localhost:3000` by default. For a different frontend port, explicitly set
`WORKPAPER_ORIGINS` to that exact origin when launching the backend. Mixing
`localhost` and `127.0.0.1` across browser/API hosts can prevent SameSite cookies
from working. Cookie credentials, CSRF and Origin validation remain mandatory.

The login panel reports a locked/misconfigured/unreachable backend with the API
URL and a retry action. Select a staff identity and click **Start / switch
session** only after initialization succeeds. Credential/production mode must be
configured separately; this demo flag cannot override production settings.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
