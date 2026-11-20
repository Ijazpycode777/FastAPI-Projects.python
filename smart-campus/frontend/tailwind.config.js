/** @type {import('tailwindcss').Config} */
// Spec palette (Part 11.2). Tokens are repointed in place so existing utility
// classes (bg-navy, text-indigo, bg-teal, …) propagate the new colours everywhere.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Primary dark blue — sidebar, attendance "present", brand accents.
        navy: { DEFAULT: "#163A70", soft: "#1F2937" },
        // Primary blue — buttons, active nav, links, focus ring.
        indigo: { DEFAULT: "#2457A6", soft: "#3B6FB5", dark: "#1F4A8A" },
        // Success
        teal: { DEFAULT: "#23865B", soft: "#2BA06E" },
        // Warning
        amber: { DEFAULT: "#D99A27", soft: "#E6B24A" },
        // Error / danger
        rose: { DEFAULT: "#D64545", soft: "#E06A6A" },
        // Neutrals
        slate: { bg: "#F5F7FA", card: "#FFFFFF", border: "#E4E7EC", muted: "#667085" },
        // Main text (near-black)
        ink: { DEFAULT: "#1F2937" },
        // Light blue surface
        lightblue: { DEFAULT: "#EAF1FA" },
        // Neutral grey — leave / inactive (attendance "leave" segment)
        neutral: { DEFAULT: "#9AA3AF" },
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
