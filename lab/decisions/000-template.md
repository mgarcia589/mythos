<!--
ADR template. Copy this file with:
  cp lab/decisions/000-template.md lab/decisions/NNN-short-slug.md

Sequential 3-digit numbering. kebab-case slug.
Delete this comment block before committing the real document.
-->

# ADR NNN — [Decision title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Superseded by ADR-NNN | Deprecated
<!-- Status holds exactly one of those four values, no free text. Anything else
(date accepted, implementation notes, scope) goes on its own metadata line
below the header, e.g. **Implemented:** ... — keep Status parseable.
See lab/decisions/README.md for the full lifecycle. -->

## Context

[What problem or situation forced this decision. What made it necessary now
rather than later. An ADR without clear context is one nobody will understand
in six months — including future-you.]

## Decision

[What was decided, in one or two clear sentences. If it takes more than a
paragraph to state, it's probably two decisions — split them into two ADRs.]

## Alternatives considered

### Alternative A — [name]

[Brief description. Why it was rejected — the rejection reasoning matters more
than the description; it documents which criteria actually governed the choice.]

### Alternative B — [name]

[Brief description. Why it was rejected.]

## Consequences

**Positive:**

- [What this decision buys. Expected benefits, measurable where possible.]

**Negative / accepted costs:**

- [What this costs. What's given up. Risks knowingly accepted.]

**Future review triggers:**

- [What event or metric should trigger revisiting this. E.g. "if the codebase
  gains other contributors", "if module X needs to support Y".]

## Related specs / ADRs

- Related spec(s): [lab/specs/..., if applicable]
- Extends / requires first: [ADR-NNN, if applicable]
- Superseded by / supersedes: [ADR-NNN, if applicable]
- Related: [ADR-NNN, if applicable]

## Notes

[Optional. Anything else worth preserving: prior conversations, external
references, links to prototypes or analysis that informed the decision.]
