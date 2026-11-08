/** Explicitly separate disposable assignment hosting; no changes to secure hosted policy. */
export function assignmentHostingConfig(env = process.env) {
  if (
    env.WORKPAPER_PROFILE !== "assignment-demo" ||
    env.WORKPAPER_HOSTED ||
    env.NEXT_PUBLIC_ASSIGNMENT_DEMO !== "1" ||
    env.NEXT_PUBLIC_API_URL !== ""
  )
    throw new Error("Explicit non-production assignment settings required");
  let origin, target;
  try {
    origin = new URL(env.WORKPAPER_PUBLIC_ORIGIN);
    target = new URL(env.WORKPAPER_BACKEND_ORIGIN);
  } catch {
    throw new Error("Assignment frontend and backend origins required");
  }
  const clean = (u) =>
    !u.username && !u.password && u.pathname === "/" && !u.search && !u.hash;
  const isolated =
    !env.VERCEL &&
    !env.WORKPAPER_HOSTED &&
    env.WORKPAPER_ENV === "test" &&
    env.WORKPAPER_ASSIGNMENT_TEST === "1" &&
    origin.origin === "https://localhost:3300" &&
    target.origin === "http://127.0.0.1:8300" &&
    clean(origin) &&
    clean(target);
  if (isolated)
    return {
      hosted: true,
      rewrites: [
        { source: "/api/:path*", destination: target.origin + "/api/:path*" },
      ],
      redirects: [],
    };
  const tunnel = env.WORKPAPER_ASSIGNMENT_TUNNEL === "1" && !env.VERCEL;
  if (
    !tunnel &&
    env.WORKPAPER_ASSIGNMENT_VERCEL_ELIGIBILITY !==
      "personal-noncommercial-confirmed"
  )
    throw new Error(
      "Vercel Hobby eligibility must be explicitly confirmed; otherwise use the scheduled local tunnel",
    );
  if (
    !clean(origin) ||
    origin.protocol !== "https:" ||
    origin.port ||
    !(
      tunnel ? /^[a-z0-9-]+\.trycloudflare\.com$/ : /^[a-z0-9-]+\.vercel\.app$/
    ).test(origin.hostname)
  )
    throw new Error(
      "Assignment requires an exact free HTTPS application hostname",
    );
  if (
    !clean(target) ||
    (tunnel
      ? target.origin !== "http://127.0.0.1:8000"
      : target.protocol !== "https:" ||
        target.port ||
        !/^[a-z0-9-]+\.onrender\.com$/.test(target.hostname))
  )
    throw new Error(
      "Assignment API destination must be the configured Render service or explicit local tunnel backend",
    );
  return {
    hosted: true,
    rewrites: [
      { source: "/api/:path*", destination: target.origin + "/api/:path*" },
    ],
    redirects: [
      {
        source: "/:path*",
        missing: [
          {
            type: "host",
            value: origin.hostname.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
          },
        ],
        destination: origin.origin + "/:path*",
        permanent: false,
      },
    ],
  };
}
