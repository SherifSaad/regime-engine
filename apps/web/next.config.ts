import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    root: __dirname,
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "logo.twelvedata.com", pathname: "/**" },
      { protocol: "https", hostname: "api.twelvedata.com", pathname: "/**" },
    ],
  },
};

export default nextConfig;
