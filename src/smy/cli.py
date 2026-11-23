#!/usr/bin/env python3
"""SMY: a small, configuration-driven persistent-memory CLI for agents.

The CLI indexes Markdown notes and can search configured raw session roots
without copying raw session bodies into the index.  It never ships with a
machine-specific path or credential.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Iterable

SECRET_PATTERNS = (
    re.compile(r"(?i)\bsk-[^\s`\"\\]{4,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r'''(?i)(?:api[-_ ]?key|access[-_ ]?token|secret)\s*[:=]\s*["']?[A-Za-z0-9._~+/=-]{16,}'''),
    re.compile(r'''(?i)https?://[^\s"']+[?&](?:key|token|secret|api_key)=[^\s"']+'''),
)
DEFAULT_STATUSES = ("active", "verified", "baseline", "operating-baseline", "protocol-baseline")


def redact(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: redact_obj(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_obj(v) for v in value]
    return redact(value)


def default_config_path() -> Path:
    return Path(os.environ.get("SMY_CONFIG", Path.home() / ".smy" / "config.json"))


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"memory_roots": [], "raw_roots": [], "index": str(path.parent / "index.sqlite")}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    data.setdefault("memory_roots", [])
    data.setdefault("raw_roots", [])
    data.setdefault("index", str(path.parent / "index.sqlite"))
    return data


def iter_files(roots: Iterable[Any], suffixes=(".md", ".markdown", ".txt")):
    for item in roots:
        if isinstance(item, str):
            name, raw = Path(item).name, item
        else:
            name, raw = item.get("name", Path(item["path"]).name), item["path"]
        root = Path(raw).expanduser()
        if root.is_file() and root.suffix.lower() in suffixes:
            yield name, root
        elif root.is_dir():
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in suffixes and ".git" not in path.parts:
                    yield name, path


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2).strip("\"'")
    return result


def classify(path: Path, text: str) -> str:
    layer = parse_frontmatter(text).get("layer")
    if layer in {"fact", "method", "philosophy"}:
        return layer
    lowered = str(path).replace("\\", "/").lower()
    if "philosophy" in lowered or "哲学" in lowered:
        return "philosophy"
    if "method" in lowered or "workflow" in lowered or "方法" in lowered:
        return "method"
    return "fact"


def build_index(config: dict[str, Any], db_path: Path) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript("""
      PRAGMA journal_mode=WAL;
      DROP TABLE IF EXISTS docs;
      DROP TABLE IF EXISTS docs_fts;
      CREATE TABLE docs(id INTEGER PRIMARY KEY, path TEXT UNIQUE, source TEXT, layer TEXT,
        title TEXT, body TEXT, status TEXT, updated_at TEXT, content_hash TEXT);
      CREATE VIRTUAL TABLE docs_fts USING fts5(title, body, content=docs, content_rowid=id,
        tokenize='unicode61 remove_diacritics 0');
    """)
    count = 0
    for source, path in iter_files(config.get("memory_roots", [])):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta = parse_frontmatter(text)
        title = next((line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#")), path.stem)
        safe = redact(text)
        cur = con.execute(
            "INSERT INTO docs(path,source,layer,title,body,status,updated_at,content_hash) VALUES(?,?,?,?,?,?,?,?)",
            (str(path), source, classify(path, text), redact(title), safe, meta.get("status", "active"),
             dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
             hashlib.sha256(safe.encode()).hexdigest()),
        )
        con.execute("INSERT INTO docs_fts(rowid,title,body) VALUES(?,?,?)", (cur.lastrowid, redact(title), safe))
        count += 1
    con.commit()
    con.execute("INSERT INTO docs_fts(docs_fts) VALUES('optimize')")
    con.commit()
    con.close()
    return {"db": str(db_path), "docs": count}


def search_index(query: str, config: dict[str, Any], top: int, source: str | None = None, layer: str | None = None, statuses: tuple[str, ...] = DEFAULT_STATUSES):
    db_path = Path(config["index"]).expanduser()
    if not db_path.exists():
        return [], {"scanned": 0, "total_files": 0, "truncated": False, "elapsed_ms": 0}
    started = time.perf_counter()
    con = sqlite3.connect(db_path)
    placeholders = ",".join("?" for _ in statuses)
    clauses = [f"docs_fts MATCH ?", f"d.status IN ({placeholders})"]
    args: list[Any] = [query]
    args.extend(statuses)
    if source:
        clauses.append("d.source = ?"); args.append(source)
    if layer:
        clauses.append("d.layer = ?"); args.append(layer)
    args.append(top)
    sql = "SELECT d.path,d.source,d.layer,d.title,snippet(docs_fts,1,'','', ' … ',36) FROM docs_fts JOIN docs d ON d.id=docs_fts.rowid WHERE " + " AND ".join(clauses) + " ORDER BY rank LIMIT ?"
    try:
        rows = con.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        rows = []
    count_clauses = [f"d.status IN ({placeholders})"]
    count_args = list(statuses)
    if source:
        count_clauses.append("d.source = ?"); count_args.append(source)
    if layer:
        count_clauses.append("d.layer = ?"); count_args.append(layer)
    count_sql = "SELECT COUNT(*) FROM docs d WHERE " + " AND ".join(count_clauses)
    try:
        total_files = con.execute(count_sql, count_args).fetchone()[0]
    except sqlite3.OperationalError:
        total_files = 0
    con.close()
    diagnostics = {"scanned": total_files, "total_files": total_files, "truncated": False, "elapsed_ms": round((time.perf_counter() - started) * 1000)}
    return [{"path": redact(r[0]), "source": r[1], "layer": r[2], "title": redact(r[3]), "snippet": redact(r[4])} for r in rows], diagnostics


def raw_search(query: str, config: dict[str, Any], top: int, source: str | None = None, seconds: float = 8, scan_all: bool = False):
    needle = query.casefold()
    rows = []
    files = list(iter_files(config.get("raw_roots", [])))
    started = time.perf_counter()
    truncated = False
    for index, (name, path) in enumerate(files, start=1):
        if source and name != source:
            continue
        if time.perf_counter() - started >= seconds:
            truncated = True
            break
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        pos = text.casefold().find(needle)
        if pos >= 0:
            start = max(0, pos - 180)
            rows.append({"path": redact(str(path)), "source": name, "role": "raw", "snippet": redact(text[start:pos + len(query) + 220].replace("\n", " "))})
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    diagnostics = {"scanned": index if files else 0, "total_files": len(files), "truncated": truncated, "elapsed_ms": elapsed_ms}
    return rows[:top], diagnostics


def print_rows(rows, as_json: bool, diagnostics: dict[str, Any] | None = None):
    diagnostics = diagnostics or {"scanned": 0, "total_files": 0, "truncated": False, "elapsed_ms": 0}
    if as_json and not rows:
        print(json.dumps({"record_type": "meta", **diagnostics}, ensure_ascii=False))
        return
    for row in rows:
        enriched = {**row, **diagnostics}
        print(json.dumps(redact_obj(enriched), ensure_ascii=False) if as_json else f"[{row.get('source','raw')}] {row.get('title', row.get('path',''))}\n  {row.get('path','')}\n  …{row.get('snippet','')}…")
    if not as_json and diagnostics.get("truncated"):
        print(f"[scan] truncated after {diagnostics['scanned']}/{diagnostics['total_files']} files")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="smy", description="Persistent memory search for CLI agents")
    parser.add_argument("--config", type=Path, default=default_config_path())
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("index"); p.add_argument("--db", type=Path)
    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("--top", type=int, default=5); p.add_argument("--seconds", type=float, default=8); p.add_argument("--source"); p.add_argument("--layer"); p.add_argument("--status", action="append"); p.add_argument("--raw", action="store_true"); p.add_argument("--scan-all", action="store_true"); p.add_argument("--json", action="store_true")
    sub.add_parser("health")
    sub.add_parser("sources")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.command == "index":
        if args.db: config["index"] = str(args.db)
        print(json.dumps(build_index(config, Path(config["index"]).expanduser()), ensure_ascii=False))
    elif args.command == "search":
        if args.raw:
            rows, diagnostics = raw_search(args.query, config, args.top, args.source, args.seconds, args.scan_all)
        else:
            statuses = tuple(args.status) if args.status else DEFAULT_STATUSES
            rows, diagnostics = search_index(args.query, config, args.top, args.source, args.layer, statuses)
        print_rows(rows, args.json, diagnostics)
    elif args.command == "health":
        print(json.dumps({"config": str(args.config), "index": str(Path(config["index"]).expanduser()), "index_exists": Path(config["index"]).expanduser().exists(), "memory_roots": len(config["memory_roots"]), "raw_roots": len(config["raw_roots"])}, ensure_ascii=False))
    elif args.command == "sources":
        print(json.dumps({"memory_roots": config["memory_roots"], "raw_roots": config["raw_roots"]}, ensure_ascii=False) if True else "")


if __name__ == "__main__":
    main()
