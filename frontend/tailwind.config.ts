import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Gaming dark theme palette
        surface: {
          DEFAULT: "#0a0a0f",
          secondary: "#12121a",
          tertiary: "#1a1a25",
          hover: "#252535",
        },
        // Neon cyan - primary accent
        neon: {
          cyan: "#00fff2",
          cyanDark: "#00d4c8",
          cyanGlow: "rgba(0, 255, 242, 0.3)",
        },
        // Neon magenta - secondary accent
        magenta: {
          DEFAULT: "#ff00ff",
          dark: "#cc00cc",
          glow: "rgba(255, 0, 255, 0.3)",
        },
        // Purple accent
        purple: {
          neon: "#8b5cf6",
          dark: "#7c3aed",
          glow: "rgba(139, 92, 246, 0.3)",
        },
        // Text colors
        text: {
          primary: "#f0f0f5",
          secondary: "#9999aa",
          muted: "#666677",
        },
        // Gaming gradients will use these
        gaming: {
          start: "#00fff2",
          mid: "#8b5cf6",
          end: "#ff00ff",
        },
      },
      fontFamily: {
        display: ["var(--font-space-grotesk)", "system-ui", "sans-serif"],
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      backgroundImage: {
        "gaming-gradient": "linear-gradient(135deg, #00fff2 0%, #8b5cf6 50%, #ff00ff 100%)",
        "gaming-gradient-subtle": "linear-gradient(135deg, rgba(0,255,242,0.1) 0%, rgba(139,92,246,0.1) 50%, rgba(255,0,255,0.1) 100%)",
        "cyber-grid": `
          linear-gradient(rgba(0,255,242,0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(0,255,242,0.03) 1px, transparent 1px)
        `,
      },
      boxShadow: {
        "neon-cyan": "0 0 20px rgba(0, 255, 242, 0.4), 0 0 40px rgba(0, 255, 242, 0.2)",
        "neon-magenta": "0 0 20px rgba(255, 0, 255, 0.4), 0 0 40px rgba(255, 0, 255, 0.2)",
        "neon-purple": "0 0 20px rgba(139, 92, 246, 0.4), 0 0 40px rgba(139, 92, 246, 0.2)",
        "inner-glow": "inset 0 0 20px rgba(0, 255, 242, 0.1)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "glow": "glow 2s ease-in-out infinite alternate",
        "gradient-shift": "gradientShift 8s ease infinite",
      },
      keyframes: {
        glow: {
          "0%": { boxShadow: "0 0 20px rgba(0, 255, 242, 0.4)" },
          "100%": { boxShadow: "0 0 30px rgba(0, 255, 242, 0.6), 0 0 60px rgba(0, 255, 242, 0.3)" },
        },
        gradientShift: {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
