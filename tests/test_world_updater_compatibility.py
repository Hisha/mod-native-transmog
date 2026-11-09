#!/usr/bin/env python3
"""Regression coverage for AzerothCore's mysql-client update-file contract."""

from __future__ import annotations

import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SQL_FILES = (
    ROOT / "data/sql/db-world/base/001_native_transmog_npc_service.sql",
    ROOT / "data/sql/db-world/updates/2026_11_09_00_native_warpweavers.sql",
)


def _find_azerothcore_root() -> Path | None:
    candidates = []
    if configured := os.environ.get("AZEROTHCORE_ROOT"):
        candidates.append(Path(configured))
    candidates.extend(
        (
            ROOT.parents[1],
            Path.home() / "aicode_folder/azerothcore-wotlk",
        )
    )
    relative = Path("src/server/database/Updater/DBUpdater.cpp")
    return next((path for path in candidates if (path / relative).is_file()), None)


def _mysql_batch_statements(sql: str) -> list[str]:
    """Split the ordinary statements accepted by mysql's default batch mode.

    This intentionally has no DELIMITER implementation: AzerothCore passes the
    file to mysql on stdin and supplies no preprocessing layer for routines.
    """

    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    line_comment = False
    block_comment = False
    index = 0

    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""

        if line_comment:
            current.append(char)
            if char == "\n":
                line_comment = False
            index += 1
            continue

        if block_comment:
            current.append(char)
            if char == "*" and following == "/":
                current.append(following)
                block_comment = False
                index += 2
            else:
                index += 1
            continue

        if quote:
            current.append(char)
            if char == "\\" and following:
                current.append(following)
                index += 2
                continue
            if char == quote:
                if following == quote and quote in ("'", '"', "`"):
                    current.append(following)
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if char in ("'", '"', "`"):
            quote = char
            current.append(char)
            index += 1
            continue
        if char == "#" or (char == "-" and following == "-" and
                           (index + 2 == len(sql) or sql[index + 2].isspace())):
            line_comment = True
            current.append(char)
            index += 1
            continue
        if char == "/" and following == "*":
            block_comment = True
            current.extend((char, following))
            index += 2
            continue
        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current.clear()
            index += 1
            continue

        current.append(char)
        index += 1

    if quote or block_comment:
        raise AssertionError("unterminated SQL quote or block comment")
    if "".join(current).strip():
        raise AssertionError("unterminated SQL statement")
    return statements


def _without_leading_comments(statement: str) -> str:
    lines = statement.splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("--")):
        lines.pop(0)
    return "\n".join(lines).lstrip()


class WorldUpdaterCompatibilityTests(unittest.TestCase):
    def test_real_playerbot_updater_streams_files_to_mysql_without_parsing(self) -> None:
        core = _find_azerothcore_root()
        if core is None:
            self.skipTest("set AZEROTHCORE_ROOT to a Playerbot AzerothCore checkout")

        updater = (core / "src/server/database/Updater/DBUpdater.cpp").read_text(
            encoding="utf-8"
        )
        process = (core / "src/common/Utilities/StartProcess.cpp").read_text(
            encoding="utf-8"
        )

        self.assertIn("DBUpdaterUtil::GetCorrectedMySQLExecutable()", updater)
        self.assertIn('args.emplace_back("--default-character-set=utf8")', updater)
        self.assertIn("path.generic_string(), true", updater)
        self.assertIn("std_in = inputFile.get()", process)
        self.assertNotIn("DELIMITER", updater)
        self.assertNotIn('args.emplace_back("--force")', updater)

    def test_installer_is_valid_for_the_real_updater_batch_contract(self) -> None:
        for path in SQL_FILES:
            statements = _mysql_batch_statements(path.read_text(encoding="utf-8"))
            executable = [_without_leading_comments(item).upper() for item in statements]

            self.assertGreater(len(executable), 15)
            self.assertTrue(all(item for item in executable))
            self.assertFalse(any(item.startswith("DELIMITER") for item in executable))
            self.assertFalse(any(item.startswith("CREATE PROCEDURE") for item in executable))
            self.assertFalse(any(item.startswith("CREATE FUNCTION") for item in executable))
            self.assertFalse(any(item.startswith("CALL ") for item in executable))
            self.assertEqual(sum(item.startswith("START TRANSACTION") for item in executable), 1)
            self.assertEqual(sum(item.startswith("COMMIT") for item in executable), 1)


if __name__ == "__main__":
    unittest.main()
