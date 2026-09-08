# AI skill boundary

Type: grilling
Status: open
Blocked by: 03, 05

## Question

Fix the boundary of the optional AI skill under `ab_spatial/.claude/` — not its
conversation flow.

- Inputs it reads from plumber: the `PhaseModule` / `ExecutionStrategy`
  Protocols, `plumber check` output, the config schema. How does it get them —
  import plumber, shell out to `plumber check --json`, read a schema file?
- Outputs it emits: the config file (writes/updates it), and rework
  recommendation text for protocol/partition issues. Anything else? Does it ever
  write into the target repo's phase modules? (Constraint says no — confirm and
  record.)
- Invocation: slash-command name, and what triggers it (explicit only, or also
  on some condition).
- Degradation: enumerate exactly what a human does by hand when the skill is
  absent, to confirm nothing is skill-only.
- Dependency direction: skill depends on plumber; plumber never imports or knows
  about the skill.

Output: an inputs/outputs/invocation spec for the skill, ready for its own later
effort to design the conversation.
