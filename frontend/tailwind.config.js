/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Light SaaS palette
        'app-bg': '#F7F8FC',
        surface: '#FFFFFF',
        'surface-2': '#F0F2F8',
        border:  '#EAECEF',
        primary: { DEFAULT: '#6C4CF1', light: '#8B5CF6', dark: '#5438D8', glow: '#6C4CF120' },
        success: { DEFAULT: '#22C55E', light: '#4ADE80', bg: '#DCFCE7' },
        warning: { DEFAULT: '#F59E0B', light: '#FCD34D', bg: '#FEF3C7' },
        danger:  { DEFAULT: '#EF4444', light: '#F87171', bg: '#FEE2E2' },
        ink:     { DEFAULT: '#111827', muted: '#6B7280', subtle: '#9CA3AF', faint: '#D1D5DB' },
        // Keep old tokens for components that still use them
        void:    '#F7F8FC',
        card:    '#FFFFFF',
        purple:  { DEFAULT: '#6C4CF1', light: '#8B5CF6', glow: '#6C4CF120' },
        cyan:    { DEFAULT: '#06b6d4', light: '#22d3ee', glow: '#06b6d420' },
        green:   { DEFAULT: '#22C55E', light: '#4ADE80', glow: '#22C55E20' },
        amber:   { DEFAULT: '#F59E0B', light: '#FCD34D', glow: '#F59E0B20' },
        rose:    { DEFAULT: '#EF4444', light: '#F87171' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'card':     '0 1px 3px rgba(0,0,0,0.07), 0 4px 12px rgba(0,0,0,0.04)',
        'card-md':  '0 4px 16px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.05)',
        'card-lg':  '0 8px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.06)',
        'card-hover':'0 8px 24px rgba(108,76,241,0.12), 0 2px 8px rgba(0,0,0,0.06)',
        'primary':  '0 4px 14px rgba(108,76,241,0.35)',
        // Legacy aliases
        'glow-sm':  '0 0 12px rgba(108,76,241,0.2)',
        'glow-md':  '0 0 24px rgba(108,76,241,0.25)',
        'glow-lg':  '0 0 48px rgba(108,76,241,0.2)',
        'cyan-glow':'0 0 24px rgba(6,182,212,0.15)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'float':      'float 6s ease-in-out infinite',
        'fade-in':    'fadeIn 0.3s ease-out',
        'slide-up':   'slideUp 0.4s ease-out',
      },
      keyframes: {
        float:    { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
        fadeIn:   { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp:  { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
};
