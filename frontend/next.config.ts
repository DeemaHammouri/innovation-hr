import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Plain client-rendered app behind a login: no cache components or partial prefetching needed.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
