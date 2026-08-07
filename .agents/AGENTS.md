# Workspace Agent Instructions: sr6yuriko

## Shadowrun 6e Rules & Mechanics Verification

When answering rules questions, updating character dossier files (`chapters/*.qmd`), auditing Karma/Nuyen ledgers, or verifying matrix/drone combat mechanics:

- Trigger rules lookups using `sr6 search "<item>"` or `sr6 rag query "<query>"`.
- Ensure all rules assertions follow the SRM 4-level authority hierarchy (Level 1 SRM Exception > Level 2 Supplements > Level 3 Core > Level 4 Homebrew).
- Provide explicit book and page citations wherever applicable.

## Writing & Narrative Anti-Slop (No AI Slop)

When writing or editing prose, narrative chapters (`chapters/*.md`), character questionnaire answers (`twenty_questions.qmd`), or user-facing summaries:

- Trigger or adhere to the `no-ai-slop` skill instructions (`C:\GitHub\sr6-core\.agents\skills\no-ai-slop\SKILL.md`).
- Avoid banned words & AI sensory tropes (`ozone`, `copper`, `delve`, `foster`, `leverage`, `robust`, `tapestry`, etc. as defined in `no-ai-slop`).
- Eliminate AI writing patterns: binary contrasts ("not X, but Y"), colon reveals, fake-profound kickers, summary recaps, throat-clearing openers, excessive em-dashes (>1.0 per 300 words), and excessive ellipses (>0.6 per 300 words).
- Preserve the authentic voice, concrete numbers/stats, active voice, and sharp character tone.
- **Walkthrough Metrics Logging:** Whenever `no-ai-slop` is invoked (for audits or editing), record the full performance metrics (banned word count, cognitive verb count, throat-clearing count, binary contrast count, em-dash density) in the run's `walkthrough.md` artifact.

## Literary Analysis & Prose Refactoring

When evaluating, scoring, or refactoring narrative chapters (`chapters/*.md`):

- Trigger the `literary-analysis` skill (`C:\GitHub\sr6-core\.agents\skills\literary-analysis\SKILL.md`).
- Execute sub-skills as required:
  1. `stage1_thematic_centering` for moral axis, SRM lore alignment, and exploring "the spaces between" (human condition via digital/spiritual phenomenology).
  2. `stage2_quality_benchmarking` for 1-10 literary scoring & artistic elevation of Shadowrun mechanics.
  3. `five_dimensional_scoring_matrix` for 1-100 metric evaluation across Concept, Prose, Characterization, Structure, and Meatspace/Matrix friction.
  4. `apply_prose_chisel` for line-level techno-poetic refactoring.
- **Walkthrough Metrics Logging:** Whenever `literary-analysis` is invoked, capture and record all scores, sub-skill metrics, and the 5D scoring matrix breakdown in the run's `walkthrough.md` artifact.

## Workspace Diagnostic & Automation Utilities

Before completing edits or reviewing narrative/character updates, run the corresponding `sr6` CLI subcommands:

- **Prose & Markdown Linter:** Run `sr6 lint "chapters/<file>.qmd"` to get instant diagnostics on markdownlint syntax formatting, em-dash density, cognitive verbs, banned words, and sentence length cadence.
- **Continuity Engine:** Run `sr6 continuity .` to index character relationships, sprite states, locations, and narrative heatmaps into `reference/story_continuity.md`.
- **Dossier & Ledger Auditor:** Run `sr6 characters audit yuriko` or `sr6 sync-all` to verify Karma/Nuyen balance consistency, Submersion grade calculations, and registered sprite limits against SRM rules.
