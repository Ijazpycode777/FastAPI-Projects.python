/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#172554", soft: "#1e293b" },
        indigo: { DEFAULT: "#4F46E5", soft: "#6366F1", dark: "#4338CA" },
        teal: { DEFAULT: "#0D9488", soft: "#14B8A6" },
        amber: { DEFAULT: "#F59E0B", soft: "#FBBF24" },
        rose: { DEFAULT: "#E11D48", soft: "#F43F5E" },
        slate: { bg: "#F1F5F9", card: "#FFFFFF", border: "#E2E8F0", muted: "#64748B" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Helvetica", "Arial"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(15,23,42,0.04), 0 1px 3px 0 rgba(15,23,42,0.06)",
        pop: "0 10px 25px -5px rgba(15,23,42,0.10), 0 8px 10px -6px rgba(15,23,42,0.08)",
      },
      borderRadius: { xl: "0.875rem", "2xl": "1.25rem" },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { fadeIn: "fadeIn 150ms ease-out", slideUp: "slideUp 200ms ease-out" },
    },
  },
  plugins: [],
};
