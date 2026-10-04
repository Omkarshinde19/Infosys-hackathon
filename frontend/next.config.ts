import type { NextConfig } from "next";

const gateway = process.env.GATEWAY_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Proxy REST calls to the FastAPI gateway so the browser never needs CORS.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${gateway}/:path*` }];
  },
};

export default nextConfig;
