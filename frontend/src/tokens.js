/**
 * Design Tokens — Shared constants for React islands.
 *
 * These mirror the CSS custom properties defined in
 *   app/static/css/modules/_variables.css
 *
 * Usage in React components:
 *   import { colors, spacing, radius, shadows, fonts } from "../tokens";
 *   <div style={{ color: colors.gray700, padding: spacing.md }}>
 *
 * We use CSS var() references so values stay in sync with the design
 * system at runtime, while also providing the raw hex fallback for
 * contexts where CSS vars aren't supported (e.g. canvas, SVG fills).
 */

// ─────────────────────────────────────────────────────────────────────────────
// Colors
// ─────────────────────────────────────────────────────────────────────────────
export const colors = {
  // Accent — Forest Green
  accent: "var(--accent-color, #2d6a4f)",
  accentLight: "var(--accent-light, #40916c)",
  accentDark: "var(--accent-dark, #1b4332)",
  accentSoft: "var(--accent-soft, #f0fdf4)",
  accent50: "var(--accent-50, #f0fdf4)",
  accent100: "var(--accent-100, #dcfce7)",
  accent700: "var(--accent-700, #1b4332)",

  // Gray scale
  gray50: "var(--gray-50, #f7f8fc)",
  gray100: "var(--gray-100, #f3f4f6)",
  gray200: "var(--gray-200, #e5e7eb)",
  gray300: "var(--gray-300, #d1d5db)",
  gray400: "var(--gray-400, #9ca3af)",
  gray500: "var(--gray-500, #6b7280)",
  gray600: "var(--gray-600, #4b5563)",
  gray700: "var(--gray-700, #374151)",
  gray800: "var(--gray-800, #1f2937)",
  gray900: "var(--gray-900, #111827)",

  // Semantic
  success50: "var(--success-50, #f0fdf4)",
  success500: "var(--success-500, #059669)",
  warning50: "var(--warning-50, #fef3c7)",
  warning500: "var(--warning-500, #f59e0b)",
  danger50: "var(--danger-50, #fef2f2)",
  danger500: "var(--danger-500, #dc2626)",
  info50: "var(--info-50, #eff6ff)",
  info500: "var(--info-500, #3b82f6)",
  purple50: "var(--purple-50, #f5f3ff)",
  purple500: "var(--purple-500, #8b5cf6)",

  // Semantic aliases
  border: "var(--border-light, #e5e7eb)",
  borderMedium: "var(--border-medium, #d1d5db)",
  textPrimary: "var(--text-primary, #111827)",
  textSecondary: "var(--text-secondary, #6b7280)",
  textMuted: "var(--text-muted, #9ca3af)",
  white: "#ffffff",
};

// ─────────────────────────────────────────────────────────────────────────────
// Raw hex values — for use when CSS var() isn't viable (canvas, SVG, etc.)
// ─────────────────────────────────────────────────────────────────────────────
export const rawColors = {
  accent: "#2d6a4f",
  accentLight: "#40916c",
  accentDark: "#1b4332",
  gray200: "#e5e7eb",
  gray500: "#6b7280",
  gray800: "#1f2937",
  gray900: "#111827",
  danger500: "#dc2626",
  info500: "#3b82f6",
  success500: "#059669",
  warning500: "#f59e0b",
  white: "#ffffff",
};

// ─────────────────────────────────────────────────────────────────────────────
// Spacing
// ─────────────────────────────────────────────────────────────────────────────
export const spacing = {
  xs: "0.25rem",  // 4px
  sm: "0.5rem",   // 8px
  md: "1rem",     // 16px
  lg: "1.5rem",   // 24px
  xl: "2rem",     // 32px
  xxl: "3rem",    // 48px
};

// Numeric px values for calculations
export const spacingPx = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

// ─────────────────────────────────────────────────────────────────────────────
// Border Radius
// ─────────────────────────────────────────────────────────────────────────────
export const radius = {
  sm: "var(--radius-sm, 4px)",
  md: "var(--radius-md, 8px)",
  btn: "var(--radius-btn, 10px)",
  lg: "var(--radius-lg, 12px)",
  xl: "var(--radius-xl, 16px)",
  pill: "var(--radius-pill, 50px)",
};

// ─────────────────────────────────────────────────────────────────────────────
// Shadows
// ─────────────────────────────────────────────────────────────────────────────
export const shadows = {
  light: "var(--shadow-light, 0 2px 4px rgba(0,0,0,0.04))",
  medium: "var(--shadow-medium, 0 4px 12px rgba(0,0,0,0.08))",
  heavy: "var(--shadow-heavy, 0 8px 32px rgba(0,0,0,0.12))",
  hover: "var(--shadow-hover, 0 12px 40px rgba(0,0,0,0.15))",
};

// ─────────────────────────────────────────────────────────────────────────────
// Fonts
// ─────────────────────────────────────────────────────────────────────────────
export const fonts = {
  sans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  mono: "'JetBrains Mono', ui-monospace, monospace",
  heading: "'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

// ─────────────────────────────────────────────────────────────────────────────
// Font sizes
// ─────────────────────────────────────────────────────────────────────────────
export const fontSizes = {
  xs: "0.75rem",    // 12px
  sm: "0.875rem",   // 14px
  base: "1rem",     // 16px
  lg: "1.125rem",   // 18px
  xl: "1.25rem",    // 20px
  xxl: "1.5rem",    // 24px
};

// ─────────────────────────────────────────────────────────────────────────────
// Transitions
// ─────────────────────────────────────────────────────────────────────────────
export const transitions = {
  fast: "0.15s ease",
  normal: "0.3s ease",
  slow: "0.5s ease",
};
