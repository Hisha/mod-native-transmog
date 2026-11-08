#!/usr/bin/env python3
"""Winner-only Disenchant-roll integration and collection regressions."""

from __future__ import annotations

import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text(encoding="utf-8")
COLLECTION_CPP = (ROOT / "src/NativeTransmogCollection.cpp").read_text(encoding="utf-8")
COLLECTION_H = (ROOT / "src/NativeTransmogCollection.h").read_text(encoding="utf-8")

CORE_ROOT = Path(os.environ.get(
    "AZEROTHCORE_SOURCE_DIR", "/home/smithkt/aicode_folder/azerothcore-wotlk"
))


class DisenchantCoreIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        group = CORE_ROOT / "src/server/game/Groups/Group.cpp"
        player_h = CORE_ROOT / "src/server/game/Scripting/ScriptDefines/PlayerScript.h"
        player_cpp = CORE_ROOT / "src/server/game/Scripting/ScriptDefines/PlayerScript.cpp"
        manager_h = CORE_ROOT / "src/server/game/Scripting/ScriptMgr.h"
        if not all(path.exists() for path in (group, player_h, player_cpp, manager_h)):
            raise unittest.SkipTest(
                "set AZEROTHCORE_SOURCE_DIR to the patched Playerbot source tree"
            )
        cls.group = group.read_text(encoding="utf-8")
        cls.player_h = player_h.read_text(encoding="utf-8")
        cls.player_cpp = player_cpp.read_text(encoding="utf-8")
        cls.manager_h = manager_h.read_text(encoding="utf-8")

    def test_real_disenchant_winner_path_fires_before_material_generation(self) -> None:
        branch = self.group[self.group.index("else if (rollvote == DISENCHANT)"):]
        branch = branch[:branch.index("if (roll->totalNeed == 0 && roll->totalGreed == 0)")]
        hook = "sScriptMgr->OnPlayerGroupRollDisenchant(player, roll->itemid, item->count, roll);"
        self.assertEqual(branch.count(hook), 1)
        self.assertLess(branch.index("SendLootRollWon" if "SendLootRollWon" in branch else "item->is_looted = true"),
                        branch.index(hook))
        self.assertLess(branch.index(hook), branch.index("player->AutoStoreLoot"))
        self.assertLess(branch.index(hook), branch.index("player->SendItemRetrievalMail"))
        self.assertIn("player = ObjectAccessor::FindPlayer(maxguid)", self.group)
        self.assertIn("if (player)", self.group)

    def test_hook_is_additive_and_dispatched_through_playerscript(self) -> None:
        signature = "OnPlayerGroupRollDisenchant(Player*"
        self.assertIn("PLAYERHOOK_ON_GROUP_ROLL_DISENCHANT", self.player_h)
        self.assertIn(signature, self.player_h)
        self.assertIn(signature, self.manager_h)
        self.assertIn("CALL_ENABLED_HOOKS(PlayerScript, PLAYERHOOK_ON_GROUP_ROLL_DISENCHANT",
                      self.player_cpp)
        self.assertIn("OnPlayerGroupRollRewardItem", self.player_h)

    def test_need_and_greed_paths_remain_store_new_item_paths(self) -> None:
        self.assertGreaterEqual(self.group.count("OnPlayerGroupRollRewardItem"), 2)
        self.assertGreaterEqual(self.group.count("player->StoreNewItem"), 2)
        self.assertIn("void OnPlayerStoreNewItem", MODULE)
        self.assertIn("AcquisitionSource::NewItem", MODULE)


class DisenchantModulePolicyTests(unittest.TestCase):
    def test_module_reuses_collection_service_with_original_template(self) -> None:
        handler = MODULE[MODULE.index("void OnPlayerGroupRollDisenchant"):]
        handler = handler[:handler.index("void OnPlayerAfterSetVisibleItemSlot")]
        self.assertIn("sObjectMgr->GetItemTemplate(itemEntry)", handler)
        self.assertIn("CollectionService::Instance().Unlock", handler)
        self.assertIn("AcquisitionSource::DisenchantRoll", handler)
        self.assertNotIn("AutoStoreLoot", handler)

    def test_disenchant_source_is_append_only_and_uses_acquire_policy(self) -> None:
        self.assertIn("DisenchantRoll = 7", COLLECTION_H)
        self.assertIn('case AcquisitionSource::DisenchantRoll: return "disenchant-roll"',
                      COLLECTION_CPP)
        unlock = COLLECTION_CPP[COLLECTION_CPP.index("bool CollectionService::Unlock(Player* player, ItemTemplate const*"):]
        source_gate = unlock[:unlock.index("if (!_config.enabled")]
        self.assertIn("case AcquisitionSource::DisenchantRoll", source_gate)
        self.assertIn("sourceEnabled = _config.unlockOnAcquire", source_gate)

    def test_winner_only_and_duplicate_behavior_model(self) -> None:
        collected: set[tuple[int, int, int, int]] = set()

        def unlock(winner: str | None, selected: dict[str, str], key, eligible=True):
            if winner is None or selected.get(winner) != "DISENCHANT" or not eligible:
                return None
            before = len(collected)
            collected.add(key)
            return winner if len(collected) != before else None

        appearance = (777, 4, 1, 7)
        votes = {"alice": "DISENCHANT", "bob": "GREED", "cara": "DISENCHANT"}
        self.assertEqual(unlock("alice", votes, appearance), "alice")
        self.assertIsNone(unlock("alice", votes, appearance), "duplicate must not add a row")
        self.assertIsNone(unlock("bob", votes, (778, 4, 1, 7)),
                          "a Greed winner does not traverse the Disenchant hook")
        self.assertIsNone(unlock("alice", votes, (779, 15, 0, 0), eligible=False))
        self.assertIsNone(unlock("bob", votes, (780, 4, 1, 7)))
        self.assertEqual(unlock("cara", votes, (781, 2, 7, 13)), "cara")


if __name__ == "__main__":
    unittest.main()
