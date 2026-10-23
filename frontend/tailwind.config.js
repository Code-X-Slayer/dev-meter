/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#090d1a",
        panel: "#10172a",
        violet: "#8b7cf6",
      },
    },
  },
  plugins: [],
};
