# Packaging, distribution & "run from any repo"

Type: grilling
Status: open
Blocked by: —

## Question

Decide how plumber is installed and how it locates a target repo's phases and
config when invoked from that repo's working directory.

- Distribution: pipx-installed global tool (like `ruff`/`pytest`) vs. a dev
  dependency each pipeline repo adds vs. both. "Run from any repo" leans global.
- Discovery root: cwd-relative? a `plumber.toml` / `pyproject.toml [tool.plumber]`
  marker at the repo root? an explicit `--config` path?
- Console-script entry point name (`plumber`), subcommand surface (`run`,
  `check`, later `new-phase`).
- Dev environment for the plumber repo itself: match maply's Nix + `uv` +
  `direnv` setup, or simpler? Python version floor (maply targets 3.9–3.12).
- Packaging backend (hatchling, like maply) and versioning approach.

Output: the install story, the discovery rules, and the plumber repo's own dev
setup.
