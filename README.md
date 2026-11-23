# Smart Memory CLI

Smart Memory 是一个面向 AI Agent 的持久记忆命令行工具。它把结构化记忆和原始会话检索接入同一个 CLI，让不同 Agent 可以通过 exec、系统提示词、Skill 或 MCP 适配器使用同一套记忆入口。

## 解决的问题

Agent 的上下文会随着会话结束而消失，换一个 Agent 后还要重新解释背景。Smart Memory 为记忆检索提供稳定的命令行接口，优先查询持久化 Markdown 记忆，必要时直接回查原始会话，并保留多轮检索直到结果足以支撑下一步行动。

## 使用方法

需要 Python 3.10 或更高版本。

```bash
python -m pip install .
smy --help
```

复制 `config.example.json` 为 `~/.smy/config.json`，再把路径改成自己的记忆目录和原始会话目录。

```bash
smy --config ~/.smy/config.json index
smy --config ~/.smy/config.json search "deployment workflow" --json
smy --config ~/.smy/config.json search "deployment workflow" --raw --json
smy --config ~/.smy/config.json search "deployment workflow" --raw --scan-all --json
smy --config ~/.smy/config.json search "deployment workflow" --status verified --json
smy --config ~/.smy/config.json health
```

Agent 接入时，建议把 `smy` 入口写入对应 Agent 的系统提示词或启动规则。第一次使用普通 `search`，检查 JSON 中的扫描诊断。如果结果不足、互相矛盾或 `truncated=true`，再使用 `--scan-all` 或换关键词继续检索。记忆库没有相关内容时，应明确说明没有找到。

## 核心优势

- Basic Memory 和原始会话使用同一个 CLI 入口。
- 默认检索保持快速，重要问题可以使用 `--scan-all` 完整扫描。
- 默认检索 active、verified 和基线状态的记忆，可用 `--status` 精确筛选。
- JSON 结果包含扫描数量、总文件数、截断状态和耗时，便于 Agent 决定是否继续检索。
- 常见 API key、Bearer token、secret 赋值和带凭据 URL 会在索引和输出中脱敏。

## 技术架构

实现使用 Python 标准库和 SQLite FTS5。`src/smy/cli.py` 提供 CLI，`index` 将配置的 Markdown/TXT 记忆建立为本地索引，`search` 查询索引，`search --raw` 只读扫描原始会话，`--scan-all` 提供重要任务的完整扫描路径。

## 配置与数据边界

配置文件只保存用户自己的路径。仓库不包含个人 FMP 规则、Basic Memory 内容、原始会话、账号数据、权限链接、密钥或令牌。原始历史保留在原位置，由 Smart Memory 直接扫描，不复制进 SQLite 索引。

## 开发与验证

```bash
python -m unittest discover -s tests -v
python -m compileall src tests
python -m pip wheel . --no-deps --wheel-dir dist
```

## English

### Smart Memory CLI

Smart Memory is a persistent-memory command-line tool for AI agents. It gives different agents one stable entry point for structured memory and original session search through exec, system prompts, Skills, or an MCP adapter.

### Problem it solves

An agent loses working context when a session ends, and switching agents often requires repeating the same background. Smart Memory provides a stable retrieval interface. It searches durable Markdown memory first, reads original sessions when needed, and supports repeated retrieval until the result is sufficient for the next action.

### Usage

Python 3.10 or newer is required.

```bash
python -m pip install .
smy --help
```

Copy `config.example.json` to `~/.smy/config.json` and set the paths for your memory and original-session roots.

```bash
smy --config ~/.smy/config.json index
smy --config ~/.smy/config.json search "deployment workflow" --json
smy --config ~/.smy/config.json search "deployment workflow" --raw --json
smy --config ~/.smy/config.json search "deployment workflow" --raw --scan-all --json
smy --config ~/.smy/config.json search "deployment workflow" --status verified --json
smy --config ~/.smy/config.json health
```

Expose the `smy` entry point through the target agent's system prompt or startup rules. Start with a normal search and inspect the JSON diagnostics. Use `--scan-all` or refine the query when the result is insufficient, contradictory, or `truncated=true`. If the memory store has no relevant entry, say so explicitly.

### Core strengths

- One CLI entry point for durable memory and original sessions.
- Fast default retrieval with `--scan-all` for important questions.
- Active, verified, and baseline memory states are searchable by default, with `--status` for precise filtering.
- JSON diagnostics expose scanned files, total files, truncation, and elapsed time.
- Common API keys, bearer tokens, secret assignments, and credential-bearing URLs are redacted in indexed content and output.

### Architecture

Smart Memory uses the Python standard library and SQLite FTS5. `src/smy/cli.py` provides the CLI. `index` builds a local index from configured Markdown/TXT memory, `search` queries the index, `search --raw` reads original sessions without copying them into the index, and `--scan-all` provides a complete scan path for important tasks.

### Configuration and data boundary

The configuration file contains only user-provided paths. The repository contains no personal FMP rules, Basic Memory content, original sessions, account data, permission links, keys, or tokens. Original history stays in its source location and is read directly by Smart Memory.

### Development and verification

```bash
python -m unittest discover -s tests -v
python -m compileall src tests
python -m pip wheel . --no-deps --wheel-dir dist
```
