import type { Config } from "tailwindcss";

/**
 * VIP Network: navy + gold from the logo and the approved mock. Semantic names map to the CSS
 * variables in src/styles/tokens.css (light and dark values).
 */
export default {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { 950: "#070F1F", 900: "#0B1630", 800: "#12213F", 700: "#1B2D52" },
        gold: { DEFAULT: "#C9A14A", hi: "#E8CB82", lo: "#9C7428", ink: "var(--gold-ink)" },
        canvas: "var(--bg)",
        surface: { DEFAULT: "var(--surface)", 2: "var(--surface-2)" },
        line: { DEFAULT: "var(--line)", 2: "var(--line-2)" },
        ink: { DEFAULT: "var(--fg)", 2: "var(--fg-2)", muted: "var(--muted)" },
        buy: { DEFAULT: "var(--buy)", bg: "var(--buy-bg)" },
        sell: { DEFAULT: "var(--sell)", bg: "var(--sell-bg)" },
        part: { DEFAULT: "var(--part)", bg: "var(--part-bg)" },
        net: { DEFAULT: "var(--net)", bg: "var(--net-bg)" },
        ok: { DEFAULT: "var(--ok)" },
        warn: { DEFAULT: "var(--warn)", bg: "var(--warn-bg)" },
        bad: { DEFAULT: "var(--bad)", bg: "var(--bad-bg)" },
      },
      fontFamily: {
        display: ["Montserrat", "Segoe UI", "system-ui", "sans-serif"],
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
      },
      maxWidth: { site: "1200px" },
      borderRadius: { card: "18px", control: "10px" },
      boxShadow: {
        sm2: "0 1px 2px rgba(14,25,48,.06), 0 1px 1px rgba(14,25,48,.04)",
        md2: "0 8px 24px rgba(14,25,48,.10), 0 2px 6px rgba(14,25,48,.06)",
        lg2: "0 24px 60px rgba(7,15,31,.28)",
        gold: "0 4px 14px rgba(201,161,74,.35)",
      },
      backgroundImage: {
        "gold-grad": "linear-gradient(135deg,#E8CB82 0%,#C9A14A 45%,#A87C2F 100%)",
      },
      keyframes: {
        pop: { from: { transform: "scale(.96)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
        slide: { from: { transform: "translateX(40px)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
      },
      animation: { pop: "pop .22s ease-out", slide: "slide .25s ease-out" },
    },
  },
  plugins: [],
} satisfies Config;
