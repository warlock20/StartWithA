import { colors } from "../../tokens";

/**
 * Loading spinner using Bootstrap's spinner-border classes.
 * Usage: <LoadingSpinner size="sm" message="Loading data..." />
 */
export function LoadingSpinner({ size = "sm", message }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, color: colors.textMuted }}>
      <span className={`spinner-border spinner-border-${size}`} role="status" />
      {message && <span>{message}</span>}
    </span>
  );
}
