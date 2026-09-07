import type { NextConfig } from "next";

const configuredBackend = process.env.DJANGO_API_ORIGIN?.trim();
if (process.env.VERCEL && !configuredBackend) {
  throw new Error("Set DJANGO_API_ORIGIN to your Render HTTPS origin in Vercel before building.");
}
const backendUrl = new URL(configuredBackend || "http://127.0.0.1:8000");
if (backendUrl.username || backendUrl.password || backendUrl.search || backendUrl.hash || backendUrl.pathname !== "/") {
  throw new Error("DJANGO_API_ORIGIN must be an origin only, without credentials, /api, or a query.");
}
if (!["http:", "https:"].includes(backendUrl.protocol) ||
    (process.env.VERCEL && (backendUrl.protocol !== "https:" || ["localhost", "127.0.0.1", "[::1]"].includes(backendUrl.hostname)))) {
  throw new Error("Vercel requires a public HTTPS Django backend, not localhost.");
}
const backend = backendUrl.origin;
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
