import { mountIsland } from "./lib/mountIsland";
import { HomePreview } from "./components/home-preview/HomePreview";

/**
 * Home Preview — React island entry point.
 *
 * Renders the tabbed product showcase on the public landing page.
 * Mounts into #home-preview-root defined in public_home.html.
 */

document.addEventListener("DOMContentLoaded", function () {
  const el = document.getElementById("home-preview-root");
  if (el) {
    mountIsland("home-preview-root", HomePreview, {});
  }
});
