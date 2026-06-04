import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        destination: "http://localhost:8000/:path*",
        source: "/api/:path*",
      },
    ];
  },
};

export default nextConfig;
