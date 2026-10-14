/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        studio: {
          bg: "#0a0e14",
          panel: "#10161f",
          panel2: "#141c27",
          border: "#1e2a3a",
          text: "#e6edf3",
          muted: "#8b98a9",
          faint: "#5b6a7d",
        },
        accent: {
          DEFAULT: "#22d3ee",
          dim: "#0e7490",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
