import type { NextConfig } from "next";
import path from "node:path";

// `output: "export"` produces a fully static bundle in `apps/web/out/` that
// the FastAPI backend can serve directly. This is what the Windows installer
// uses — one Python process, no Node.js runtime needed.
//
// Toggle with NEXT_OUTPUT=export at build time; otherwise we keep the default
// (Node-based) output for `npm run dev` and Docker.
const exportMode = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname, "../../"),
  ...(exportMode
    ? {
        output: "export",
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {}),
};

export default nextConfig;
