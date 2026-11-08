/** Public fictional-data demo only. Secure and assignment hosting configurations are separate. */
export function publicHostingConfig(env = process.env) {
  if (
    env.WORKPAPER_PROFILE !== "public-demo" ||
    env.WORKPAPER_HOSTED ||
    env.NEXT_PUBLIC_PUBLIC_DEMO !== "1" ||
    env.NEXT_PUBLIC_API_URL !== ""
  )
    throw new Error(
      "Explicit public-demo profile and same-origin API required",
    );
  let frontend, backend;
  try {
    frontend = new URL(env.WORKPAPER_PUBLIC_ORIGIN);
    backend = new URL(env.WORKPAPER_BACKEND_ORIGIN);
  } catch {
    throw new Error("Public demo frontend and backend origins required");
  }
  const clean = (u) =>
    !u.username && !u.password && u.pathname === "/" && !u.search && !u.hash;
  const isolated =
    env.WORKPAPER_ENV === "test" &&
    env.WORKPAPER_PUBLIC_TEST === "1" &&
    !env.VERCEL &&
    frontend.origin === "https://localhost:3300" &&
    backend.origin === "http://127.0.0.1:8300" &&
    clean(frontend) &&
    clean(backend);
  if (
    !isolated &&
    (!clean(frontend) ||
      frontend.protocol !== "https:" ||
      frontend.port ||
      !/^[a-z0-9-]+\.vercel\.app$/.test(frontend.hostname) ||
      !clean(backend) ||
      backend.protocol !== "https:" ||
      backend.port ||
      !/^[a-z0-9-]+\.onrender\.com$/.test(backend.hostname))
  )
    throw new Error(
      "Public demo requires exact HTTPS Vercel and Render origins",
    );
  return {
    hosted: true,
    rewrites: [
      { source: "/api/:path*", destination: backend.origin + "/api/:path*" },
    ],
    redirects: isolated
      ? []
      : [
          {
            source: "/:path*",
            missing: [
              {
                type: "host",
                value: frontend.hostname.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
              },
            ],
            destination: frontend.origin + "/:path*",
            permanent: false,
          },
        ],
  };
}
