/** @type {import('tailwindcss').Config} */
// Premium ERP palette — dark navy sidebar, indigo→violet primary, bright SaaS
// accents, cool-gray canvas, hairline borders, soft diffuse elevation.
// Token keys are kept stable so existing utilities (bg-navy, text-indigo, …)
// propagate the new colours everywhere without touching call sites.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark navy — sidebar surface + attendance "present" brand.
        navy: { DEFAULT: "#171E30", soft: "#1E2640", deep: "#121726" },
        // Primary indigo→violet — buttons, active nav, links, focus ring.
        indigo: { DEFAULT: "#4F46E5", soft: "#6D5DF6", dark: "#4338CA" },
        // Violet accent (gradient end, premium highlights).
        violet: { DEFAULT: "#7C3AED", soft: "#8B5CF6" },
        // Success
        teal: { DEFAULT: "#10B981", soft: "#34D399" },
        // Warning
        amber: { DEFAULT: "#F59E0B", soft: "#FBBF24" },
        // Error / danger
        rose: { DEFAULT: "#EF4444", soft: "#F87171" },
        // Info
        blue: { DEFAULT: "#3B82F6", soft: "#60A5FA" },
        // Neutrals — cool gray canvas, hairline borders.
        slate: {
          bg: "#F4F6FB", card: "#FFFFFF", border: "#E9EDF5",
          hairline: "#EEF1F7", muted: "#6B7280", faint: "#9CA3AF",
        },
        // Main text — near-black navy.
        ink: { DEFAULT: "#1E2233" },
        // Light indigo surface (tints, focus wells).
        lightblue: { DEFAULT: "#EEF2FF" },
        // Neutral grey — leave / inactive (attendance "leave" segment).
        neutral: { DEFAULT: "#9CA3AF" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Helvetica", "Arial"],
      },
      boxShadow: {
        // Soft, diffuse elevation — the premium SaaS card lift.
        card: "0 1px 2px rgba(23,30,60,0.04), 0 8px 24px rgba(23,30,60,0.06)",
        pop: "0 12px 32px -8px rgba(23,30,60,0.18), 0 8px 16px -10px rgba(23,30,60,0.10)",
        glow: "0 8px 24px -6px rgba(79,70,229,0.45)",
      },
      borderRadius: { xl: "1rem", "2xl": "1.25rem", "3xl": "1.5rem" },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, #6D5DF6 0%, #8B5CF6 100%)",
        "navy-gradient": "linear-gradient(180deg, #171E30 0%, #121726 100%)",
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
