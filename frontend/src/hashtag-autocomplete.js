import { mountIsland } from "./lib/mountIsland";
import { HashtagAutocomplete } from "./components/HashtagAutocomplete";

/**
 * Mount the HashtagAutocomplete React island.
 *
 * Usage (in Jinja2 template):
 *   window.initHashtagAutocomplete('hashtag-autocomplete-mount', {
 *     name: 'hashtags',
 *     initialValue: '#valuation #moat',
 *     placeholder: 'e.g., #valuation #moat #earnings',
 *     className: 'form-control'
 *   });
 */
window.initHashtagAutocomplete = function (elementId, config) {
  return mountIsland(elementId, HashtagAutocomplete, config);
};
