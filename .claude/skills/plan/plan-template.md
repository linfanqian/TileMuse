# <Feature> Plan

Issue: #<n> · Branch: `<type>/<person>-<issue#>-<short-name>`

## Context
- What exists today and what's missing (cite `path:line`).
- Pipeline stage(s) touched: LLM spec / spec schema / generator / export / validator / explainer / API / editor UI.

## Requirements
- Must-have behaviors, as testable statements.
- Out of scope: what this change deliberately does not do.

## Design Decisions
### 1. <Decision>
Chose <approach> because <reason>. Alternative considered: <alt> (rejected because <reason>).

## Technical Design
- Interfaces and data models, with signatures and type hints (Pydantic models, TS types, API request/response shapes).
- Data flow through the pipeline, if it changes.

## Files Changed
The only files this change should touch:
- `backend/app/x.py` (lines 23-49): <what changes>
- `frontend/src/y.tsx` (new): <purpose>

## Implementation Steps
1. <Small step that leaves tests green>
2. <Next step>

## Testing
List each test case by name and what it asserts.
- Generator: fixed-seed test asserting identical output.
- Validator: for each rule, one passing map and one violating map.
- Other: <unit/integration cases>. Avoid heavy mocking. Mock only the Claude API.

## Open Questions
- <Unresolved items that need the user's or teammate's input>
