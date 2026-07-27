/**
 * Session Summary — Constants & Configuration
 *
 * Status colors align with the platform's existing design tokens:
 *   - _variables.css: --success-500, --danger-500, --warning-500, --info-500
 *   - _checklist-verification.css: .cl-progress-segment, .cl-verdict-btn, .cl-map-item-number
 *   - tokens.js: colors.success500, colors.danger500, etc.
 */
import { colors, rawColors } from "../../tokens";

export const STATUS_CONFIG = {
  satisfied: {
    label: 'Satisfied',
    color: colors.success500,
    rawColor: rawColors.success500,
    bg: colors.success50,
    border: '#a7f3d0',
    icon: 'check-circle-fill',
  },
  not_satisfied: {
    label: 'Not Satisfied',
    color: colors.danger500,
    rawColor: rawColors.danger500,
    bg: colors.danger50,
    border: '#fecaca',
    icon: 'x-circle-fill',
  },
  needs_attention: {
    label: 'Needs Attention',
    color: colors.warning500,
    rawColor: rawColors.warning500,
    bg: colors.warning50,
    border: '#fde68a',
    icon: 'exclamation-circle-fill',
  },
  neutral: {
    label: 'Neutral',
    color: colors.info500,
    rawColor: rawColors.info500,
    bg: colors.info50,
    border: colors.gray200,
    icon: 'dash-circle-fill',
  },
  not_answered: {
    label: 'Not Answered',
    color: colors.gray400,
    rawColor: '#9ca3af',
    bg: colors.gray100,
    border: colors.gray200,
    icon: 'circle',
  },
};

export const FILTER_TABS = [
  { id: 'all', label: 'All', color: colors.gray600 },
  { id: 'satisfied', label: 'Satisfied', color: STATUS_CONFIG.satisfied.color },
  { id: 'needs_attention', label: 'Attention', color: STATUS_CONFIG.needs_attention.color },
  { id: 'not_satisfied', label: 'Not Satisfied', color: STATUS_CONFIG.not_satisfied.color },
  { id: 'neutral', label: 'Neutral', color: STATUS_CONFIG.neutral.color },
];
