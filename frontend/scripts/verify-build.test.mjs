import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  readdirSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, relative } from "node:path";
import ts from "typescript";
import { verifyBuild } from "./verify-build.mjs";
const frontend = resolve(import.meta.dirname, "..");
const env = {
  WORKPAPER_PROFILE: "public-demo",
  NEXT_PUBLIC_PUBLIC_DEMO: "1",
  NEXT_PUBLIC_API_URL: "",
  WORKPAPER_PUBLIC_ORIGIN: "https://demo.vercel.app",
  WORKPAPER_BACKEND_ORIGIN: "https://demo.onrender.com",
};
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "miraflores-artifact-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const dir of ["static/chunks", "server/app"])
    mkdirSync(join(root, dir), { recursive: true });
  writeFileSync(join(root, "BUILD_ID"), "isolated-test-build");
  writeFileSync(join(root, "build-manifest.json"), "{}");
  writeFileSync(
    join(root, "routes-manifest.json"),
    JSON.stringify({
      rewrites: {
        afterFiles: [
          {
            source: "/api/:path*",
            destination: "https://demo.onrender.com/api/:path*",
          },
        ],
      },
    }),
  );
  writeFileSync(
    join(root, "static/chunks/page.js"),
    'fetch("/api/workflow/notes");',
  );
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html>PUBLIC FICTIONAL DEMO<script src="/_next/static/chunks/page.js"></script></html>',
  );
  return root;
}
test("valid Next.js public artifact uses the one existing FastAPI rewrite", (t) =>
  assert.equal(verifyBuild(fixture(t), env).browserAssets, 1));
for (const signature of [
  "https://wrong.supabase.co/rest/v1/review_notes",
  "@supabase/supabase-js",
  "audit_log",
  "import.meta.env.VITE_URL",
  "/@vite/client",
  "vite.svg",
])
  test("build rejects legacy signature " + signature, (t) => {
    const root = fixture(t);
    writeFileSync(join(root, "static/chunks/page.js"), signature);
    assert.throws(() => verifyBuild(root, env), /Unexpected/);
  });
test("Vite-only output cannot pass as Next.js", (t) => {
  const root = fixture(t);
  rmSync(join(root, "BUILD_ID"));
  assert.throws(() => verifyBuild(root, env), /Next.js output/);
});
test("missing or wrong API rewrite fails the production gate", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "routes-manifest.json"),
    JSON.stringify({ rewrites: [] }),
  );
  assert.throws(() => verifyBuild(root, env), /FastAPI/);
  writeFileSync(
    join(root, "routes-manifest.json"),
    JSON.stringify({
      rewrites: [
        {
          source: "/api/:path*",
          destination: "https://wrong.onrender.com/api/:path*",
        },
      ],
    }),
  );
  assert.throws(() => verifyBuild(root, env), /FastAPI/);
});
test("legacy root HTML is rejected even with superficially valid Next.js metadata", (t) => {
  const root = fixture(t);
  writeFileSync(join(root, "server/app/index.html"), '<div id="root"></div>');
  assert.throws(() => verifyBuild(root, env), /root page/);
});
test("Git auto-deployment is not disabled and the production build always verifies artifacts", () => {
  const config = JSON.parse(
    readFileSync(join(frontend, "vercel.json"), "utf8"),
  );
  const pkg = JSON.parse(readFileSync(join(frontend, "package.json"), "utf8"));
  assert.equal(config.git?.deploymentEnabled, undefined);
  assert.equal(config.github?.enabled, undefined);
  assert.equal(config.framework, "nextjs");
  assert.equal(config.installCommand, "npm ci");
  assert.equal(config.buildCommand, "npm run build -- --webpack");
  assert.equal(config.outputDirectory, undefined);
  assert.equal(pkg.scripts.build, "next build");
  assert.equal(pkg.scripts.postbuild, "node scripts/verify-build.mjs");
  assert.ok(
    !Object.keys({ ...pkg.dependencies, ...pkg.devDependencies }).some((p) =>
      /supabase|axios|^vite$/.test(p),
    ),
  );
});
function sources(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory()
      ? sources(join(root, e.name))
      : /\.(tsx?|jsx?)$/.test(e.name)
        ? [join(root, e.name)]
        : [],
  );
}
test("all browser network calls use the shared FastAPI session client; no third-party SDKs or endpoints", () => {
  const direct = [];
  for (const file of sources(join(frontend, "src"))) {
    const content = readFileSync(file, "utf8");
    assert.doesNotMatch(
      content,
      /supabase|\breview_notes\b|\baudit_log\b|\baxios\b|\bcreateClient\b/i,
      file,
    );
    const source = ts.createSourceFile(
      file,
      content,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    function visit(node) {
      if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        node.expression.text === "fetch"
      )
        direct.push(relative(frontend, file));
      if (ts.isNewExpression(node))
        assert.ok(
          !["XMLHttpRequest", "WebSocket", "EventSource"].includes(
            node.expression.getText(source),
          ),
          file,
        );
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
  assert.deepEqual(direct, ["src/components/session.tsx"]);
  const config = readFileSync(join(frontend, "src/lib/api-config.ts"), "utf8");
  assert.match(config, /NEXT_PUBLIC_API_URL/);
});

test("public indicator may be in a root-linked Client Component instead of the prerendered shell", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html><div>Loading…</div><script defer src="/_next/static/chunks/page.js?dpl=fixture"></script></html>',
  );
  writeFileSync(
    join(root, "static/chunks/page.js"),
    'document.body.textContent="PUBLIC FICTIONAL DEMO";',
  );
  assert.equal(verifyBuild(root, env).browserAssets, 1);
});

test("HTML text boundaries and encoded whitespace do not hide the public indicator", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html><p>PUBLIC<!-- boundary --> <span>FICTIONAL</span>&nbsp;DEMO</p><script src="/_next/static/chunks/page.js"></script></html>',
  );
  assert.equal(verifyBuild(root, env).browserAssets, 1);
});

test("missing public indicator still fails even with correct config and Next.js assets", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html>Loading<script src="/_next/static/chunks/page.js"></script></html>',
  );
  assert.throws(
    () => verifyBuild(root, env),
    /demonstration indicator is missing/,
  );
  writeFileSync(
    join(root, "static/chunks/unrelated-page.js"),
    '"PUBLIC FICTIONAL DEMO";',
  );
  assert.throws(
    () => verifyBuild(root, env),
    /demonstration indicator is missing/,
  );
});

test("missing root HTML has its own precise diagnostic", (t) => {
  const root = fixture(t);
  rmSync(join(root, "server/app/index.html"));
  assert.throws(
    () => verifyBuild(root, env),
    /root page is missing: server\/app\/index.html/,
  );
});

for (const name of [
  "NEXT_PUBLIC_PUBLIC_DEMO",
  "NEXT_PUBLIC_API_URL",
  "WORKPAPER_PUBLIC_ORIGIN",
  "WORKPAPER_BACKEND_ORIGIN",
]) {
  test("public build still rejects missing configuration " + name, (t) => {
    const root = fixture(t);
    assert.throws(() => verifyBuild(root, { ...env, [name]: undefined }));
  });
}

test("public indicator cannot excuse Supabase in a referenced script", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html>Loading<script src="/_next/static/chunks/page.js"></script></html>',
  );
  writeFileSync(
    join(root, "static/chunks/page.js"),
    '"PUBLIC FICTIONAL DEMO"; "https://wrong.supabase.co";',
  );
  assert.throws(() => verifyBuild(root, env), /Unexpected Supabase/);
});
