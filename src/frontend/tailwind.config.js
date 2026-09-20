/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f4f8',
          100: '#d9e2ec',
          200: '#bcccdc',
          300: '#9fb3c8',
          400: '#829ab1',
          500: '#627d98',
          600: '#486581',
          700: '#334e68',
          800: '#243b53',
          900: '#1F3B63', // Primary brand color
        },
        tier: {
          standard: '#10B981', // green-500
          ia: '#3B82F6', // blue-500
          glacier: '#F59E0B', // amber-500
          deeparchive: '#EF4444', // red-500
        }
      },
    },
  },
  plugins: [],
}
