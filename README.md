# SMY Memory CLI

SMY is a small, dependency-free command-line bridge for persistent memory across AI agents. It gives an agent a stable way to retrieve durable notes and, when explicitly requested, scan original session files directly. This separates shared memory mechanics from any one agent, model, MCP server, or personal rule set.

## What is published

This repository contains only the generic CLI, configuration example, tests, and usage guidance. It does **not** contain personal FMP rules, Basic Memory content, original sessions, credentials, tokens, account data, permission links, or machine-specific absolute paths. Full raw history remains in its original store; SMY scans and retrieves it directly and does not copy raw bodies into the SQLite index.

## Install

```bash
python -m pip install .
smy --help
```

Or run without installation:

```bash
python -m smy.cli --config ~/.smy/config.json health
```

Copy `config.example.json` to `~/.smy/config.json` and change the paths. `memory_roots` are durable Markdown/TXT notes that SMY indexes; `raw_roots` are original session directories that remain read-only and are searched only with `--raw`.

## Agent integration

Choose the path your actual agent can execute:

- Any agent with shell/exec: call `smy --config ... search "the user's original wording" --json`.
- Agents that support MCP may wrap this CLI with a local MCP adapter, but MCP is optional; the stable contract is the CLI and JSON output.
- Agents with a native tool/skill system can expose the same command as a read-only memory tool.

Put the chosen SMY entry point in that agent's system prompt or equivalent startup instructions. Start with a normal search, inspect the diagnostic fields, and retry with `--scan-all` when the result is truncated, insufficient, or contradictory. Continue searching until the result supports the next action. Say explicitly when no memory hit exists. The CLI is an interoperability layer, not a claim that every agent automatically shares context.

## Commands

```bash
smy --config ~/.smy/config.json index
smy --config ~/.smy/config.json search "deployment workflow" --json
smy --config ~/.smy/config.json search "deployment workflow" --raw --json
smy --config ~/.smy/config.json search "deployment workflow" --raw --scan-all --json
smy --config ~/.smy/config.json search "deployment workflow" --status verified --json
smy --config ~/.smy/config.json health
smy --config ~/.smy/config.json sources
```

Index output is sanitized for common API keys, bearer tokens, secret assignments, and credential-bearing URLs. Treat source files as private and review your own repository history before publishing.

## Development and release checks

```bash
python -m unittest discover -s tests -v
python -m compileall src tests
```

JSON search results include `scanned`, `total_files`, `truncated`, and `elapsed_ms`. The default index search includes active and verified baseline states. The project intentionally has no runtime dependency beyond Python 3.10+ and SQLite FTS5. The package exposes the `smy` console command through standard Python packaging. The implementation lives under `src/smy/`, so consumers install and invoke a product entry point rather than depending on a copied script.
