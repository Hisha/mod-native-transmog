#!/usr/bin/env python3
"""Audit the explicit Phase 5A catalog against an installed AzerothCore item_template dump."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re

from verify_catalog import split_row


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATTERN = re.compile(
    r'SET\((\d+), (\d+), "([^"]+)", "([^"]+)", "([^"]+)", (true|false)\)'
)
INVENTORY_SLOTS = {
    1: "head", 3: "shoulders", 4: "shirt", 5: "chest", 20: "chest", 6: "waist",
    7: "legs", 8: "feet", 9: "wrists", 10: "hands", 16: "back", 13: "main-hand",
    17: "main-hand", 21: "main-hand", 14: "off-hand", 22: "off-hand", 23: "off-hand",
    15: "ranged", 25: "ranged", 26: "ranged", 19: "tabard",
}


def expected_piece_count(family: str) -> int:
    if family in {"Tier 1", "Tier 2", "Tier 3", "Tier 6"}:
        return 8
    return 5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("item_template_sql", type=Path)
    args = parser.parse_args()

    definitions = [
        (int(set_id), int(class_mask), expansion, family, category, legacy == "true")
        for set_id, class_mask, expansion, family, category, legacy in CATALOG_PATTERN.findall(
            (ROOT / "src/NativeTransmogVerifiedCatalog.inc").read_text(encoding="utf-8")
        )
    ]
    if len(definitions) != 263 or len({row[0] for row in definitions}) != len(definitions):
        raise SystemExit("verified catalog must contain exactly 263 unique ItemSet identities")

    wanted = {row[0] for row in definitions}
    items = defaultdict(list)
    with args.item_template_sql.open(encoding="utf-8") as source:
        for line in source:
            if not line.startswith("("):
                continue
            fields = split_row(line.strip().lstrip("(").rstrip(",;\n)"))
            set_id = int(fields[112])
            inventory_type = int(fields[12])
            if set_id in wanted and inventory_type in INVENTORY_SLOTS and int(fields[5]):
                items[set_id].append(
                    (int(fields[0]), INVENTORY_SLOTS[inventory_type], int(fields[13]), fields[4].strip("'"))
                )

    failures = []
    for set_id, class_mask, expansion, family, category, legacy in definitions:
        members = items[set_id]
        slots = {member[1] for member in members}
        expected = expected_piece_count(family)
        if len(slots) != expected:
            failures.append(f"ItemSet {set_id} {family}: {len(slots)} slots, expected {expected}")
        if not any(mask == class_mask or mask & class_mask for _, _, mask, _ in members):
            failures.append(f"ItemSet {set_id}: no member permits verified class mask {class_mask}")
    if failures:
        raise SystemExit("\n".join(failures))

    counts = Counter((expansion, category) for _, _, expansion, _, category, _ in definitions)
    print(f"PASS {len(definitions)} verified ItemSet identities; all class masks and piece counts match")
    for (expansion, category), count in sorted(counts.items()):
        print(f"PASS {expansion:26} {category}: {count}")


if __name__ == "__main__":
    main()
