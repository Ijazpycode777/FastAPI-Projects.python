/** @type {import('tailwindcss').Config} */
// Premium ERP palette — navy→deep-purple primary identity, lavender canvas,
// hairline borders, soft diffuse elevation. Aligned to the Smart Campus design
// spec: navy #21145B / deep purple #301078 / accent #6041C8 / lavender #F0EDFC.
// Token keys are kept stable so existing utilities (bg-navy, text-indigo, …)
// propagate the new colours everywhere without touching call sites.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark navy — sidebar surface, primary brand, attendance "present" brand.
        navy: { DEFAULT: "#21145B", soft: "#2A1A6B", deep: "#1A0F47" },
        // Primary accent — buttons, active nav, links, focus ring.
        indigo: { DEFAULT: "#6041C8", soft: "#7C5BD8", dark: "#301078" },
        // Deep purple — gradient end, premium highlights.
        violet: { DEFAULT: "#301078", soft: "#4A2A9A" },
        // Success
        teal: { DEFAULT: "#18A879", soft: "#2BC494" },
        // Warning
        amber: { DEFAULT: "#E8A23A", soft: "#F0B85A" },
        // Error / danger
        rose: { DEFAULT: "#E05262", soft: "#E9707E" },
        // Info
        blue: { DEFAULT: "#3999D6", soft: "#5DB0DF" },
        // Neutrals — cool lavender-tinted canvas, hairline borders.
        slate: {
          bg: "#F6F7FC", card: "#FFFFFF", border: "#E8E8F0",
          hairline: "#EEF0F7", muted: "#73758A", faint: "#9CA0B5",
        },
        // Main text — near-black navy.
        ink: { DEFAULT: "#202033" },
        // Light lavender surface (tints, focus wells, soft highlights).
        lightblue: { DEFAULT: "#F0EDFC" },
        // Neutral grey — leave / inactive (attendance "leave" segment).
        neutral: { DEFAULT: "#9CA0B5" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Helvetica", "Arial"],
      },
      boxShadow: {
        // Soft, diffuse elevation — the premium SaaS card lift.
        card: "0 1px 2px rgba(33,20,91,0.04), 0 8px 24px rgba(33,20,91,0.06)",
        pop: "0 12px 32px -8px rgba(33,20,91,0.18), 0 8px 16px -10px rgba(33,20,91,0.10)",
        glow: "0 8px 24px -6px rgba(96,65,200,0.45)",
      },
      borderRadius: { xl: "1rem", "2xl": "1.25rem", "3xl": "1.5rem" },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #21145B 0%, #301078 50%, #6041C8 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, #6041C8 0%, #301078 100%)",
        "navy-gradient": "linear-gradient(180deg, #21145B 0%, #1A0F47 100%)",
      },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { fadeIn: "fadeIn 150ms ease-out", slideUp: "slideUp 200ms ease-out" },
    },
  },
  plugins: [],
};
