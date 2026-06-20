/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0A0C0F",
          900: "#0F1318",
          800: "#161B22",
          700: "#1E2530",
          600: "#2A3340",
          500: "#3D4A5C",
        },
        paper: {
          100: "#F4F1E8",
          200: "#E8E2D2",
        },
        amber: {
          400: "#E8A23D",
          500: "#D4881F",
        },
        verdict: {
          supported: "#4DD0A7",
          contradicted: "#E85D5D",
          pending: "#E8A23D",
        },
        cyan: {
          400: "#4DD0E1",
        },
      },
      fontFamily: {
        display: ["Georgia", "Cambria", "Times New Roman", "serif"],
        mono: ["SF Mono", "Roboto Mono", "Consolas", "monospace"],
        sans: ["-apple-system", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"],
      },
      backgroundImage: {
        "grain": "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.04) 1px, transparent 0)",
      },
      keyframes: {
        scanline: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        pulseRing: {
          "0%": { boxShadow: "0 0 0 0 rgba(232,162,61,0.4)" },
          "70%": { boxShadow: "0 0 0 10px rgba(232,162,61,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(232,162,61,0)" },
        },
      },
      animation: {
        scanline: "scanline 3s linear infinite",
        pulseRing: "pulseRing 2s infinite",
      },
    },
  },
  plugins: [],
}
