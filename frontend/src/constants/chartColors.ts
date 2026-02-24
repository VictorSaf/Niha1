/**
 * Hex color constants for SVG charts and canvas-based chart libraries.
 * Tailwind classes don't work in SVG attributes or chart library configs,
 * so these hex values map to our design system tokens.
 */

/* eslint-disable no-restricted-syntax -- SVG/canvas requires hex values */

/** Maps to Tailwind's navy-* palette */
export const CHART_NAVY = {
  400: '#94a3b8',
  500: '#64748b',
  '700_30': 'rgba(51, 65, 85, 0.3)',
  800: '#1e293b',
} as const;

/** Maps to Tailwind's emerald/green/teal/cyan palette */
export const CHART_GREEN = {
  emerald400: '#34d399',
  emerald500: '#10b981',
  green400: '#4ade80',
  teal400: '#2dd4bf',
  cyan400: '#22d3ee',
} as const;

/** Maps to Tailwind's red palette */
export const CHART_RED = {
  red400: '#f87171',
  red500: '#ef4444',
} as const;

/** Convenience: up = green, down = red for trend lines */
export const TREND_COLORS = {
  up: CHART_GREEN.emerald500,
  down: CHART_RED.red500,
  upFill: 'rgba(16,185,129,0.08)',
  downFill: 'rgba(239,68,68,0.08)',
} as const;

/** Candlestick / line chart color config */
export const CANDLESTICK_COLORS = {
  background: 'transparent',
  text: CHART_NAVY[400],
  grid: CHART_NAVY['700_30'],
  crosshair: CHART_NAVY[500],
  upColor: CHART_GREEN.emerald400,
  downColor: CHART_RED.red400,
  lineColor: CHART_GREEN.emerald400,
  labelBackground: CHART_NAVY[800],
} as const;

/** EnvironmentalImpact gauge SVG colors */
export const GAUGE_COLORS = [
  CHART_GREEN.emerald400,
  CHART_GREEN.green400,
  CHART_GREEN.teal400,
  CHART_GREEN.cyan400,
] as const;

/* eslint-enable no-restricted-syntax */
