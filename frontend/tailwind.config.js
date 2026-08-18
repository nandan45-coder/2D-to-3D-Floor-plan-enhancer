/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Drafting table" palette -- grounded in the blueprint/architectural
        // subject matter of the product rather than a generic UI default.
        ink: {
          DEFAULT: "#0F2942", // primary chrome / sidebar background
          light: "#1B3A5C",
          dark: "#081826",
        },
        blueprint: {
          DEFAULT: "#4FB6E8", // linework cyan -- accents, active states, focus rings
          soft: "#BFE6F7",
        },
        paper: {
          DEFAULT: "#F5F7FA", // main content background (cool, not cream)
          panel: "#FFFFFF",
        },
        graphite: {
          DEFAULT: "#1C2530", // primary text
          muted: "#5B6675",   // secondary text
          faint: "#94A0AF",   // tertiary / placeholder text
        },
        redline: {
          DEFAULT: "#D8483F", // correction-mark red -- used for errors/destructive actions
          soft: "#F6DEDC",
        },
        approved: {
          DEFAULT: "#0FA37F", // stamp-green -- used for success states
          soft: "#D8F3EA",
        },
      },
      fontFamily: {
        display: ["\"Space Grotesk\"", "system-ui", "sans-serif"],
        body: ["\"Inter\"", "system-ui", "sans-serif"],
        mono: ["\"IBM Plex Mono\"", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15, 41, 66, 0.06), 0 1px 8px rgba(15, 41, 66, 0.04)",
      },
    },
  },
  plugins: [],
};
