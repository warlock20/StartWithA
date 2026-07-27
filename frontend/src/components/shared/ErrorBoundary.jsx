import React from "react";
import { colors, radius, spacing } from "../../tokens";

/**
 * React error boundary with a retry button.
 * Catches rendering errors in child components and displays a fallback UI.
 *
 * Usage: <ErrorBoundary><MyComponent /></ErrorBoundary>
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("[React Island] Error caught by boundary:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: spacing.md,
          borderRadius: radius.md,
          border: `1px solid ${colors.danger500}`,
          background: colors.danger50,
          color: colors.danger500,
          fontSize: 13,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>
            Something went wrong
          </div>
          <div style={{ color: colors.textSecondary, marginBottom: 12 }}>
            {this.state.error?.message || "An unexpected error occurred."}
          </div>
          <button
            onClick={this.handleRetry}
            style={{
              padding: "6px 12px", borderRadius: 6,
              border: `1px solid ${colors.danger500}`,
              background: colors.white, color: colors.danger500,
              fontSize: 12, fontWeight: 600, cursor: "pointer",
            }}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
