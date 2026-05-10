import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#17201b",
        paper: "#f7f6f1",
        staff: "#2f5d50",
        rosin: "#b86b42",
        reed: "#d7b56d",
      },
      boxShadow: {
        soft: "0 18px 50px rgba(23, 32, 27, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
