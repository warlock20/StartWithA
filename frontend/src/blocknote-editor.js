import React from "react";
import { createRoot } from "react-dom/client";
import { BlockNoteEditor } from "./components/BlockNoteEditor";

/**
 * Initialize BlockNote Editor
 * Called from Flask template to mount React component
 *
 * @param {string} elementId - DOM element ID to mount to
 * @param {object} config - Editor configuration
 */
window.initBlockNoteEditor = function (elementId, config = {}) {
  const container = document.getElementById(elementId);

  if (!container) {
    console.error(`Element #${elementId} not found`);
    return null;
  }

  const root = createRoot(container);

  // Fetch initial content from API
  const loadInitialContent = async () => {
    if (config.getResearchNotesUrl) {
      try {
        const response = await fetch(config.getResearchNotesUrl);
        const data = await response.json();
        return data.success ? data.content : "";
      } catch (error) {
        console.error("Failed to load initial content:", error);
        return "";
      }
    }
    return config.initialContent || "";
  };

  // Save handler
  const handleSave = async (json, blocks) => {
    if (config.saveResearchNotesUrl) {
      try {
        const response = await fetch(config.saveResearchNotesUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: json }),
        });

        const data = await response.json();

        if (!data.success) {
          throw new Error(data.error || "Save failed");
        }

        // Call custom onSave callback if provided
        if (config.onSave) {
          config.onSave(data);
        }
      } catch (error) {
        console.error("Save error:", error);
        throw error;
      }
    }
  };

  // Selection change handler for snippets
  const handleSelectionChange = (selection) => {
    const selectedText = selection ? selection.toString() : "";

    if (config.onSelectionChange) {
      config.onSelectionChange(selectedText, selection);
    }

    // Update global variable for snippet functionality
    if (window.selectedSnippetText !== undefined) {
      window.selectedSnippetText = selectedText;
    }

    // Show/hide snippet button
    const snippetBtn = document.getElementById("saveSnippetBtn");
    if (snippetBtn) {
      if (selectedText && selectedText.length > 0) {
        snippetBtn.style.display = "block";
      } else {
        snippetBtn.style.display = "none";
      }
    }
  };

  // Load content and render
  loadInitialContent().then((initialContent) => {
    root.render(
      <BlockNoteEditor
        initialContent={initialContent}
        onSave={handleSave}
        onSelectionChange={handleSelectionChange}
        placeholder={config.placeholder}
        editorId={elementId}
      />
    );
  });

  return root;
};

/**
 * Get editor content as JSON
 * Useful for exporting or manual saves
 */
window.getBlockNoteContent = function (elementId) {
  const container = document.getElementById(elementId);
  if (container && container._reactRootContainer) {
    // Access editor instance and get content
    // This would need to be implemented via ref
    console.warn("getBlockNoteContent not yet implemented");
    return null;
  }
  return null;
};

// Export for potential direct imports
export { BlockNoteEditor };
