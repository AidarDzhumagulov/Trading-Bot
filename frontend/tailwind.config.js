/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'trading-green': '#10b981',
        'trading-red': '#ef4444',
      }
    },
  },
  plugins: [],
}
