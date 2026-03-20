import React, { useState, useEffect, useRef } from "react";
import { BlockNoteView } from "@blocknote/mantine";
import { useCreateBlockNote } from "@blocknote/react";
import "@blocknote/core/fonts/inter.css";
import "@blocknote/mantine/style.css";
import "../styles/blocknote-custom.css";

/**
 * BlockNote Editor Component - SIMPLIFIED
 * Using @blocknote/mantine for the simplest setup
 */
export function BlockNoteEditor({
  initialContent,
  onSave,
  onSelectionChange,
  placeholder = "Start your research here... Type '/' for commands",
  editorId = "blocknote-editor"
}) {
  const [saveStatus, setSaveStatus] = useState("saved");
  const saveTimerRef = useRef(null);

  // Create editor instance
  const editor = useCreateBlockNote({
    initialContent: initialContent ? parseInitialContent(initialContent) : undefined,
  });

  // Expose editor instance and methods globally for template insertion
  useEffect(() => {
    if (editor) {
      window.blockNoteEditorInstance = {
        editor: editor,
        insertHTML: async (html) => {
          // Convert HTML to BlockNote blocks
          const blocks = convertHTMLToBlocks(html);

          // Insert at cursor position
          try {
            const currentBlock = editor.getTextCursorPosition().block;
            await editor.insertBlocks(blocks, currentBlock, "after");
          } catch (e) {
            // If no cursor position, append to end
            await editor.insertBlocks(blocks, editor.document[editor.document.length - 1], "after");
          }
        }
      };
    }
    return () => {
      window.blockNoteEditorInstance = null;
    };
  }, [editor]);

  // Auto-save on changes
  useEffect(() => {
    if (!editor) return;

    const handleChange = async () => {
      // Clear existing timer
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      setSaveStatus("saving");

      // Debounce save (2 seconds)
      saveTimerRef.current = setTimeout(async () => {
        try {
          const blocks = editor.document;
          const json = JSON.stringify(blocks);

          if (onSave) {
            await onSave(json, blocks);
          }

          setSaveStatus("saved");
        } catch (error) {
          console.error("Save error:", error);
          setSaveStatus("error");
        }
      }, 2000);
    };

    // Subscribe to editor changes
    return editor.onChange(handleChange);
  }, [editor, onSave]);

  // Handle text selection
  useEffect(() => {
    if (!onSelectionChange) return;

    const handleSelectionChange = () => {
      const selection = window.getSelection();
      const selectedText = selection?.toString() || "";
      onSelectionChange(selectedText, selection);
    };

    document.addEventListener('selectionchange', handleSelectionChange);
    return () => document.removeEventListener('selectionchange', handleSelectionChange);
  }, [onSelectionChange]);

  // Fix copy from editor — ProseMirror sometimes fails to serialize custom blocks
  useEffect(() => {
    const wrapper = document.getElementById(editorId);
    if (!wrapper) return;

    const handleCopy = (e) => {
      const selection = window.getSelection();
      const selectedText = selection?.toString() || "";
      if (selectedText) {
        e.clipboardData.setData("text/plain", selectedText);
        e.preventDefault();
      }
    };

    wrapper.addEventListener("copy", handleCopy);
    return () => wrapper.removeEventListener("copy", handleCopy);
  }, [editorId]);

  return (
    <div className="blocknote-editor-wrapper" id={editorId}>
      {/* Save status indicator */}
      <div
        className={`editor-status ${saveStatus}`}
        style={{
          position: "absolute",
          top: "10px",
          right: "10px",
          padding: "6px 12px",
          borderRadius: "4px",
          fontSize: "12px",
          fontWeight: 500,
          display: "flex",
          alignItems: "center",
          gap: "6px",
          zIndex: 10,
          backgroundColor: saveStatus === "saved" ? "#d1fae5" : saveStatus === "saving" ? "#fef3c7" : "#fee2e2",
          color: saveStatus === "saved" ? "#065f46" : saveStatus === "saving" ? "#92400e" : "#991b1b",
        }}
      >
        {saveStatus === "saved" && (
          <>
            <span>✓</span>
            <span>Saved</span>
          </>
        )}
        {saveStatus === "saving" && (
          <>
            <span>⏳</span>
            <span>Saving...</span>
          </>
        )}
        {saveStatus === "error" && (
          <>
            <span>✗</span>
            <span>Error</span>
          </>
        )}
      </div>

      {/* BlockNote Editor - SIMPLE! */}
      <BlockNoteView editor={editor} theme="light" />
    </div>
  );
}

/**
 * Parse initial content (HTML, JSON, or plain text)
 */
function parseInitialContent(content) {
  if (!content || content.trim() === "") {
    return undefined;
  }

  try {
    // Try parsing as JSON first (BlockNote format)
    const blocks = JSON.parse(content);
    if (Array.isArray(blocks)) {
      return blocks;
    }
  } catch (e) {
    // Not JSON - check if it's HTML or plain text
    const trimmed = content.trim();

    // Check if it looks like HTML (contains tags)
    if (trimmed.includes('<') && trimmed.includes('>')) {
      // Convert HTML to BlockNote blocks
      const blocks = convertHTMLToBlocks(trimmed);
      if (blocks && blocks.length > 0) {
        return blocks;
      }
    } else {
      // Plain text - convert to paragraph blocks
      const lines = trimmed.split('\n').filter(line => line.trim());
      if (lines.length > 0) {
        return lines.map(line => ({
          type: "paragraph",
          content: [{ type: "text", text: line.trim(), styles: {} }]
        }));
      }
    }
  }

  return undefined;
}

/**
 * Convert HTML to BlockNote blocks (for template insertion)
 */
function convertHTMLToBlocks(html) {
  if (!html || html.trim() === "") {
    return [];
  }

  const parser = new DOMParser();
  const doc = parser.parseFromString(html, "text/html");
  const blocks = [];

  doc.body.childNodes.forEach((node) => {
    const block = nodeToBlock(node);
    if (block) {
      if (Array.isArray(block)) {
        blocks.push(...block);
      } else {
        blocks.push(block);
      }
    }
  });

  return blocks.length > 0 ? blocks : [{ type: "paragraph", content: [] }];
}

/**
 * Convert DOM node to BlockNote block
 */
function nodeToBlock(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent.trim();
    if (text) {
      return {
        type: "paragraph",
        content: [{ type: "text", text, styles: {} }],
      };
    }
    return null;
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return null;
  }

  const tagName = node.tagName.toLowerCase();

  // Headings
  if (tagName.match(/^h[1-6]$/)) {
    const level = parseInt(tagName.charAt(1));
    return {
      type: "heading",
      props: { level: Math.min(level, 3) },
      content: getInlineContent(node),
    };
  }

  // Lists
  if (tagName === "ul" || tagName === "ol") {
    const items = [];
    node.querySelectorAll("li").forEach((li) => {
      items.push({
        type: tagName === "ul" ? "bulletListItem" : "numberedListItem",
        content: getInlineContent(li),
      });
    });
    return items;
  }

  // Paragraph (default)
  return {
    type: "paragraph",
    content: getInlineContent(node),
  };
}

/**
 * Get inline content with styles
 */
function getInlineContent(element) {
  const content = [];
  const text = element.textContent.trim();

  if (text) {
    const styles = {};

    // Check for formatting
    if (element.querySelector("strong, b")) styles.bold = true;
    if (element.querySelector("em, i")) styles.italic = true;
    if (element.querySelector("u")) styles.underline = true;
    if (element.querySelector("s, strike")) styles.strike = true;

    content.push({
      type: "text",
      text: text,
      styles: styles,
    });
  }

  return content;
}

export default BlockNoteEditor;
