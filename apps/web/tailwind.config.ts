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
        ink: "#0C0D0F",
        paper: "#121317",
        panel: "#17181D",
        line: "#2A2C33",
        brass: "#B89A6A",
        ledger: "#7A9478",
        mute: "#8B8E96",
        ivory: "#E7E4DC",
        alert: "#C17A6C",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        lg: "8px",
        xl: "10px",
        "2xl": "12px",
      },
      boxShadow: {
        desk: "none",
      },
      spacing: {
        18: "4.5rem",
      },
    },
  },
  plugins: [],
};

export default config;
