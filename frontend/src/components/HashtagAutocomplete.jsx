import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../lib/api";

/**
 * Hashtag autocomplete input with dropdown suggestions.
 *
 * Self-contained island: renders its own <input> + dropdown.
 * Reuses existing .hashtag-suggestions / .hashtag-suggestion-item CSS
 * from app/static/css/modules/_hashtag-autocomplete.css.
 *
 * Props (passed via mountIsland from template init script):
 *   name            — input name attribute (default: 'hashtags')
 *   initialValue    — pre-populated value (e.g. '#valuation #moat')
 *   placeholder     — input placeholder text
 *   apiUrl          — endpoint to fetch hashtags (default: '/journal/api/hashtags')
 *   className       — CSS class for input (default: 'form-control')
 *   minChars        — min chars after # to trigger suggestions (default: 1)
 *   maxSuggestions  — max dropdown items (default: 10)
 */
export function HashtagAutocomplete({
  name = "hashtags",
  initialValue = "",
  placeholder = "",
  apiUrl = "/journal/api/hashtags",
  className = "form-control",
  minChars = 1,
  maxSuggestions = 10,
}) {
  const [inputValue, setInputValue] = useState(initialValue);
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const inputRef = useRef(null);
  const containerRef = useRef(null);

  // ---------------------------------------------------------------------------
  // Fetch all hashtags once (staleTime: Infinity — list rarely changes)
  // ---------------------------------------------------------------------------
  const { data: hashtagsData } = useQuery({
    queryKey: ["hashtags", apiUrl],
    queryFn: () => apiGet(apiUrl),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  const hashtags = hashtagsData?.hashtags || [];

  // ---------------------------------------------------------------------------
  // Compute current word being typed (after #)
  // ---------------------------------------------------------------------------
  const currentHashtagWord = useMemo(() => {
    if (!inputRef.current) return null;
    const cursorPos = inputRef.current.selectionStart ?? inputValue.length;
    const textBeforeCursor = inputValue.substring(0, cursorPos);
    const words = textBeforeCursor.split(/\s+/);
    const currentWord = words[words.length - 1];

    if (currentWord.startsWith("#") && currentWord.length >= minChars + 1) {
      return {
        searchTerm: currentWord.substring(1).toLowerCase(),
        fullWord: currentWord,
      };
    }
    return null;
  }, [inputValue, minChars]);

  // ---------------------------------------------------------------------------
  // Filter suggestions
  // ---------------------------------------------------------------------------
  const suggestions = useMemo(() => {
    if (!currentHashtagWord || hashtags.length === 0) return [];

    const { searchTerm, fullWord } = currentHashtagWord;

    return hashtags
      .filter(
        (tag) =>
          tag.toLowerCase().includes(searchTerm) &&
          tag.toLowerCase() !== fullWord.toLowerCase()
      )
      .slice(0, maxSuggestions);
  }, [currentHashtagWord, hashtags, maxSuggestions]);

  // Show/hide dropdown based on suggestions
  useEffect(() => {
    setShowDropdown(suggestions.length > 0);
    setSelectedIndex(-1);
  }, [suggestions]);

  // ---------------------------------------------------------------------------
  // Click outside to close
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  // ---------------------------------------------------------------------------
  // Select a hashtag
  // ---------------------------------------------------------------------------
  const selectHashtag = useCallback(
    (tag) => {
      const input = inputRef.current;
      if (!input) return;

      const cursorPos = input.selectionStart ?? inputValue.length;
      const textBeforeCursor = inputValue.substring(0, cursorPos);
      const lastHashIndex = textBeforeCursor.lastIndexOf("#");

      if (lastHashIndex === -1) return;

      const before = inputValue.substring(0, lastHashIndex);
      const after = inputValue.substring(cursorPos);
      const newValue = before + tag + " " + after;

      setInputValue(newValue);
      setShowDropdown(false);

      // Set cursor position after the inserted tag
      const newCursorPos = lastHashIndex + tag.length + 1;
      requestAnimationFrame(() => {
        input.focus();
        input.setSelectionRange(newCursorPos, newCursorPos);
        // Dispatch input event for any external listeners
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
    },
    [inputValue]
  );

  // ---------------------------------------------------------------------------
  // Keyboard navigation
  // ---------------------------------------------------------------------------
  const handleKeyDown = useCallback(
    (e) => {
      if (!showDropdown) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((prev) =>
            Math.min(prev + 1, suggestions.length - 1)
          );
          break;

        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((prev) => Math.max(prev - 1, 0));
          break;

        case "Enter":
        case "Tab":
          if (selectedIndex >= 0 && suggestions[selectedIndex]) {
            e.preventDefault();
            selectHashtag(suggestions[selectedIndex]);
          }
          break;

        case "Escape":
          setShowDropdown(false);
          break;
      }
    },
    [showDropdown, selectedIndex, suggestions, selectHashtag]
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <input
        ref={inputRef}
        type="text"
        name={name}
        className={className}
        placeholder={placeholder}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        autoComplete="off"
      />

      {showDropdown && (
        <div className="hashtag-suggestions" style={{ display: "block" }}>
          {suggestions.map((tag, index) => (
            <div
              key={tag}
              className={`hashtag-suggestion-item${
                index === selectedIndex ? " selected" : ""
              }`}
              onMouseDown={(e) => {
                // mouseDown instead of click to fire before input blur
                e.preventDefault();
                selectHashtag(tag);
              }}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              {tag}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
