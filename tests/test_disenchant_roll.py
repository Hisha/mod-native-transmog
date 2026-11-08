#!/usr/bin/env python3
"""PTR-compatible group-roll integration and Disenchant limitations."""

from __future__ import annotations

import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text(encoding="utf-8")
COLLECTION_H = (ROOT / "src/NativeTransmogCollection.h").read_text(encoding="utf-8")

CORE_ROOT = Path(os.environ.get(
    "AZEROTHCORE_SOURCE_DIR", "/home/smithkt/aicode_folder/azerothcore-wotlk"
))


def committed_text(path: Path) -> str:
    """Read the target branch version, excluding any local core experiments."""
    git_dir = CORE_ROOT / ".git"
    relative = path.relative_to(CORE_ROOT).as_posix()
    if git_dir.exists():
        import subprocess

        result = subprocess.run(
            ["git", "-C", str(CORE_ROOT), "show", f"HEAD:{relative}"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    return path.read_text(encoding="utf-8")


class DisenchantCoreIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        group = CORE_ROOT / "src/server/game/Groups/Group.cpp"
        player_h = CORE_ROOT / "src/server/game/Scripting/ScriptDefines/PlayerScript.h"
        player_cpp = CORE_ROOT / "src/server/game/Scripting/ScriptDefines/PlayerScript.cpp"
        manager_h = CORE_ROOT / "src/server/game/Scripting/ScriptMgr.h"
        if not all(path.exists() for path in (group, player_h, player_cpp, manager_h)):
            raise unittest.SkipTest(
                "set AZEROTHCORE_SOURCE_DIR to the Playerbot source tree"
            )
        cls.group = committed_text(group)
        cls.player_h = committed_text(player_h)
        cls.player_cpp = committed_text(player_cpp)
        cls.manager_h = committed_text(manager_h)

    def test_disenchant_branch_has_no_reward_hook(self) -> None:
        branch = self.group[self.group.index("else if (rollvote == DISENCHANT)"):]
        branch = branch[:branch.index("if (roll->totalNeed == 0 && roll->totalGreed == 0)")]
        self.assertNotIn("OnPlayerGroupRollRewardItem", branch)
        self.assertNotIn("OnPlayerGroupRoll" + "Disenchant", branch)
        self.assertIn("player->AutoStoreLoot(pProto->DisenchantID", branch)
        self.assertIn("loot.FillLoot(pProto->DisenchantID", branch)

    def test_ptr_exposes_no_custom_disenchant_hook(self) -> None:
        hook = "PLAYERHOOK_ON_GROUP_ROLL_" + "DISENCHANT"
        callback = "OnPlayerGroupRoll" + "Disenchant"
        for source in (self.player_h, self.player_cpp, self.manager_h):
            self.assertNotIn(hook, source)
            self.assertNotIn(callback, source)
        self.assertIn("OnPlayerGroupRollRewardItem", self.player_h)

    def test_need_and_greed_paths_remain_store_new_item_paths(self) -> None:
        self.assertGreaterEqual(self.group.count("OnPlayerGroupRollRewardItem"), 2)
        self.assertGreaterEqual(self.group.count("player->StoreNewItem"), 2)
        self.assertIn("void OnPlayerStoreNewItem", MODULE)
        self.assertIn("AcquisitionSource::NewItem", MODULE)


class DisenchantModulePolicyTests(unittest.TestCase):
    def test_module_has_no_unsupported_hook_dependency(self) -> None:
        self.assertNotIn("PLAYERHOOK_ON_GROUP_ROLL_" + "DISENCHANT", MODULE)
        self.assertNotIn("OnPlayerGroupRoll" + "Disenchant", MODULE)

    def test_historical_source_value_remains_reserved(self) -> None:
        self.assertIn("DisenchantRoll = 7", COLLECTION_H)
        self.assertNotIn("AcquisitionSource::DisenchantRoll", MODULE)


if __name__ == "__main__":
    unittest.main()
