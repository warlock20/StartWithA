/**
 * Toast — thin bridge to the existing `window.showToast(message, type)` global
 * defined in `_base.html`.
 *
 * Usage (imperative):
 *   import { showToast } from '../shared/Toast';
 *   showToast('Saved!', 'success');
 *
 * Supported types: 'success' | 'danger' | 'info' | 'loading' | 'warning'
 */

/**
 * Show a toast notification via the platform global.
 * Falls back to console.log when the global isn't available (e.g., tests).
 */
export function showToast(message, type = 'info') {
  if (typeof window !== 'undefined' && typeof window.showToast === 'function') {
    window.showToast(message, type);
  } else {
    console.log(`[Toast/${type}] ${message}`);
  }
}
