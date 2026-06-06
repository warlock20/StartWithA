import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ErrorBoundary } from "../components/shared/ErrorBoundary";

// Single QueryClient shared across all islands on the page.
// Created lazily so the module can be imported without side effects.
let queryClient = null;
function getQueryClient() {
  if (!queryClient) {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 30_000,       // 30s — avoid refetch storms across islands
          retry: 1,                // retry once on failure
          refetchOnWindowFocus: false,
        },
      },
    });
  }
  return queryClient;
}

/**
 * Mount a React island into a DOM element.
 *
 * Wraps the component in QueryClientProvider + ErrorBoundary automatically.
 * For use by NEW islands only — existing islands (BlockNote, CompanyResourcesManager,
 * SessionSummary) keep their own entry files unchanged.
 *
 * Usage (in entry file):
 *   import { mountIsland } from './lib/mountIsland';
 *   import { MyComponent } from './components/MyComponent';
 *
 *   window.initMyComponent = function(elementId, config) {
 *     return mountIsland(elementId, MyComponent, config);
 *   };
 *
 * @param {string} elementId - DOM element ID to mount into
 * @param {React.ComponentType} Component - React component to render
 * @param {object} props - Props to pass to the component
 * @returns {Root|null} React root (for unmounting if needed), or null if mount point missing
 */
export function mountIsland(elementId, Component, props = {}) {
  const container = document.getElementById(elementId);
  if (!container) {
    console.error(`[React Island] Mount point #${elementId} not found`);
    return null;
  }

  const root = createRoot(container);
  root.render(
    <QueryClientProvider client={getQueryClient()}>
      <ErrorBoundary>
        <Component {...props} />
      </ErrorBoundary>
    </QueryClientProvider>
  );
  return root;
}
