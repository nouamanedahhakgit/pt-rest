/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      fontFamily: {
        'sans': ['Karla', 'system-ui', 'sans-serif'],
        'heading': ['Abril Fatface', 'serif'],
        'handwriting': ['Caveat', 'cursive'],
      },
      colors: {
        brand: {
          50: '#fff5f5',
          100: '#ffe3e3',
          200: '#ffc9c9',
          300: '#ffa8a8',
          400: '#ff8787',
          500: '#ff6b6b',
          600: '#fa5252',
          700: '#f03e3e',
          800: '#e03131',
          900: '#c92a2a',
        },
        coral: {
          50: '#fff4ed',
          100: '#ffe6d5',
          200: '#ffd0b5',
          300: '#ffb088',
          400: '#ff9466',
          500: '#ff7849',
          600: '#f9632b',
          700: '#e04f1a',
          800: '#c4440f',
          900: '#a23b0f',
        },
        cream: {
          50: '#fefdfb',
          100: '#fdfaf5',
          200: '#fbf5eb',
          300: '#f9f0e1',
          400: '#f7ebd7',
          500: '#f5e6cd',
        },
      },
    },
  },
}