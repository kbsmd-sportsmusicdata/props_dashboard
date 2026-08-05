#!/usr/bin/env python3
"""Embed the generated dashboard bundle into the standalone HTML template."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path


PLACEHOLDER = "/*__DASHBOARD_DATA__*/"


def build_dashboard(template_path: Path, payload: dict, output_path: Path) -> None:
    template = template_path.read_text(encoding="utf-8")
    placeholder_count = template.count(PLACEHOLDER)
    if placeholder_count != 1:
        raise ValueError(
            f"dashboard template must contain exactly one {PLACEHOLDER}; found {placeholder_count}"
        )
    html = template.replace(PLACEHOLDER, json.dumps(payload, separators=(",", ":")))
    if "fetch(" in html:
        raise ValueError("standalone dashboard must not use fetch()")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False) as tmp:
        tmp.write(html)
        temp_path = Path(tmp.name)
    temp_path.replace(output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_dashboard(args.template, json.loads(args.data.read_text(encoding="utf-8")), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
