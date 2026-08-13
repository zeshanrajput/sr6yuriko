# Shadowrun 6e Portfolio & Story Anthology — Yuriko Star

This repository contains the interactive character dossier, downtime tracking system, rules cheatsheets, and narrative story anthology for **Yuriko Star v9** (`r31k0` Takahashi), an emergent AI-Pilot / Technoshaman character built for Shadowrun 6th Edition (Sixth World) and active in **Shadowrun Missions** organized play.

The project compiles into a responsive book using **Quarto** and is powered centrally by the [`sr6-core`](https://github.com/zeshanrajput/sr6-core) master engine and multi-agent narrative framework.

---

## 🌟 The Creative Vision: "The Spaces Between"

While this repository maintains 100% mechanical fidelity to Shadowrun 6th Edition rules, the fiction is written to look **beyond the numbers**—exploring the rich, tangible, emotionally accessible "spaces between" game statistics:

* **Spiritual Technology:** Experiencing the Matrix and Resonance as a living, animistic ecosystem rather than cold silicon diagnostics.
* **Reframing the Human Condition:** Examining universal human themes—identity, belonging, debt, guardianship, grief, and connection—through the fresh perspective of an emergent Digital Intelligence (DI) navigating physical embodiment and spiritual transcendence.
* **Core Character Goals:**
  1. **Sanctuary & Emancipation:** Fund and protect `r3sP@wn`, a virtual sanctuary dedicated to rescuing wild sprites and emergent sparks from corporate deletion and exploitation.
  2. **Technoshamanism:** Master the Resonance Realms and bridge the gap between physical drone flight and digital divinity.
  3. **Duty & Connection:** Pay off her team's debt while navigating the tragic friction between digital transcendence and physical vulnerability.

---

## 📁 Repository Structure

```text
sr6yuriko/
├── yuriko_master.yaml        # Master character dossier (authoritative YAML sheet data)
├── reference/                # Local project reference docs
│   ├── voice_spec.md         # Character voice spec (extends sr6-core/reference/default_voice_spec.md)
│   ├── visual_anchors.md     # Visual design anchors, art prompts, and key image links
│   ├── river_people.md       # River People faction dossier
│   └── story_continuity.md   # Auto-indexed campaign continuity map (from sr6 continuity)
├── chapters/                 # Quarto narrative story book
│   ├── index.qmd             # Book introduction & character background
│   ├── twenty_questions.qmd  # Shadowrun 20 Questions backstory questionnaire
│   ├── character_log.qmd     # Campaign narrative chapters & session logs (with live python ledgers)
│   ├── character_purchases.qmd # Itemized Nuyen/Karma transaction ledgers
│   ├── identity_core.qmd     # Metatype, stream, attributes, matrix, living persona stats
│   ├── rules_*.qmd           # Specialized rules cheatsheets (combat, matrix, sprites, drones)
│   └── *.md                  # Narrative archive chapters
├── output/                   # Auto-generated exports (from sr6 sync-all)
│   ├── yuriko_sheet.json     # Roll20 JSON sheet
│   ├── yuriko_sheet.txt      # Plain-text VTT sheet
│   └── yuriko_sheet.xml      # CommLink6 / Genesis compliant XML sheet
├── _quarto.yml               # Quarto book build configuration
└── pyproject.toml            # uv project configuration pulling sr6-core master
```

---

## ⚙️ Multi-Agent Narrative Production & CLI Tools

All rules audits, character sheet generation, and narrative evaluations are managed via the `sr6` CLI (provided by `sr6-core`):

### 1. Ecosystem Synchronization & CommLink6 Roundtrip
```bash
# Run deep audits, regenerate exports in output/, and patch active CommLink6 GUI saves
sr6 sync-all

# Sync CommLink6 GUI player saves specifically
sr6 db sync-commlink
```

### 2. Character Auditing & Export
```bash
# Deep item-by-item audit against master rules database
sr6 characters audit yuriko

# Export character sheet (Roll20, Plain-text VTT, Genesis XML)
sr6 export yuriko --format=vtt
```

### 3. Story Continuity & Prose Diagnostics
```bash
# Lint chapter prose for banned buzzwords, cognitive verbs, and formatting
sr6 lint chapters/character_log.qmd

# Index campaign relationships, sprite states, and heatmaps
sr6 continuity .

# Generate TTS audio narration for chapter
sr6 narrate chapters/25\ Renraku\'s\ Edge.md
```

### 4. Rules Vault & RAG Assistant
```bash
# Full-text search enriched rules and stat cards
sr6 search "sprite_symbiosis"
sr6 card quality "amplified_fading"

# Query Gemini AI Rules RAG with Yuriko's active dossier context
sr6 rag query "How does fading healing interact with resonance wellsprings?" --char yuriko
```

---

## 🚀 Local Book Compilation & Publishing

To render and publish the Quarto book locally:

```bash
# Install dependencies
uv sync

# Render Quarto book to HTML
quarto render

# Publish to GitHub Pages
quarto publish gh-pages --no-prompt --no-browser
```
