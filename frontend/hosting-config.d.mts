export function hostingConfig(env?: Record<string, string | undefined>): {
  hosted: boolean;
  rewrites: { source: string; destination: string }[];
  redirects: {
    source: string;
    missing: { type: "host"; value: string }[];
    destination: string;
    permanent: boolean;
  }[];
};
