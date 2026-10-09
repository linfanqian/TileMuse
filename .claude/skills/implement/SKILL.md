---
name: implement
description: Implements a plan file from plans/ step by step, with checks and Conventional Commits on a feature branch. Use when the user asks to implement or execute a plan, or invokes /implement.
argument-hint: "[plan-file]"
disable-model-invocation: true
---

## Usage

```
/implement plans/12-door-rule.md
/implement                        # lists plans/ and asks which one
```

Run it after `/plan`. It runs `review` itself at the end.

Implement the plan in: $ARGUMENTS

If no plan path is given, list `plans/` and ask which plan to use. If there is no plan, suggest `/plan` first.

## Steps

1. **Read.** Read the whole plan and `CLAUDE.md`, then the files listed under Files Changed. If the plan has unresolved Open Questions that block the work, ask before starting.
2. **Branch.** Never work on `main`. If the current branch already matches the plan, stay on it. Otherwise create `<type>/<person>-<issue#>-<short-name>` from an up-to-date `main`. Ask for `<person>` if you can't tell it from the user's existing branches.
3. **Build in steps.** Follow the plan's Implementation Steps in order. For each step:
   - Write or update the step's tests first when the plan names them. The generator and validator always need tests, as `CLAUDE.md` Testing requires.
   - Make the change, then run the single relevant test file (`npx vitest run <file>` or `uv run pytest <file>`).
   - Commit when the step is green, using a Conventional Commit message (`feat: ...`, `fix: ...`, `test: ...`).
4. **Final checks.** Run the full check set for each side you touched:
   - Backend: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`
   - Frontend: `npm run lint`, `npx prettier --check .`, `npx tsc --noEmit`, `npm test`
   Fix any failures. Don't skip, disable, or weaken a test to make it pass.
5. **Review.** Run the `review` skill on the branch and fix every 🔴 finding. Report 🟡 and 🟢 findings to the user. Don't fix those unasked.
6. **Report.** Summarize what was done, how it was tested, and any deviations from the plan. Don't push or open a PR unless asked.

## Rules

- **Stay inside the plan.** Touch only the files in Files Changed. If you need a file or approach the plan doesn't cover, stop and explain why, then update the plan's Files Changed or Design Decisions before you continue. Small mechanical additions such as a missing `__init__.py` are fine; mention them in the report.
- Keep the `CLAUDE.md` invariants. If a step would break one, stop and ask.
- Match the surrounding code's style. No drive-by refactors or unrelated cleanups.
- The team develops on Windows and macOS. Use `pathlib`/`path` instead of hardcoded separators, keep `package.json` scripts shell-neutral, and match file-name case exactly in imports.
- Never commit anything under `plans/`. It is gitignored, so don't force-add it.
- Never read, print, or commit `backend/.env` or the API key. Tests mock the Claude API and never call it for real.
