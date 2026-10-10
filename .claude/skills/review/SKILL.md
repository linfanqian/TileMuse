---
name: review
description: Reviews TileMuse changes (the current branch against main, uncommitted work, or a PR number) for correctness, the CLAUDE.md invariants, and plan conformance, and returns a prioritized action list. Read-only. Use when the user asks for a review of changes, a branch, or a PR, after /implement, or on /review.
argument-hint: "[PR# | base-ref]"
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git show *), Bash(git rev-parse *), Bash(git merge-base *), Bash(gh pr view *), Bash(gh pr diff *), Bash(gh issue view *), PowerShell(git status *), PowerShell(git diff *), PowerShell(git log *), PowerShell(git show *), PowerShell(git rev-parse *), PowerShell(git merge-base *), PowerShell(gh pr view *), PowerShell(gh pr diff *), PowerShell(gh issue view *)
---

## Usage

```
/review                           # current branch + uncommitted work vs main
/review 27                        # teammate's PR #27
/review HEAD~3                    # only the last 3 commits
```

Review the changes and produce a prioritized action list. Do not edit any files.

Target: $ARGUMENTS

## 1. Collect the diff

- If the target is a PR number, run `gh pr view <n>` and `gh pr diff <n>`.
- Otherwise review the current branch: only the commits it added since the base ref (default `main`), plus uncommitted work. Collect `git log --oneline <base>..HEAD`, `git diff <base>...HEAD`, and the uncommitted changes (`git status --porcelain`, `git diff HEAD`).
- If the diff is empty, say so and stop.

Read every changed file in full, not just the hunks, plus the callers and tests of anything you change.

## 2. Find the plan

Look for `plans/<issue#>-*.md`, matching the issue number in the branch name or PR. Plans are local and never committed, so a teammate's PR usually has none. In that case use the linked issue (`gh issue view <n>`) as the spec. If neither exists, skip the plan axis and say so.

## 3. Review on three axes

**Correctness.** Logic bugs, missed edge cases (empty or 1×1 maps, maps without doors, out-of-range GIDs), error handling at the API boundary, type mismatches between the frontend and backend contracts, and tests that can't fail (tautological or over-mocked).

**Project rules** (`CLAUDE.md`). Check each and cite the rule you apply:
- The LLM produces only the spec, never tiles or maps.
- Spec validation (Pydantic) and map validation (gameplay rules) stay separate.
- The validator runs after generation and after every edit, and returns `Violation` objects.
- The generator is deterministic: the seed is required, the RNG is passed explicitly, and there's no global or unseeded randomness (`random.*` at module level, `Math.random`, set or dict ordering that affects output).
- The explainer is template-based, one template per violation code. LLM polish only rephrases, and the templates are the fallback.
- Claude API calls and the key exist only in `backend/`. Nothing logs or commits secrets.
- Generator changes come with a fixed-seed test. Validator rules each have a passing map and a violating map.
- Dependencies are added via `uv add`, never pip.
- Nothing under `plans/` is committed.
- The code works on both Windows and macOS. Look for hardcoded `\` separators or drive letters instead of `pathlib`/`path`, shell-specific scripts in `package.json` or docs, and import or file names whose case differs from the file on disk.

**Plan conformance.** Requirements that are missing or only partly done, files changed outside the plan's Files Changed list, and behavior nobody asked for (scope creep). Quote the plan line for each finding.

Skip formatting and lint issues that ruff, oxlint, and Prettier already enforce.

## 4. Report

```
## Code Review

Scope: <base..HEAD or PR #n>, <n> files · Plan: <path or "none">

Summary: <1-2 sentences>

Action Items:
1. 🔴 <must-fix: bug, invariant break, or missing required test> in `path:line`. <why>
2. 🟡 <recommended> in `path:start-end`. <why>
3. 🟢 <consider> in `path:line`. <why>
```

Order the items by severity. Report only issues you checked against the code. If you're unsure, say so instead of guessing. If there are no 🔴 items, say so explicitly.
