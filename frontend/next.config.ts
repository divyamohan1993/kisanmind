import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  async redirects() {
    return [
      { source: "/", destination: "/talk", permanent: true },
      { source: "/demo", destination: "/talk", permanent: true },
      { source: "/mandi", destination: "/talk", permanent: true },
      { source: "/weather", destination: "/talk", permanent: true },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8081/api/:path*",
      },
    ];
  },
};

export default nextConfig;
