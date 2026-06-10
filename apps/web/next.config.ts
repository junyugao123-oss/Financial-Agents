import type { NextConfig } from "next";

const apiProxyTarget =
  process.env.API_PROXY_TARGET?.replace(/\/$/, "") ?? "http://localhost:8000";

const allowedDevOrigins = (
  process.env.NEXT_ALLOWED_DEV_ORIGINS ?? "192.168.1.56,127.0.0.1,localhost"
)
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  allowedDevOrigins,
  devIndicators: false,
  output: "standalone",
  async rewrites() {
    return [
      {
        destination: `${apiProxyTarget}/:path*`,
        source: "/api/:path*",
      },
    ];
  },
};

export default nextConfig;
