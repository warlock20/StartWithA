/**
 * How a sweep row's derived state is read for display.
 *
 * Both surfaces that show a row — the Tabulator table and Focus Mode — ask
 * the same questions of it, and they must answer identically: a row cannot
 * read "Pending" in one view and "Untracked" in the other, nor offer Kill in
 * one and withhold it in the other. These live here rather than in either
 * component so neither imports the other.
 */

// `untracked` is a real state, not an error: the row is linked to a company
// the user has done nothing with yet. To a reader that is indistinguishable
// from a row they have not considered, so both read "Pending". Undo is the
// ordinary way a row lands here — it deletes the decision and deliberately
// keeps the link — and "Untracked" would be a worse answer there than
// "Pending".
export function displayState(row) {
  if (!row || !row.state) return null;
  if (row.state.key === 'untracked') return null;
  return row.state;
}

// The user already owns this company, so offering to kill it is nonsense.
// Withholding it is a display rule, not a permission: the sweep row is not
// where a held position gets exited.
export function isHeld(row) {
  var state = displayState(row);
  return !!state && state.key === 'held';
}

// The label the badge actually shows. The stored decision can contradict it
// (a row marked "inbox" whose company was later killed), so anything that
// reads the row's status for the user — badge text, sorting — goes through
// this rather than through `row.decision`.
export function statusLabel(row) {
  var state = displayState(row);
  return state ? state.label : 'Pending';
}
