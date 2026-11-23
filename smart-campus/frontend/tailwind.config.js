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
        // Refined additions — barely-there inner highlight + soft resting lift.
        soft: "0 1px 2px rgba(33,20,91,0.05), 0 4px 12px rgba(33,20,91,0.04)",
        inner: "inset 0 1px 0 0 rgba(255,255,255,0.6)",
        ring: "0 0 0 4px rgba(96,65,200,0.12)",
      },
      borderRadius: { xl: "1rem", "2xl": "1.25rem", "3xl": "1.5rem" },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #21145B 0%, #301078 50%, #6041C8 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, #6041C8 0%, #301078 100%)",
        "navy-gradient": "linear-gradient(180deg, #21145B 0%, #1A0F47 100%)",
        // Barely-there app-canvas mesh — adds depth without distracting from content.
        "app-mesh":
          "radial-gradient(60rem 60rem at 100% -10%, rgba(96,65,200,0.06), transparent 60%)," +
          "radial-gradient(50rem 50rem at -10% 110%, rgba(24,168,121,0.05), transparent 55%)",
        // Shimmer sweep for refined skeleton loaders.
        "shimmer":
          "linear-gradient(90deg, rgba(232,232,240,0) 0%, rgba(255,255,255,0.65) 50%, rgba(232,232,240,0) 100%)",
      },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        // Gradient sweep across a skeleton block — repeats.
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        // Gentle float for decorative hero orbs.
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        // Soft pulsing ring for the notification dot.
        pulseRing: { "0%": { transform: "scale(0.9)", opacity: "0.7" }, "70%": { transform: "scale(2.2)", opacity: "0" }, "100%": { transform: "scale(2.2)", opacity: "0" } },
        scaleIn: { from: { opacity: "0", transform: "scale(0.96)" }, to: { opacity: "1", transform: "scale(1)" } },
      },
      animation: {
        fadeIn: "fadeIn 150ms ease-out",
        slideUp: "slideUp 200ms ease-out",
        shimmer: "shimmer 1.8s linear infinite",
        float: "float 7s ease-in-out infinite",
        pulseRing: "pulseRing 2.4s cubic-bezier(0.4,0,0.6,1) infinite",
        scaleIn: "scaleIn 180ms cubic-bezier(0.16,1,0.3,1)",
      },
    },
  },
  plugins: [],
};
