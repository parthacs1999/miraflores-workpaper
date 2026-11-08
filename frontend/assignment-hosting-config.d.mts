export function assignmentHostingConfig(env?: NodeJS.ProcessEnv): {
  hosted: boolean;
  rewrites: { source: string; destination: string }[];
  redirects: {
    source: string;
    missing: { type: "host"; value: string }[];
    destination: string;
    permanent: boolean;
  }[];
};
