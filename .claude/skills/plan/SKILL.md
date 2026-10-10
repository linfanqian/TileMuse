---
name: plan
description: Proposes 2-3 approaches for a TileMuse change, lets the user pick one, then drafts the implementation plan as plans/<issue#>-<short-name>.md without implementing it. Use when the user asks to plan a change or a GitHub issue, write a plan, compare approaches, or invokes /plan.
argument-hint: "<issue# | description>"
disable-model-invocation: true
---

## Usage

```
/plan 12                          # plan GitHub issue #12
/plan add a door-reachability rule to the validator
```

The flow is `/plan` → `/implement plans/<file>.md` → `/review`.

Plan the change described by: $ARGUMENTS

Do not write or edit any code. The only file you create is the plan. `plans/` is gitignored and must never be committed.

## Steps

1. **Intake.** If given an issue number, read it (`gh issue view <n>`). Restate the goal in one or two sentences.
2. **Research.** Read `CLAUDE.md`, then the code the change touches. Follow imports and read the related tests. Note existing patterns to reuse. Document what exists; don't redesign what you weren't asked to.
3. **Clarify.** Ask about anything that changes the design: scope, which pipeline stage owns the logic, data shapes, edge cases. Ask one question at a time and give your recommended answer with each. Stop when the open questions no longer affect the design. Don't ask what the code already answers.
4. **Propose.** Present two distinct approaches. Add a third only if it is a real contender, never as filler. Use this format:

   ```
   **Approach A: <name>**: <1-2 sentence overview>
   - Pros: <1-2 sentences>
   - Cons: <1-2 sentences>

   **Approach B: <name>**: ...

   **Recommendation:** <A or B>. <1-2 sentences, as an experienced engineer, on why it is the better choice here>
   ```

   Ground each approach in what step 2 found (cite `path:line`). Skip the pros or cons line if there truly are none. Then ask the user which approach to use, and wait for the answer before writing anything.
5. **Write the plan.** Write the chosen approach to `plans/<issue#>-<short-name>.md`, or `plans/<short-name>.md` if there is no issue. Follow the structure of [plan-template.md](plan-template.md). Record the rejected approaches in Design Decisions in one line each. Write short, actionable bullets, and delete sections that don't apply rather than leaving them as empty headings.
6. **Report.** Give the plan path, a three-line summary, and any open questions you couldn't resolve. Suggest `/implement <plan path>` as the next step.

## Rules

- Keep it minimal. Plan only what was asked. No speculative abstractions, config, or "future-proofing".
- Respect the pipeline in `CLAUDE.md`. No approach may bend an invariant: the LLM produces only the spec, the generator is deterministic and seeded, spec validation and map validation stay separate, the explainer is template-first, and the API key stays in the backend. If the request seems to require bending one, raise it with the user instead.
- **Files Changed** must list every file the change touches. Give line ranges for existing files. Implementation is held to this list.
- The test plan must follow `CLAUDE.md` Testing: a fixed-seed identical-output test for generator changes, and a passing map plus a violating map for each validator rule.
- The team develops on Windows and macOS. Plan commands, paths, and scripts that work on both: use forward-slash paths, `uv`/`npm` scripts rather than shell-specific one-liners, and no OS-specific tooling.
