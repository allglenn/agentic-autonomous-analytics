import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: "#111111",
          "bg-deep": "#0D0D0D",
          card: "#161616",
          border: "#1E1E1E",
          "border-light": "#2A2A2A",
          accent: "#1A56DB",
          text: "#E5E7EB",
          muted: "#6B7280",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
