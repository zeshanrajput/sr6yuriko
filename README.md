# Shadowrun 6e Portfolio & Story Anthology — Yuriko Star

This repository contains the interactive character dossier, downtime tracking system, rules cheatsheets, and narrative story anthology for **Yuriko Star v9** (`r31k0` Takahashi), an emergent AI-Pilot Technoshaman character built for Shadowrun 6th Edition (Sixth World) and active in **Shadowrun Missions** organized play.

The project is compiled into a polished, responsive book using **Quarto** and hosted on GitHub Pages.

---

## The Creative Vision: "The Spaces Between"

While this repository maintains 100% mechanical fidelity to Shadowrun 6th Edition rules, the fiction is written to look **beyond the numbers**—exploring the rich, tangible, emotionally accessible "spaces between" game statistics:

* **Spiritual Technology:** Experiencing the Matrix and Resonance as a living, animistic ecosystem rather than cold silicon diagnostics.
* **Reframing the Human Condition:** Examining universal human themes—identity, belonging, debt, guardianship, grief, and connection—through the fresh perspective of an emergent AI entity who must manually paint a smile to communicate with her human companions.
* **Core Character Goals:**
  1. **Sanctuary & Emancipation:** Fund and protect `r3sP@wn`, a virtual sanctuary dedicated to rescuing wild spirits and emergent AIs from corporate deletion and exploitation.
  2. **Technoshamanism:** Master the Resonance Realms and bridge the gap between physical drone flight and digital divinity.
  3. **Duty & Connection:** Pay off her team's debt while navigating the tragic friction between digital transcendence and physical vulnerability.

---

## Project Structure

- `scripts/`: Python utility scripts (including `main.py` and the parsing engines) that dynamically parse character exports (XML/JSON) to generate updated cheatsheets and markdown summaries.
- `chapters/`: The source files for the Quarto book:
  - `identity_core.qmd`: Metatype, stream, attributes, matrix, living persona stats, and skill matrix.
  - `character_sheet.qmd`: Embeds the generated plain-text VTT-formatted character sheet.
  - `rules_and_downtime.qmd`: Landing hub for downtime protocols and quick stats.
  - `rules_matrix.qmd`: ASDF attributes, action pools, decking cheat sheet, and remote host specs.
  - `rules_sprites.qmd`: Complex forms, compiling/registering downtime formulas, and focus fading calculations.
  - `rules_drones.qmd`: Drone stat blocks, action pools, rigger/remote attribute mapping, and sensor locks.
  - `rules_combat.qmd`: Weapon attack tables, link-fired arrays, laser ammo, and Krime splash ammo.
  - `character_totals.qmd`: Live dashboard for Karma/Nuyen balances, regional Reputation, and Active Sprite stable.
  - `character_log.qmd`: Complete run history, mission briefs, GM notes, and campaign rewards.
  - `character_purchases.qmd`: Itemized purchase ledgers for gear, software, drone mods, and SINs.
  - `dronomancy.md`: DI-to-DI guide on remote drone operation, casemodding, and rigging mechanics.
  - `twenty_questions.qmd`: Character questionnaire detailing personality and ethics.
  - Narrative Chapters (`01 The Weight of Zero.md`, etc.): Out-of-session narrative archives.
- `input/`: Pre-processed raw character exports (`Yuriko Star.xml`, `Yuriko Star.json` from Genesis/Commlink).
- `output/`: Post-processed calculated artifacts (`character_sheet.txt`, `Yuriko Star.json`, `Yuriko Star.xml`) generated with true Karma, Nuyen, and career ledger data.
- `rules_vault/`: Rules database containing text rules used by the parsing script.
- `reference/`: Miscellaneous project reference docs, including [visual_anchors.md](reference/visual_anchors.md) (master visual design anchors, key image links, and prompt templates), [narrative_standards.md](reference/narrative_standards.md) (review framework and digital-native conventions), and [river_people.md](reference/river_people.md) (faction dossier).

---

## The Rules Vault (`rules_vault/`)

The rules engine dynamically references snippets in the `rules_vault/` directory to build footnotes and verification blocks.

> [!IMPORTANT]
> **Copyright & `.gitignore`**
>
> To respect copyright laws, the `rules_vault/` directory is **git-ignored by default** (except for the publicly available Shadowrun Missions Guide files, `SRMG-*.md`).
>
> If you clone this repository, you must populate the vault locally with your own rulebook extractions (e.g. `6WB-*.md` for *Sixth World Book*, `WN-*.md` for *Wild Blue*, etc.) parsed from your purchased PDFs.

---

## Local Development & Compilation

To generate the sheets and build the book locally:

1. **Setup Dependencies**: Ensure you have Python and `uv` installed.

   ```bash
   uv sync
   ```

2. **Build the Dossier**: Run the script to parse your inputs and output the VTT character sheet.

   ```bash
   uv run python scripts/main.py "input/Yuriko Star v9.json" --output "output/character_sheet.txt"
   ```

3. **Compile the Quarto Book**: Render the project locally.

   ```bash
   quarto render
   ```

4. **Publish**: Publish the output to your `gh-pages` branch.

   ```bash
   quarto publish gh-pages --no-prompt --no-browser
   ```
