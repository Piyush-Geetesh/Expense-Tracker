import type { NextConfig } from "next";

const backend = (process.env.DJANGO_API_ORIGIN || "http://127.0.0.1:8000").replace(/\/$/, "");
const config: NextConfig = {
  poweredByHeader: false,
  // Preserve Django's slash-terminated API endpoints, including DELETE/POST.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*/` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "same-origin" },
        { key: "X-Frame-Options", value: "DENY" },
      ],
    }];
  },
};
export default config;
