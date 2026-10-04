import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.PDTT_API_ORIGIN || "http://127.0.0.1:8001"}/api/:path*` }];
  },
};

export default nextConfig;
