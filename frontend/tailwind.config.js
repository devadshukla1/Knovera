// Preserve semantic CSS variables while allowing Tailwind opacity modifiers.
const token = (name) => ({ opacityValue }) => opacityValue === undefined
  ? `var(${name})`
  : `color-mix(in srgb, var(${name}) calc(${opacityValue} * 100%), transparent)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: token("--background"),
        surface: {
          DEFAULT: token("--surface"),
          elevated: token("--surface-elevated"),
          muted: token("--surface-muted"),
          overlay: token("--surface-overlay"),
        },
        border: {
          DEFAULT: token("--border"),
          subtle: token("--border-subtle"),
          highlight: token("--border-highlight"),
        },
        text: {
          primary: token("--text-primary"),
          secondary: token("--text-secondary"),
          muted: token("--text-muted"),
        },
        primary: {
          DEFAULT: token("--primary"),
          hover: token("--primary-hover"),
          soft: token("--primary-soft"),
          foreground: token("--primary-foreground"),
        },
        accent: {
          DEFAULT: token("--accent"),
          purple: token("--accent-purple"),
        },
        success: token("--success"),
        warning: token("--warning"),
        danger: token("--danger"),
        error: token("--error"),
        info: token("--info"),
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        'glow-sm': '0 0 15px -3px rgba(139, 124, 255, 0.25)',
        'glow': '0 0 25px -4px rgba(139, 124, 255, 0.35)',
        'glow-teal': '0 0 20px -3px rgba(45, 212, 191, 0.3)',
        'elevation-1': '0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px -1px rgba(0, 0, 0, 0.3)',
        'elevation-2': '0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -2px rgba(0, 0, 0, 0.3)',
        'elevation-3': '0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -4px rgba(0, 0, 0, 0.4)',
        'elevation-4': '0 20px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.5)',
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '112': '28rem',
      },
      borderRadius: {
        sm: '6px',
        DEFAULT: '8px',
        md: '10px',
        lg: '14px',
        xl: '18px',
        '2xl': '24px',
      },
      animation: {
        'shimmer': 'shimmer 2.5s linear infinite',
        'border-beam': 'border-beam calc(var(--duration)*1s) infinite linear',
        'pulse-subtle': 'pulse-subtle 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'gradient-pan': 'gradient-pan 6s ease infinite',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
        'border-beam': {
          '100%': {
            'offset-distance': '100%',
          },
        },
        'pulse-subtle': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        'gradient-pan': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
      },
    },
  },
  plugins: [],
};
