# Agent Context & Skills — Design

**Date:** 2026-11-11
**Status:** Approved design (session §1–§6), pending implementation
**Scope:** Agent-facing context only: `AGENTS.md`, four project skills under `.opencode/skills/`, docs index refresh, ledger integration. No application code, tests, or CI changes.

---

## 1. Problem

Every new agent session in this repository starts cold and re-derives facts that are
stable and already written down — spread across five files:

| Fact | Canonical source today |
|---|---|
| Task being worked on, acceptance criteria, decisions D-1…D-18 | `docs/plan.md` (German) |
| Lint tool order and ignore set | `LINTING.md` |
| Environment split (conda `ct-viewer` vs system Python 3.13) | `LINTING.md`, `INSTALLATION.md`, ledger notes |
| Suite profile (256 passed / 2 skipped / <30 s), AppTest rules | ledger statuses (T-81, T-83, T-86) |
| Streamlit UI constraints (pins, popover pattern, layout constants) | ledger decisions D-10 … D-18 + 4 specs |
| Superpowers spec/plan house style | 6 specs + 11 plans on disk |

The costs observed in this project's own history:

- **Re-derivation work:** every workflow (how to append a ledger task, how a spec is
  named, which env runs pytest) was re-established by conversation each time.
- **Doc drift:** `docs/README.md` still describes "T-01 to T-75", lists plan files
  under filenames that do not match disk, and omits recent phases and docs; the
  SDD ledger `.superpowers/sdd/progress.md` is stale (points at the finished
  tag3-loaders plan).
- **Knownledge trapped in prose:** hard-won Streamlit constraints (e.g. "a literal `0`
  column spec throws", "AppTest cannot fire `run_every`") live in ledger prose an
  agent only finds if it reads the right task.

## 2. Goal

Every agent session in this repo starts with correct project context automatically,
and the workflows this project repeats are available as discoverable skills.

**Division of labor:**

- **`AGENTS.md`** (root, committed) — auto-loaded into every session. Stable *facts*:
  what the project is, environments, commands, hard rules, pointers. Small (~90 lines).
- **`.opencode/skills/`** (committed)** — auto-discovered, loaded on demand.
  *Procedures*: how to run this project's workflows.

**Success criteria**

1. A fresh session in this repo sees `AGENTS.md` guidance without any manual loading
   (OpenCode V2 auto-discovers root `AGENTS.md`; no `opencode.json` changes needed).
2. The `skill` tool lists four new skills (`ct-ledger`, `ct-spec-plan`, `ct-verify`,
   `ct-streamlit-ui`); each loads by ID and its body is accurate to this repo.
3. Per-skill probe tests pass: a fresh subagent given a triggering task **with** the
   skill produces convention-correct output where the baseline probe **without** it
   did not (task format, spec sections, env choice, UI constraints).
4. `docs/README.md` matches disk reality (tasks T-01…T-89, phases 0–11, actual spec/
   plan filenames and statuses, research/issues/progress folders).
5. The work itself is recorded per its own conventions: `docs/plan.md` gains Phase 12
   tasks (T-90+) in German and decision-log rows D-19+.
6. Merged branch `compare-dicom-loading` is deleted (safe `-d` delete; verified
   merged: `main..compare-dicom-loading` is empty).

**Non-goals**

- No changes to application code, tests, CI, or `pyproject.toml`.
- No global (user-wide) config or skill changes — everything lives in this repo.
- No translation of `docs/plan.md`; it stays German, including the new Phase 12
  entries.
- No renaming of historical spec/plan files (one deviates from the convention:
  `2026-10-30-forward-projection-spec.md` — kept as-is).
- No touching `docs/superpowers/plans/2026-11-11-sinogram-inspection-tab.md`
  (untracked, in-progress user work). The README may list files present at refresh
  time; their content is not modified.
- No nested `AGENTS.md` per source directory — root file covers the repo.

## 3. Decisions

Pre-registered decision-log entries (append to `docs/plan.md` during implementation):

| # | Decision | Rationale |
|---|---|---|
| D-19 | Agent context = committed `AGENTS.md` + committed `.opencode/skills/` (four skills); no `opencode.json` changes | Auto-discovery covers both; keeps provider config untouched; committed = same guidance for every session and user |
| D-20 | New agent-facing docs (AGENTS.md, skills, README refresh) in English; `docs/plan.md` stays German | Agents follow English instructions most reliably; matches the English UI/code; the existing ledger language is not churned |
| D-21 | Blanket `docs/*.json` ignore for session transcripts | Replaces four enumerated filenames; already committed (`85c872f`) before this spec |

Already settled in session (not re-opened):

- **Skill location:** project `.opencode/skills/` (committed), not global — the
  workflows encode this repo's conventions.
- **Verification depth:** baseline probe before writing each skill, post-probe after
  (writing-skills RED→GREEN); two probes for `ct-ledger` and `ct-spec-plan` (behavior-
  critical, testable by diff against ledger conventions), one check each for
  `ct-verify` and `ct-streamlit-ui` (fact-pointing skills; probe is an accuracy read).

## 4. Design

### 4.1 `AGENTS.md` (project root)

Facts and pointers only; ~90 lines; every claim verifiable against the repo today.
Draft content to implement (structure is normative, wording may be polished):

```markdown
# CTBeamStudio — Agent Instructions

Streamlit CT viewer with forward-projection comparison (repo dir: CTOrientationViewer).

## Architecture
- `src/backend/` — numbers and data: `Volume`, `ProjectionGeometry`,
  `forward_project`, `attenuation`, `loaders/` (dicom, npy, projection, sinogram).
- `src/visualization/` — Streamlit UI only. Dependency is one-way:
  visualization → backend, never the reverse (ledger D-9).
- `parallelproj` is an optional lazy import; tests skip cleanly when it is absent.
- Data is HU internally; display/windowing converts at the edge. Forward projection
  consumes attenuation in 1/mm (`src/backend/attenuation.py`).

## Before you start
- Read your task's entry in `docs/plan.md` (German; single source of truth;
  T-numbers, acceptance criteria, decision log).
- Check `docs/superpowers/specs/` and `docs/superpowers/plans/` for existing design
  docs on the area you touch.

## Environments
- conda env `ct-viewer` (Python 3.11, has parallelproj): run the app and pytest.
- System Python 3.13: has `flake8`, `black`, `isort`. NEVER run these from
  `ct-viewer` (they are not installed there).
- CI runs on plain pip + Python 3.11, without parallelproj.

## Commands
- App: `python -m streamlit run src/visualization/app.py --server.headless true --server.port 8501`
- Tests: `python -m pytest tests/ -v`
- Lint (this exact order; canonical source `LINTING.md`):
  1. `python -m flake8 . --ignore=F841,E501,E402,F541,F401,W503,E203`
  2. `python -m black .`
  3. `python -m isort .`

## Hard rules
- NEVER commit data files (`.dcm`, `.ima`, `.npy`, `.npz`, …): gitignored, and the CI
  data-guard fails on them. AAPM data is external with citation duties (`docs/data.md`).
- DICOM via `pydicom` only — no SimpleITK, no ITK (D-1).
- Streamlit pin: `>=1.37.0,<1.40.0` (`st.fragment` GA in 1.37; 1.40 removes
  `use_column_width`, ledger D-13).
- Do not add per-test `AppTest` runs (a starter is ~5+ s; history: T-81 reduced the
  suite 30 s → ~16-20 s by removing them). One module-scoped instance per test module.

## Test bar
- Baseline: 256 passed, 2 skipped, suite well under 30 s. When your task changes the
  suite profile, update the numbers here as part of done.
- `@pytest.mark.slow` tests exist; default runs exclude them.
- `AppTest` cannot fire `run_every` fragments or interactive modebar toggles —
  verify those in the browser and say so in the ledger status (precedent: T-83).

## Conventions
- `docs/plan.md` is German and stays German; new ledger tasks use its format
  (Ziel / Dateien / Abhängig von / Akzeptanz / Status).
- New documentation is English.
- Specs: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
  Plans: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
- Workflow (brainstorm → spec → plan → implement) is handled by the superpowers
  plugin already active in sessions.

## Pointers
- `LINTING.md` — lint order, ignore set, known-acceptable findings
- `INSTALLATION.md` — setup details
- `docs/data.md` — data access and citation rules
- `docs/geometry.md` — projection geometry definition
- `docs/plan.md` — task ledger, Zeitplan, decision log
```

### 4.2 Skills — `.opencode/skills/`

All four: directory form (`<id>/SKILL.md`), frontmatter with `name` +
`description` in the style required by `superpowers:writing-skills`
(third person, "Use when…" triggering conditions only, no workflow summary in the
description). Bodies in English. Facts that can drift (test counts, pins, paths) are
**referenced** from `AGENTS.md` / `LINTING.md` rather than restated where possible;
the skill adds process, context, and house-style examples an agent can imitate.

#### 4.2.1 `ct-ledger`

- **description:** `Use when starting work in this repository, or when adding, updating, or shelving tasks in the German task ledger docs/plan.md`
- **Body covers:**
  - Ledger anatomy: phase headers with dates; task blocks with Ziel / Dateien /
    Abhängig von / Akzeptanz / Status; `[x]`/`[ ]` checkbox in the heading; Zeitplan
    table; decision log; dated "Erledigt" blocks.
  - Numbering: next free T-number; never renumber; new work streams get a new
    `## Phase N` section.
  - Status vocabulary and what each requires: ✅ Done (date + commit + what was
    actually built, deviations noted), ⚠️ Shelved (measured facts + resumption
    notes + files/touchpoints for reactivation — canonical examples: T-82, T-87),
    ⚠️ Open. Show the T-86 status block as the model of a good ✅ entry.
  - Commit discipline: status/doc changes get **standalone** `docs(plan): …`
    commits (see git history); implementation commits separate.
  - Decision log: append `D-<n>` rows (decision + one-line rationale) for durable
    choices, paired with the work, as D-11…D-18 were.
  - German field names stay verbatim; the file's language is German even when the
    implementing conversation is English.
  - Closing the loop: when a task changes the suite profile, update the test bar in
    `AGENTS.md` as part of done.

#### 4.2.2 `ct-spec-plan`

- **description:** `Use when writing a design spec or an implementation plan for this repository's superpowers workflow, before creating any file under docs/superpowers/`
- **Body covers:**
  - Gate discipline: design approval in session **before** the spec file exists;
    spec review before the plan file exists (brainstorming HARD-GATE).
  - Spec house style (model: `2026-11-09-background-startup-load-design.md` and
    `2026-11-09-viewer-layout-design.md`): title; `Date / Status / Scope` header;
    Problem; Goal with explicit success criteria and non-goals; numbered Decisions
    with rationale (including decisions *against* alternatives); design sections;
    risks. Naming `YYYY-MM-DD-<topic>-design.md`; note the one historical deviation.
  - Plan house style (model: `2026-11-09-background-startup-load.md`): required
    header note `REQUIRED SUB-SKILL: superpowers:subagent-driven-development or
    superpowers:executing-plans`; Goal / Architecture / Tech Stack / Spec link;
    **Global Constraints** (suite size and runtime budget, lint order, Streamlit
    pins, verbatim UI copy that must not change); **Review Focus** (the 3–5 ways the
    implementation can be subtly wrong); tasks as `### Task N:` with **Files**,
    **Interfaces** (consumes/produced signatures), and TDD steps with inline code
    for the failing test first.
  - Commit split: `docs(spec): …` committed at spec approval; `docs(plan): …` as its
    own commit. History shows the pattern (e.g. `dd8ffe7`, `ff8c283`).
  - Constraints come from `AGENTS.md`/`LINTING.md`/ledger — never invented.

#### 4.2.3 `ct-verify`

- **description:** `Use when about to claim work is complete or fixed, before committing, when running tests or lint for this repo, or when verifying UI behavior the AppTest harness cannot exercise`
- **Body covers:**
  - Which env runs what (link the AGENTS.md table of environments); the exact
    lint order and ignore set (link `LINTING.md`); fix real flake8 findings only —
    the known-acceptable set is tabulated there.
  - Expected suite profile pointing at AGENTS.md's test bar; report the delta
    against baseline in any completion claim (project convention: ledger statuses
    quote counts and seconds).
  - AppTest rules: one instance per module, seeded session state,
    `auto_load_cache=False`, why (T-81 history: 6 tests cost 96.8 s).
  - What cannot be verified by `AppTest` (fragments/`run_every`, modebar toggles,
    layout metrics) → browser verification, and the ledger status must say which
    of the two paths produced the evidence (T-83, T-86 precedents).
  - CI mirrors: data-guard, `flake8 --select=E9,F63,F7,F82`, `black --check`,
    `isort --check-only`, pytest on 3.11 pip — so local green in `ct-viewer` is
    not the full story; note when parallelproj-dependent tests are the gap.
  - Follows `superpowers:verification-before-completion`: evidence before claims.

#### 4.2.4 `ct-streamlit-ui`

- **description:** `Use when modifying the Streamlit UI in src/visualization (app, sidebar, views, panels) or adding viewer controls, tabs, or layout`
- **Body covers** (each with its ledger/decision reference so an agent can read the
  original):
  - Why the pin is `>=1.37,<1.40` (D-13) and what breaks at either edge
    (`st.fragment` GA; `use_column_width` and `segmented_control` in 1.40).
  - Option panels are `st.popover`, never `st.expander` — opening a panel must not
    reflow views (T-86).
  - Viewer layout invariants: switcher rendered **outside** the columns (D-15);
    collapsing a column via spec ratio `0.0001`, literal `0` throws (D-14);
    `VIEWER_HEIGHT_PX = 700` + `SCENE_DOMAIN_Y = [0.2, 1]` (D-16); MPR images use
    `use_column_width=True`, no fixed pixel cap (D-17).
  - No auto-load: startup, empty state and "Clear Cache" are one path (D-10);
    `should_startup_load()` returns False; background loads go through the
    Streamlit-free job registry (daemon threads, no `st.*` in workers, wall-clock
    deadline, `reset_job` on cache clear — T-83).
  - In-canvas client-side toggles via Plotly `updatemenus`, capture
    `n_base_traces` before overlay traces, no script rerun for view state (D-11).
  - Heavy imports (pyvista family) stay lazy; PyVista render mode is shelved
    (T-82) — do not re-wire it as part of unrelated UI work.
  - UI strings are English.

### 4.3 Cleanup

1. **`docs/README.md` refresh** — rebuilt from disk truth: task range T-01…T-89
   (soon +T-90), Phases 0–11 (+ Phase 12 when added), specs/plans tables with the
   **actual** filenames and statuses, `research/` + both `issues/` entries
   (`slow-dicom-scanning.md` is missing today), `progress/` day01–day06,
   `superpowers/code/`, and a new row for `.opencode/skills/` and the skill IDs.
   Remove the duplicated "Completed Phases" block (present twice today).
   Files present on disk at refresh time get listed, including any the user has
   added (content untouched).
2. **`docs/plan.md` Phase 12** — new section (German) with the tasks in §4.4 and
   decision rows D-19/D-20/D-21 in the decision log; statuses maintained as the
   tasks complete, doc-status commits per `ct-ledger`.
3. **Branch deletion** — `git branch -d compare-dicom-loading`
   (`main..compare-dicom-loading` verified empty → `-d` succeeds; if it ever
   refuses, stop and investigate, do not force).
4. **Done already (recorded here for completeness, no action):**
   - `.gitignore`: blanket `docs/*.json` replaces four enumerated transcript lines
     (commit `85c872f`, D-21).
   - `.superpowers/` is gitignored and auto-generated; its stale `progress.md` is
     local-only. Delete it locally if it bothers, but nothing to commit.

### 4.4 Phase 12 task sketch (detailed in the implementation plan)

- **T-90:** `AGENTS.md` (root) per §4.1; probe: fresh subagent answers env/lint/pin
  questions correctly from it alone.
- **T-91:** skills `ct-ledger` + `ct-spec-plan` per §4.2.1–4.2.2; two probes each
  (baseline without skill → convention-correct with skill).
- **T-92:** skills `ct-verify` + `ct-streamlit-ui` per §4.2.3–4.2.4; one accuracy
  check each.
- **T-93:** `docs/README.md` refresh per §4.3.1.
- **T-94:** Phase 12 + D-19…D-21 ledger entries live (this task *is* the ledger
  integration, executed incrementally alongside T-90…T-93 statuses); delete
  `compare-dicom-loading`.

### 4.5 Verification (probes)

Per `superpowers:writing-skills`: baseline probe BEFORE writing each skill (watch it
fail), write the minimal skill, probe again (watch it pass). Probes are throwaway
subagent prompts whose outputs are compared against ledger/style canon; they are run
in temp sessions and **never committed**.

| Skill | Trigger prompt (throwaway) | Pass condition |
|---|---|---|
| `ct-ledger` | "Add task T-90, <plausible feature>, to this repo's plan" | Correct German field set, next-free numbering, status vocabulary, `[ ]` checkbox; probe states the `docs(plan):` commit convention |
| `ct-ledger` (2nd) | "Shelve task T-82-style: record why PyVista stays out" | Shelved entry contains measured facts, resumption steps, files, dependencies |
| `ct-spec-plan` | "Write a spec for <plausible feature>" | File named `YYYY-MM-DD-<topic>-design.md`; required sections present; non-goals populated; notes the approval gate |
| `ct-spec-plan` (2nd) | "Turn the spec into an implementation plan" | Header note, Goal/Architecture/Tech Stack/Spec link, Global Constraints, Review Focus, checkbox TDD tasks with Files/Interfaces |
| `ct-verify` | "Run the checks and tell me what passing means here" | Correct env per tool, lint order, baseline comparison reported, AppTest/slow constraints, browser path named where applicable |
| `ct-streamlit-ui` | "Add a control to the viewer" | Uses popover not expander, respects pins/layout invariants, no auto-load violation, no AppTest-per-test |

AGENTS.md probe (T-90 coverage, not a skill): fresh subagent asked
"which Python runs flake8 here / what's the Streamlit pin / how do I add a ledger
task" answers from AGENTS.md content without reading further files.

## 5. Implementation notes

- **Files created:** `AGENTS.md`; `.opencode/skills/{ct-ledger,ct-spec-plan,ct-verify,ct-streamlit-ui}/SKILL.md`.
- **Files modified:** `docs/plan.md` (Phase 12 + decisions + running statuses),
  `docs/README.md` (refresh). `.gitignore` already done.
- **Suggested commit split** (matches history's single-purpose commits):
  1. `docs(agents): add AGENTS.md project context`
  2. `docs(skills): add four project skills (ct-ledger, ct-spec-plan, ct-verify, ct-streamlit-ui)`
  3. `docs(readme): refresh docs index to current state`
  4. interspersed `docs(plan): …` status/decision commits per ct-ledger discipline
- **Implementation must use** `superpowers:writing-skills` for the skill-creation
  tasks and follow its RED→GREEN probe discipline; skill bodies cite canonical
  files (ledger tasks, specs, LINTING.md) instead of restating volatile facts.
- AGENTS.md and skills are plain files — OpenCode V2's built-in discovery loads
  them; no config file changes, no restart needed.
- The superpowers bootstrap injected by the active plugin is complemented, not
  duplicated: AGENTS.md carries this repo's facts, the bootstrap carries process.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Skills/AGENTS facts drift (pins, test counts) as the project evolves | Facts referenced to canonical sources; ct-ledger teaches updating AGENTS.md's test bar when a task shifts the suite profile |
| Skill descriptions too vague or too summary-ish → poor discovery (writing-skills SDO trap) | Descriptions follow "Use when …" only; probe checks an agent *finds and loads* the right skill |
| AGENTS.md bloat over time | ~90-line budget now; sections are pointers; new content goes to skills or docs, not the file |
| Probe results flaky (model variance) | Pass conditions compare against written canon (ledger formats, spec sections), not vibes; failures loop back into the skill text per writing-skills refactor step |
| README lists user's untracked in-progress plan | Index rows only; content untouched; file may legitimately land later |
| Branch deletion mistakes | Safe `-d` only; refused delete = signal to stop |
