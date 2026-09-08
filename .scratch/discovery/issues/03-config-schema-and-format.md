# Config file schema & format

Type: grilling
Status: open
Blocked by: 01, 02

## Question

Define the plumber config file — the artifact both a human and the AI skill
author.

- Format: YAML or TOML. Pick one; note why.
- Schema: pipeline name; input block (format, CRS, geometry type); ordered phase
  list with per-phase params and per-phase constraints; execution block
  (strategy, partition spec — by field(s) / chunk size / worker count).
- How phase identity in the config maps to discovered modules (depends on 01).
- What is a CLI flag vs. a config key: executor and scale live on flags and
  override config; params live in config. Nail the override precedence.
- Validation: is the config schema-checked on load, and by what (pydantic /
  plain dataclass + manual checks)?

Output: an annotated example config plus the field list and override rules.
