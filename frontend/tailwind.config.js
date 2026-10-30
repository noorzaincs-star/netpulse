/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#08111f",
        panel: "#111d2d",
        line: "#233349",
        accent: "#48d6b5",
      },
    },
  },
  plugins: [],
};
