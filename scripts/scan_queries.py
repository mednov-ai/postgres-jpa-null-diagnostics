#!/usr/bin/env python3
"""Find PostgreSQL/JPA null-binding patterns that require targeted verification."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    rule: str
    level: str
    message: str
    excerpt: str


RULES = (
    (
        "raw-untyped-null",
        "verify",
        re.compile(r"\.setObject\s*\([^,]+,\s*null\s*\)"),
        "Raw JDBC null is bound without a JDBC type; inspect the prepared SQL because an explicit SQL cast may make it safe.",
    ),
    (
        "named-param-coalesce",
        "verify",
        re.compile(r"coalesce\s*\(\s*:(\w+)\s*,\s*null\s*\)", re.IGNORECASE),
        "Named parameter is used in COALESCE; resolve its declared type and test the actual binding path.",
    ),
    (
        "spel-null-guard",
        "semantic",
        re.compile(r":#\{\s*null\s+eq\s+#(\w+)\s*}", re.IGNORECASE),
        "SpEL null guard detected; confirm parameter type and intended null/empty semantics.",
    ),
    (
        "direct-is-null",
        "verify",
        re.compile(r":(\w+)\s+is\s+null", re.IGNORECASE),
        "Direct null check needs a known bind type; inspect other typed uses and reproduce null binding.",
    ),
    (
        "projection-fetch-join",
        "maintainability",
        re.compile(r"join\s+fetch\s+(?:\w+\.)?\w+\s+\w+(?:\s+on\b)?", re.IGNORECASE),
        "Fetch join detected; determine whether the query returns entities or a projection and test pagination/count behavior.",
    ),
)


def source_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for suffix in ("*.kt", "*.java"):
        yield from root.rglob(suffix)


def declared_parameter_types(text: str) -> dict[str, str | None]:
    candidates: dict[str, set[str]] = {}
    pattern = re.compile(
        r'(?:@Param\("(?P<annotation>\w+)"\)\s*)?'
        r'(?P<variable>\w+)\s*:\s*'
        r'(?P<type>[A-Za-z_][\w.]*(?:\s*<[^>]+>)?\??)'
    )
    for match in pattern.finditer(text):
        name = match.group("annotation") or match.group("variable")
        candidates.setdefault(name, set()).add(match.group("type").replace(" ", ""))
    return {name: next(iter(types)) if len(types) == 1 else None for name, types in candidates.items()}


def is_collection(type_name: str | None) -> bool:
    return bool(type_name and re.search(r"(?:List|Set|Collection|Iterable|Array)<", type_name))


def scan(path: Path, display_root: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parameter_types = declared_parameter_types(text)
    findings: list[Finding] = []
    for rule, level, pattern, message in RULES:
        for match in pattern.finditer(text):
            effective_rule = rule
            effective_level = level
            effective_message = message
            parameter = match.group(1) if match.lastindex else None
            parameter_type = parameter_types.get(parameter) if parameter else None
            if rule == "named-param-coalesce" and parameter:
                if is_collection(parameter_type):
                    effective_rule = "collection-coalesce"
                    effective_message = (
                        f"{parameter} is declared as {parameter_type}; test null, empty, singleton, and multiple values "
                        "through the real repository method."
                    )
                elif parameter_type:
                    effective_rule = "scalar-coalesce"
                    effective_level = "info"
                    effective_message = (
                        f"{parameter} is declared as {parameter_type}; scalar COALESCE may work but is not automatically required."
                    )
            elif rule == "spel-null-guard" and parameter:
                if is_collection(parameter_type):
                    effective_rule = "collection-spel-null-only"
                    effective_message = (
                        f"{parameter} is declared as {parameter_type}; null is absent while an empty collection remains an active filter."
                    )
                elif parameter_type:
                    effective_rule = "scalar-spel-null-guard"
                    effective_level = "info"
                    effective_message = f"{parameter} is declared as {parameter_type}; verify null and non-null bindings."
            line = text.count("\n", 0, match.start()) + 1
            line_text = text.splitlines()[line - 1].strip()
            try:
                shown_path = str(path.relative_to(display_root))
            except ValueError:
                shown_path = str(path)
            findings.append(
                Finding(shown_path, line, effective_rule, effective_level, effective_message, line_text[:240])
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Kotlin/Java source file or project directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    root = args.path.resolve()
    if not root.exists():
        parser.error(f"path does not exist: {root}")

    display_root = root if root.is_dir() else root.parent
    findings = sorted(
        (finding for file in source_files(root) for finding in scan(file, display_root)),
        key=lambda item: (item.file, item.line, item.rule),
    )

    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2, ensure_ascii=False))
    else:
        for item in findings:
            print(f"{item.file}:{item.line}: [{item.level}] {item.rule}: {item.message}")
            print(f"  {item.excerpt}")
        print(f"Findings: {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
