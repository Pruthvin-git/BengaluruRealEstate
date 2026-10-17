import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Nested inside a multi-project workspace that already has its own agent router.
  agentRules: false,
};
export default nextConfig;
