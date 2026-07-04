# Start with A — Strategy & Step 1 Plan

*Working strategy document. Keep it short, keep it light.*

---

## Part 1 — Business Plan (Brief)

### The one-line model
Open-source the platform. Distribute through investing communities.
Earn by **hosting it as a service** for the serious investors who'd rather pay
than self-host. Stay a light, one-person operation.

### Why this model (and why it fits Germany)
- The product is **niche** (deep-value / fundamental investors), so a
  venture-style startup is the wrong shape — high effort, small market.
- Spinning up a heavy company structure in Germany (GmbH/UG, VAT across the EU,
  etc.) is overkill before there's any revenue.
- This model lets us **start as a Kleingewerbe** (small trade, ~€50 to register,
  VAT-exempt under the Kleinunternehmer rule) and only formalize later **if**
  hosting revenue justifies it.
- No investors, no payroll, no office. Effort scales only when paying clients ask.

### Why open source is the strategy, not a giveaway
- **Privacy is the wedge.** Serious investors guard their thesis and holdings.
  "Here's the code, run it yourself, we never see your data" beats any closed
  competitor on the one thing this audience cares about most.
- **Open source IS the distribution.** Self-hostable tools get shared organically.
  Trust comes from transparency, not marketing spend.
- **Precedent:** Ghostfolio does exactly this — open-source core, self-host free,
  paid hosted tier for people who don't want to run a server.

### How we make money (light + high margin)
- **Not** volume SaaS. We don't chase hundreds of €15/month users with a support queue.
- Instead: **white-glove hosting** for a small number of serious investors who
  love the product and ask us to run it for them.
- Higher price, fewer clients, manageable support. Money is a **side effect** of
  people loving the tool — not the goal.
- The AI layer (mistake detection, behavioral warnings, prompt tuning) is the
  natural premium: it needs API keys and tuning, so it's the part people would
  rather we manage.

### Distribution channels
- Reddit: r/ValueInvesting, r/SecurityAnalysis, r/investing
- Hacker News (Show HN) — the open-source + self-host angle plays well there
- Value-investing communities (forums, Substacks, Discords)
- LinkedIn (founder story post — drafted separately)
- Organic: shareable research templates/checklists pull in new users

### How interested clients reach us
- Simple: a "Want this hosted? Contact us" path (email / form / GitHub Discussions).
- **Pull, not push.** We don't sell hosting cold — people who already use and
  love the self-hosted version raise their hand. They're pre-qualified.

### The one cost to stay honest about
Open source is **not** automatically less effort. A public repo means issues,
PRs, and support questions forever. We control this by:
- Setting support expectations **explicitly** in the README (best-effort community
  support; **paid hosting clients get direct support**).
- Letting the community carry low-value work (templates, checklists, sector defs).

---

## Part 2 — Step 1: Repo Setup Plan

Goal: get the repo **safe, clean, and runnable by a stranger** before it goes public.
Nothing below is optional — a public repo is read on day one.

### A. Security cleanup (BLOCKER — do first)
- [ ] Confirm `.env` is in `.gitignore` and **not** tracked.
- [ ] Scrub any secrets from **git history** (not just the latest commit) —
      e.g. `git filter-repo` or BFG. Removing a key in a new commit is NOT enough;
      it stays in history.
- [ ] **Rotate** every credential that was ever committed (DB, API keys, Flask
      secret key). Assume anything in history is already compromised.
- [ ] Provide a clean `.env.example` with placeholder values and comments.

### B. Make it runnable by someone who isn't you
- [ ] `docker-compose.yml` that brings up app + Postgres with one command.
- [ ] Test it on a **fresh machine / clean checkout** — not your dev box with its
      existing state. If it doesn't work clean, it doesn't work.
- [ ] Document required env vars and the model-provider setup (bring-your-own key).
- [ ] Seed/migration step documented (Alembic) so the DB initializes cleanly.

### C. Harden external integrations
- [ ] Audit the **Yahoo Finance provider** — it's an unofficial endpoint that
      rate-limits and breaks. Add retries, timeouts, graceful failure, and clear
      error messages so a stranger's deploy doesn't crash on first use.
- [ ] Make sure missing/optional API keys degrade gracefully (AI features off,
      not app crash).

### D. Open-source essentials (the files people look for)
- [ ] `LICENSE` — **AGPL-3.0** (chosen: keeps hosted derivatives open; standard
      open-core base, same as Ghostfolio).
- [ ] `README.md` — founder story + screenshots + 1-command quickstart +
      "what's open / what hosting offers" + support expectations.
- [ ] `CONTRIBUTING.md` — how to contribute templates/checklists/code.
- [ ] `SECURITY.md` — how to privately report a vulnerability (don't let people
      post exploits as public issues).
- [ ] Issue + PR templates (`.github/`).
- [ ] Support-expectations paragraph in README (community = best-effort;
      hosting clients = direct support).

### E. Brand
- [ ] Merge the **rebrand to "Start with A"** first (see REBRAND_INSTRUCTIONS.md)
      so the public repo is consistent from commit one.
- [ ] Rename the GitHub repo + update description.

### F. Hosting contact path
- [ ] Add a clear "Want it hosted? → contact" line in README (email or
      GitHub Discussions). Low-tech is fine for v1.

### Order of operations
1. Rebrand merged →
2. Security scrub + key rotation →
3. Clean Docker run verified on fresh checkout →
4. Yahoo/integration hardening →
5. Open-source files (LICENSE, README, etc.) →
6. Flip repo public →
7. *Then* publish the LinkedIn/Reddit posts with the link.

> Do not publish any post with the GitHub link until steps 1–6 are done.
> The first thing a curious reader does is open the repo.

---

## Out of scope for now (parked)
- German company formation beyond Kleingewerbe — revisit only if hosting revenue grows.
- Payment/Merchant-of-Record setup (Lemon Squeezy / Polar) — only needed once we
  have a paying hosting client; not a launch blocker.
- Landing-page redesign — separate task, after rebrand merges.
- Pricing for hosting tier — decide when the first client asks; don't pre-build.