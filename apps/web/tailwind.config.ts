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
        ink: "#0A0E14",
        paper: "#10151C",
        panel: "#161D27",
        line: "#243040",
        brass: "#C4A574",
        ledger: "#7D9B78",
        mute: "#8B93A0",
        ivory: "#E8E4DC",
        alert: "#C47B6A",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        desk: "0 24px 80px rgba(0,0,0,0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
