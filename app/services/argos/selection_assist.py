# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Selection assist — what the user's own knowledge says about a highlighted phrase.

The user selects text while reading, and the companion offers evidence they
already have: a past finding, a note, a logged mistake. Nobody asked it a
question, so it has to earn the interruption.

**Retrieval only.** No LLM, no tokens. The one cost is embedding the selection,
which goes through the configured API provider — local models are deliberately
absent from the priority list, so nothing loads PyTorch into a web worker.

Quiet by design, which is mostly about what this *doesn't* return:

- selections shorter than ``MIN_SELECTION_CHARS`` never trigger a lookup, so a
  stray click or a two-word highlight costs nothing;
- matches below ``MIN_RELEVANCE`` are dropped — a popover of weak guesses is
  worse than no popover, because the user stops trusting it;
- at most ``MAX_EVIDENCE`` items, because this is a popover and not a search page.

Ownership comes from ``search_my_knowledge``, which filters by ``user_id`` in the
query itself.
"""

from app.services.argos.knowledge_search import search_my_knowledge

# Below this, a selection is a click or a stray word — not a question.
MIN_SELECTION_CHARS = 12

# A whole paragraph embeds poorly and isn't a "phrase" any more; trim rather than
# refuse, so selecting a long sentence still works.
MAX_SELECTION_CHARS = 600

# Cosine floor — the single knob deciding how often this feature speaks.
#
# MEASURED, not guessed, against a real 68-chunk account using Gemini
# embeddings (gemini-embedding-001 truncated to 768 dims):
#
#   6 relevant phrases    top score  0.640 – 0.968
#   6 unrelated phrases   top score  0.561 – 0.623   (recipes, train delays, gibberish)
#
# Note how compressed that range is: with this model, unrelated text still
# scores ~0.6, and gibberish once beat a genuine query. Anything below ~0.63
# fires on everything, which is worse than silence — the user stops trusting the
# popover. 0.63 sits in the gap between the two classes.
#
# This number is specific to the embedding model. Changing providers moves the
# whole distribution and the floor must be re-measured, not carried over.
MIN_RELEVANCE = 0.63

MAX_EVIDENCE = 3

# One slot per source so a company with many notes can't fill the popover with
# three variations of the same note.
_PER_SOURCE_CAPS = {'finding': 1, 'journal': 1, 'resource': 1, 'decision': 1, 'mistake': 1}


def find_evidence_for_selection(user_id, text, company_id=None):
    """Evidence for a highlighted phrase. Returns [] when there's nothing worth saying.

    Same dict shape as ``search_my_knowledge``:
    ``{source_type, source_id, title, summary, score}``.

    ``company_id`` is a preference, not a filter. Scoping hard to the page's
    company sounds right and is wrong in practice: knowledge is indexed per
    company, so on a company you haven't written about yet — exactly where you are
    most likely to be reading something new — the scoped search matches nothing
    and the feature is silent forever. So: try the company first, and fall back to
    the whole account rather than saying nothing.
    """
    selection = (text or '').strip()
    if len(selection) < MIN_SELECTION_CHARS:
        return []

    query = selection[:MAX_SELECTION_CHARS]

    def _search(scope):
        return search_my_knowledge(
            user_id, query, company_id=scope,
            total_cap=MAX_EVIDENCE, per_source_caps=_PER_SOURCE_CAPS)

    results = _search(company_id) if company_id else []
    if not results:
        results = _search(None)
    return [r for r in results if r['score'] >= MIN_RELEVANCE][:MAX_EVIDENCE]
