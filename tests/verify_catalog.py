#!/usr/bin/env python3
"""Verify the prototype catalog against an AzerothCore item_template SQL dump."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def split_row(row: str) -> list[str]:
    values = []
    current = []
    quoted = False
    escaped = False
    for char in row:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\" and quoted:
            current.append(char)
            escaped = True
        elif char == "'":
            current.append(char)
            quoted = not quoted
        elif char == "," and not quoted:
            values.append("".join(current))
            current = []
        else:
            current.append(char)
    values.append("".join(current))
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("item_template_sql", type=Path)
    args = parser.parse_args()

    expected = json.loads((ROOT / "tests/catalog_expected.json").read_text(encoding="utf-8"))
    by_id = {}
    wanted = {item for slot in expected.values() for item in slot["items"]}
    with args.item_template_sql.open(encoding="utf-8") as source:
        for line in source:
            if not line.startswith("("):
                continue
            item_id_text = line[1:line.find(",")]
            if item_id_text.isdigit() and int(item_id_text) in wanted:
                fields = split_row(line.strip().lstrip("(").rstrip(",;\n)"))
                by_id[int(fields[0])] = {"name": fields[4].strip("'"), "inventoryType": int(fields[12])}

    missing = sorted(wanted - set(by_id))
    if missing:
        raise SystemExit(f"catalog item IDs missing from item_template: {missing}")

    for slot_name, definition in expected.items():
        allowed = definition["inventoryType"]
        if not isinstance(allowed, list):
            allowed = [allowed]
        for item_id in definition["items"]:
            actual = by_id[item_id]
            if actual["inventoryType"] not in allowed:
                raise SystemExit(
                    f"{slot_name} item {item_id} ({actual['name']}) has inventory type "
                    f"{actual['inventoryType']}, expected one of {allowed}"
                )
            print(f"PASS {slot_name:10} {item_id:5} type={actual['inventoryType']:2} {actual['name']}")


if __name__ == "__main__":
    main()
