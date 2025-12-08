import React, { useState, useEffect, useRef } from "react";
import { BlockNoteView } from "@blocknote/mantine";
import { useCreateBlockNote } from "@blocknote/react";
import "@blocknote/core/fonts/inter.css";
import "@blocknote/mantine/style.css";
import "../styles/blocknote-custom.css";
import "../styles/blocknote-toc.css";

/**
 * BlockNote Editor with Table of Contents Sidebar
 * Enhanced version with navigation sidebar for long documents
 */
export function BlockNoteWithTOC({
  initialContent,
  onSave,
  onSelectionChange,
  placeholder = "Start your research here... Type '/' for commands",
  editorId = "blocknote-editor",
  showTOC = true
}) {
  const [saveStatus, setSaveStatus] = useState("saved");
  const [tocItems, setTocItems] = useState([]);
  const [isTOCOpen, setIsTOCOpen] = useState(true);
  const [activeHeading, setActiveHeading] = useState(null);
  const saveTimerRef = useRef(null);
  const editorContainerRef = useRef(null);

  // Create editor instance
  const editor = useCreateBlockNote({
    initialContent: initialContent ? parseInitialContent(initialContent) : undefined,
  });

  // Expose editor instance globally
  useEffect(() => {
    if (editor) {
      window.blockNoteEditorInstance = {
        editor: editor,
        insertHTML: async (html) => {
          const blocks = convertHTMLToBlocks(html);
          try {
            const currentBlock = editor.getTextCursorPosition().block;
            await editor.insertBlocks(blocks, currentBlock, "after");
          } catch (e) {
            await editor.insertBlocks(blocks, editor.document[editor.document.length - 1], "after");
          }
        }
      };
    }
    return () => {
      window.blockNoteEditorInstance = null;
    };
  }, [editor]);

  // Extract headings for TOC
  useEffect(() => {
    if (!editor || !showTOC) return;

    const updateTOC = () => {
      const blocks = editor.document;
      const headings = [];
      let headingIndex = 0;

      blocks.forEach((block, index) => {
        if (block.type === "heading") {
          const level = block.props?.level || 1;
          const text = block.content?.map(c => c.text || "").join("") || "Untitled";

          headings.push({
            id: `heading-${headingIndex}`,
            blockId: block.id, // Store the actual block ID from BlockNote
            level: level,
            text: text,
            blockIndex: index
          });
          headingIndex++;
        }
      });

      setTocItems(headings);
    };

    // Update TOC on editor changes
    updateTOC();
    return editor.onChange(updateTOC);
  }, [editor, showTOC]);

  // Auto-save on changes
  useEffect(() => {
    if (!editor) return;

    const handleChange = async () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      setSaveStatus("saving");

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

  // Scroll to heading
  const scrollToHeading = (blockId, blockIndex) => {
    if (!editor) return;

    try {
      // Get the editor wrapper element
      const editorWrapper = document.getElementById(editorId);
      if (!editorWrapper) {
        console.error(`Editor element #${editorId} not found`);
        return;
      }

      // Find the BlockNote editor's scrollable container
      // The actual editor content is in a nested structure
      const scrollableContainer = editorWrapper.querySelector('.bn-editor') ||
                                  editorWrapper.querySelector('[contenteditable="true"]') ||
                                  editorWrapper.querySelector('.ProseMirror');

      if (!scrollableContainer) {
        console.warn('Could not find scrollable container');
      }

      // Method 1: Find block by BlockNote's data-id attribute
      let targetElement = editorWrapper.querySelector(`[data-id="${blockId}"]`);

      // Method 2: Find by data-node-id (alternative attribute)
      if (!targetElement) {
        targetElement = editorWrapper.querySelector(`[data-node-id="${blockId}"]`);
      }

      // Method 3: Find blocks by their position
      if (!targetElement) {
        const allBlocks = editorWrapper.querySelectorAll('[data-id]');
        console.log(`Fallback to index. Found ${allBlocks.length} blocks, looking for index ${blockIndex}`);
        if (allBlocks.length > blockIndex) {
          targetElement = allBlocks[blockIndex];
        }
      }

      if (targetElement) {
        console.log('Found target element, scrolling to it...');

        // Scroll the element into view
        targetElement.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'nearest'
        });

        // Also move the cursor to this block (helps with context)
        try {
          const block = editor.document[blockIndex];
          if (block) {
            setTimeout(() => {
              editor.setTextCursorPosition(block, "end");
            }, 100);
          }
        } catch (e) {
          console.warn('Could not set cursor position:', e);
        }

        setActiveHeading(blockIndex);

        // Add temporary highlight to show which heading was clicked
        targetElement.style.transition = 'background-color 0.5s ease';
        targetElement.style.backgroundColor = '#fef3c7';
        setTimeout(() => {
          targetElement.style.backgroundColor = '';
        }, 1500);

        console.log('✓ Scrolled to heading:', blockIndex);
      } else {
        console.error(`Could not find block with ID ${blockId} or index ${blockIndex}`);

        // Debug: Show what blocks we can find
        const allBlocks = editorWrapper.querySelectorAll('[data-id]');
        console.log('Available blocks:', allBlocks.length);
        if (allBlocks.length > 0) {
          console.log('First block sample:', allBlocks[0]);
        }
      }
    } catch (e) {
      console.error("Error scrolling to heading:", e);
    }
  };

  return (
    <div className="blocknote-with-toc-container">
      {/* Table of Contents Sidebar */}
      {showTOC && tocItems.length > 0 && (
        <div className={`blocknote-toc-sidebar ${isTOCOpen ? 'open' : 'closed'}`}>
          {/* TOC Header */}
          <div className="toc-header">
            <h3 className="toc-title">
              <i className="bi bi-list-nested"></i>
              {isTOCOpen && <span>Contents</span>}
            </h3>
            <button
              className="toc-toggle-btn"
              onClick={() => setIsTOCOpen(!isTOCOpen)}
              title={isTOCOpen ? "Collapse" : "Expand"}
            >
              <i className={`bi bi-chevron-${isTOCOpen ? 'left' : 'right'}`}></i>
            </button>
          </div>

          {/* TOC List */}
          {isTOCOpen && (
            <nav className="toc-nav">
              <ul className="toc-list">
                {tocItems.map((item, index) => (
                  <li
                    key={item.id}
                    className={`toc-item toc-level-${item.level} ${activeHeading === item.blockIndex ? 'active' : ''}`}
                  >
                    <button
                      onClick={() => scrollToHeading(item.blockId, item.blockIndex)}
                      className="toc-link"
                      title={item.text}
                    >
                      {item.text}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>
          )}
        </div>
      )}

      {/* Editor Container */}
      <div
        className="blocknote-editor-wrapper-with-toc"
        id={editorId}
        ref={editorContainerRef}
      >
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

        {/* BlockNote Editor */}
        <BlockNoteView editor={editor} theme="light" />
      </div>
    </div>
  );
}

/**
 * Parse initial content (HTML or JSON)
 */
function parseInitialContent(content) {
  if (!content || content.trim() === "") {
    return undefined;
  }

  try {
    const blocks = JSON.parse(content);
    if (Array.isArray(blocks)) {
      return blocks;
    }
  } catch (e) {
    return undefined;
  }

  return undefined;
}

/**
 * Convert HTML to BlockNote blocks
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

export default BlockNoteWithTOC;
