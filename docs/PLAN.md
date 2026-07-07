# Implementation Plan — CloakBrowser Manager CLI/TUI

> **How to use**: Each task references a detailed implementation spec in `impl/`.  
> Feed the spec file to a subagent along with `SPEC.md` for full context.

## Task Dependency Graph

```
Phase 1 — Core Engine
======================
T01 (scaffolding)
 ├─→ T02 (database)
 ├─→ T03 (models) ──→ T04 (config)
 ├─→ T07 (utils)
 │
 └─→ T05 (browser_mgr) ←── T06 (cdp_mgr)
      │
      └─→ ALL Phase 2 tasks

Phase 2 — CLI
=============
T08 (cli main) ──→ T09─T13 (all CLI modules)
                    │
                    └─→ T14 (tui entry)

Phase 3 — TUI
=============
T14 (tui app) ──→ T15 (widgets) ──→ T16 (screens)

Phase 4 — Polish
================
T17 (tests + packaging)
```

---

## Task List

### PHASE 1: Core Engine

| ID | Task | Priority | Depends On | Spec File |
|---|---|---|---|---|
| T01 | Project scaffolding | P0 | — | `impl/01-scaffolding.md` |
| T02 | Core database module | P0 | T01 | `impl/02-database.md` |
| T03 | Core models (Pydantic) | P0 | T01 | `impl/03-models.md` |
| T04 | Core config module | P1 | T03 | `impl/04-config.md` |
| T05 | Core browser manager | P0 | T02, T03, T07 | `impl/05-browser-manager.md` |
| T06 | Core CDP manager | P0 | T03 | `impl/06-cdp-manager.md` |
| T07 | Core utilities | P0 | T01 | `impl/07-utils.md` |

### PHASE 2: CLI Commands

| ID | Task | Priority | Depends On | Spec File |
|---|---|---|---|---|
| T08 | CLI main entry + shared output formatting | P0 | T02-T07 | `impl/08-cli-main.md` |
| T09 | CLI profile commands (create/list/show/edit/delete/clone) | P0 | T08 | `impl/09-cli-profile.md` |
| T10 | CLI launch & stop commands | P0 | T08 | `impl/10-cli-launch-stop.md` |
| T11 | CLI list & status commands | P0 | T08 | `impl/11-cli-list-status.md` |
| T12 | CLI CDP commands (list/url/code/check) | P1 | T08 | `impl/12-cli-cdp.md` |
| T13 | CLI config & info commands | P1 | T08 | `impl/13-cli-config-info.md` |

### PHASE 3: TUI Dashboard

| ID | Task | Priority | Depends On | Spec File |
|---|---|---|---|---|
| T14 | TUI app shell + dashboard screen + keybindings | P1 | T02-T07 | `impl/14-tui-app.md` |
| T15 | TUI widgets (profile list, tag filter, detail panel, log panel) | P1 | T14 | `impl/15-tui-widgets.md` |
| T16 | TUI modal screens (create, edit, confirm, code snippet) | P1 | T15 | `impl/16-tui-screens.md` |

### PHASE 4: Testing & Distribution

| ID | Task | Priority | Depends On | Spec File |
|---|---|---|---|---|
| T17 | Tests, packaging, CI/CD, docs | P1 | T09-T16 | `impl/17-testing-polish.md` |

---

## Subagent Execution Strategy

### Strategy A: Sequential (recommended for Phase 1)

Execute tasks in dependency order. Each subagent gets:
- `SPEC.md` (business context)
- The task's `impl/` spec file (technical details)
- Read access to already-completed source files before coding

```
→ T01 → [T02, T03, T07] (parallel if 3 agents)
       → T04
       → [T05, T06] (parallel)
```

### Strategy B: Parallel by Phase

After Phase 1 is complete, all Phase 2 CLI tasks (T09-T13) can run in parallel
since they only depend on the core engine, not each other.

### Subagent Task Template

```
Task: <task description from IMPL file>
Context:
  - Read SPEC.md for overall vision and architecture
  - Read impl/<task-id>.md for detailed implementation spec
  - Read existing source files in src/cloakbrowser_manager_cli/ for context
  - IMPORTANT: all imports must use the package prefix "cloakbrowser_manager_cli."

Deliverable:
  - Create/update source files as specified
  - Ensure all imports are correct and consistent
  - Run the module's tests if any exist
  - Report any blockers or questions
```

### Files That Must Stay in Sync

These files are touched by multiple tasks — read before editing:

| File | Read by tasks |
|---|---|
| `src/cloakbrowser_manager_cli/__init__.py` | T01 |
| `src/cloakbrowser_manager_cli/core/models.py` | T03, T04, T05, T06, T09, T15, T16 |
| `src/cloakbrowser_manager_cli/core/database.py` | T02, T05, T09, T11 |
| `src/cloakbrowser_manager_cli/core/config.py` | T04, T13 |
| `src/cloakbrowser_manager_cli/core/browser_manager.py` | T05, T10, T11, T14 |
| `pyproject.toml` | T01, T17 |
