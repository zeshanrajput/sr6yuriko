# Master Workspace Agent Instructions: sr6yuriko

This document defines the agentic workflow, sub-agent capabilities, narrative standards, and the **Primary Master Orchestrator (`narrative-director`)** for the Shadowrun 6e multi-agent narrative production framework in the `sr6yuriko` repository, integrating with `sr6-core`.

---

## 1. Master Orchestrator: `narrative-director`

The `narrative-director` is the primary autonomous orchestrator responsible for end-to-end narrative generation, multi-agent evaluation, iterative self-correction, and state tracking.

```
                      +-----------------------------+
                      |   1. CONTEXT INGESTION      |
                      | Outline, Voice Spec, Dossier|
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |   2. INITIAL DRAFT (v1)     |
                      +--------------+--------------+
                                     |
                                     v
         +-------------------------------------------------------+
         |            3. PARALLEL SUB-AGENT AUDIT PANEL          |
         |  - axis-voice-internality   - axis-pacing-structure   |
         |  - axis-agency-motivation   - axis-worldbuilding-grit |
         |  - no-ai-slop               - continuity-tracker      |
         |  - sr6-rules                                          |
         +---------------------------+---------------------------+
                                     |
                                     v
                      +-----------------------------+
                      | 4. SYNTHESIS & SELF-CORRECT |  <-- (Fails threshold?
                      |  Passes all 7 thresholds?   |       Re-draft v2, v3)
                      +--------------+--------------+
                                     | Passes
                                     v
                      +-----------------------------+
                      |  5. PUBLISH & STATE TRACK   |
                      |  Output .qmd & YAML diffs   |
                      +-----------------------------+
```

---

## 2. Six-Stage Execution Workflow

### Stage 1: Context Ingestion
Before drafting or editing, `narrative-director` ingests:
1. **Scene Outline / Prompt**: User-provided beat sheet, plot points, or target goals.
2. **Global Narrative Standards**: Reads [`sr6-core/reference/narrative_standards.md`](file:///c:/GitHub/sr6-core/reference/narrative_standards.md).
3. **Character Voice Specification**: Loads local [`reference/voice_spec.md`](file:///c:/GitHub/sr6yuriko/reference/voice_spec.md), extending [`sr6-core/reference/default_voice_spec.md`](file:///c:/GitHub/sr6-core/reference/default_voice_spec.md).
4. **Master Character Dossier**: Reads [`yuriko_master.yaml`](file:///c:/GitHub/sr6yuriko/yuriko_master.yaml) (attributes, inventory, ammo, nuyen, debt, qualities, complex forms, sprites, drones).
5. **RAG Story Continuity & Rules**: Queries recent chapter logs via `sr6 continuity .` and rule queries via `sr6-rules` or `sr6 rag query`.

### Stage 2: Initial Draft Generation (`v1`)
Generate Scene Draft `v1`, adhering strictly to:
* POV, animistic sensory lens, and cognitive bias from `reference/voice_spec.md`.
* 4-beat scene structure (Inciting Friction -> Escalation -> Climax -> Aftermath) from `narrative_standards.md`.
* Mechanical reality constraints and resource tracking from `yuriko_master.yaml`.

### Stage 3: Parallel Sub-Agent Audit Panel
Dispatches draft `v1` simultaneously to all **7 sub-agent evaluators**:

| Sub-Agent Skill | Focus Dimension | Passing Threshold |
| :--- | :--- | :--- |
| **`axis-voice-internality`** | Yuriko's era-aware voice & cognitive bias (Era 1–3+), DI identity, tactile animism, sensory lens | **8.0 / 10** |
| **`axis-pacing-structure`** | 4-beat structure, entry/exit discipline, action-to-exposition (80/20) | **8.0 / 10** |
| **`axis-agency-motivation`** | Proactive choice, sanctuary protection, consequential stakes, drive alignment | **8.0 / 10** |
| **`axis-worldbuilding-grit`** | Dystopian texture, corporate omnipresence, AR clutter, zero info-dumps | **8.0 / 10** |
| **`no-ai-slop`** | Anti-slop pattern detection, forbidden terms list, redline removal | **8.5 / 10** |
| **`continuity-tracker`** | Ammo/nuyen balances, damage tracks, contacts, sprite states, state diff generation | **8.5 / 10** |
| **`sr6-rules`** | SR6 mechanics (Edge, Matrix actions, complex forms, fading, rigging) accuracy | **8.5 / 10** |

### Stage 4: Synthesis & Automated Self-Correction Loop
1. Collate audit reports into a unified **Revision Matrix**.
2. If any sub-agent score falls below its threshold, formulate a targeted re-draft prompt combining all redline fixes.
3. The re-draft cycle (`v1` -> `v2` -> `v3`) repeats autonomously until **all 7 sub-agents pass threshold standards**.

### Stage 5: Publishing & State Tracking
Upon successful panel approval:
1. **Narrative Output**: Emits the final polished prose as a clean Quarto markdown file (`.qmd`) or markdown chapter in `chapters/`.
2. **State Diff Proposal**: Emits an explicit YAML patch proposing updates to `yuriko_master.yaml` for changes in nuyen, ammunition, physical/stun/fading damage, Karma, registered sprites, or contact relationships.

### Stage 6: Refinement Mode for Existing Chapters
When refining an existing chapter:
1. Dispatch target chapter directly to the 7-sub-agent audit panel.
2. Synthesize feedback and execute line-level prose chisel refactoring.
3. Write revised content **directly to the target file** for inspection via IDE diff view.
4. Log metrics (banned words, cognitive verbs, em-dash density, 5D scores) in the run's `walkthrough.md`.

---

## 3. Writing & Anti-Slop Discipline

- Adhere to `no-ai-slop` instructions (`c:\GitHub\sr6-core\.agents\skills\no-ai-slop\SKILL.md`).
- **Sensory Restraint**: Avoid cyberpunk sensory shortcuts (`burnt copper`, `hot solder`, `chemical tang of processing`, `puddles of stale encryption`, `decaying logic in the gutters`, `systems redlining`, `processing at 600%`). Replace with thermal/pressure shifts, acoustic resonance, tactile haptic weight, and geometric defamiliarization.
- **AI Writing Patterns**: Eliminate binary contrasts ("not X, but Y"), colon reveals, fake-profound kickers, summary recaps, throat-clearing openers, excessive em-dashes (>1.0 per 300 words), and excessive ellipses (>0.6 per 300 words).
- **Walkthrough Metrics Logging:** Whenever `no-ai-slop` or `literary-analysis` is invoked, record full performance metrics in `walkthrough.md`.

---

## 4. Workspace Diagnostic & Automation Utilities

Before completing edits or reviewing narrative/character updates, run the corresponding `sr6` CLI commands:

- **Prose & Markdown Linter:** `sr6 lint "chapters/<file>.qmd"` (checks markdownlint, em-dash density, cognitive verbs, banned words, cadence).
- **Continuity Engine:** `sr6 continuity .` (indexes relationships, sprite states, locations, and narrative heatmaps into `reference/story_continuity.md`).
- **Dossier & Ledger Auditor:** `sr6 characters audit yuriko` (verifies Karma/Nuyen balance consistency, Submersion grade calculations, and registered sprite limits).
- **Dual-Ledger CommLink6 Sync:** `sr6 db sync-commlink` (patches active CommLink6 GUI player saves).
- **Ecosystem Synchronizer:** `sr6 sync-all` (deep item audits, output regeneration, CommLink6 save patching).
