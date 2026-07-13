import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async redirects() {
    return [
      // P2 has no login screen of its own — the shared (auth)/login page
      // serves enterprise users. These are the addresses people type or
      // legacy code links to (the old P2 logout pointed at /p2/auth/login).
      { source: "/p2/login", destination: "/login", permanent: false },
      { source: "/p2/auth/login", destination: "/login", permanent: false },
    ];
  },
};

export default nextConfig;
