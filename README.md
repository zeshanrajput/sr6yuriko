# Shadowrun 6e Portfolio - Yuriko Star

This repository contains the interactive character dossier, downtime tracking system, rules cheatsheets, and narrative log for **Yuriko Star v9** (r31k0 Takahashi), an AI-Pilot character built for Shadowrun 6th Edition (Sixth World).

The project is compiled into a polished, responsive book using **Quarto** and hosted on GitHub Pages.

---

## Project Structure

- `scripts/`: Python utility scripts (including `main.py` and the parsing engines) that dynamically parse character exports (XML/JSON) to generate updated cheatsheets and markdown summaries.
- `chapters/`: The source files for the Quarto book:
  - `identity_core.qmd`: Metatype, stream, attributes, matrix, living persona stats, and skill matrix.
  - `character_sheet.qmd`: Embeds the generated plain-text VTT-formatted character sheet.
  - `rules_and_downtime.qmd`: Fading calculations, rigger/decking shortcuts, and network setups.
  - `character_log.qmd`: Complete run history, karma trackers, nuyen ledgers, and contact lists.
  - Narrative Chapters (`01 The Weight of Zero.md`, etc.): Out-of-session narrative archives.
- `input/`: Character source files (XML export from Chummer6/Genesis and Foundry JSON datasets).
- `output/`: Holds the compiled text character sheet (`character_sheet.txt`).
- `rules_vault/`: Rules database containing text rules used by the parsing script.
- `reference/`: Miscellaneous project reference docs, including [narrative_standards.md](file:///c:/GitHub/sr6yuriko/reference/narrative_standards.md) (the two-stage review framework and digital-native style conventions).

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
