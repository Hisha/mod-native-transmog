#!/usr/bin/env python3
"""Playerbot packet-hook integration for successful Disenchant rolls."""

from __future__ import annotations

import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text(encoding="utf-8")
DISENCHANT = (ROOT / "src/NativeTransmogDisenchant.cpp").read_text(encoding="utf-8")
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
        server_h = CORE_ROOT / "src/server/game/Scripting/ScriptDefines/ServerScript.h"
        session_cpp = CORE_ROOT / "src/server/game/Server/WorldSession.cpp"
        if not all(path.exists() for path in (
            group, player_h, player_cpp, manager_h, server_h, session_cpp
        )):
            raise unittest.SkipTest(
                "set AZEROTHCORE_SOURCE_DIR to the Playerbot source tree"
            )
        cls.group = committed_text(group)
        cls.player_h = committed_text(player_h)
        cls.player_cpp = committed_text(player_cpp)
        cls.manager_h = committed_text(manager_h)
        cls.server_h = committed_text(server_h)
        cls.session_cpp = committed_text(session_cpp)

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

    def test_winner_packet_contains_final_disenchant_identity(self) -> None:
        sender = self.group[
            self.group.index("void Group::SendLootRollWon"):
            self.group.index("void Group::SendLootAllPassed")
        ]
        for field in (
            "roll.itemid", "targetGuid", "rollNumber", "rollType"
        ):
            self.assertIn(field, sender)

        greed_resolution = self.group[
            self.group.index("if (roll->totalNeed == 0 && roll->totalGreed > 0)"):
            self.group.index("if (roll->totalNeed == 0 && roll->totalGreed == 0)")
        ]
        notification = "SendLootRollWon(roll->itemGUID, maxguid, maxresul, rollvote, *roll);"
        self.assertIn(notification, greed_resolution)
        self.assertLess(
            greed_resolution.index(notification),
            greed_resolution.index("else if (rollvote == DISENCHANT)")
        )

    def test_server_packet_hook_runs_before_socket_dispatch(self) -> None:
        self.assertIn(
            "virtual void OnPacketSent(WorldSession*", self.server_h
        )
        send = self.session_cpp[
            self.session_cpp.index("void WorldSession::SendPacket"):
            self.session_cpp.index("void WorldSession::QueuePacket")
        ]
        hook = "sScriptMgr->OnPacketSent(this, *packet);"
        self.assertIn(hook, send)
        self.assertLess(send.index(hook), send.index("if (!m_Socket)"))
        self.assertLess(send.index(hook), send.index("m_Socket->SendPacket(*packet)"))


class DisenchantModuleIntegrationTests(unittest.TestCase):
    def test_module_uses_supported_server_hook(self) -> None:
        self.assertNotIn("PLAYERHOOK_ON_GROUP_ROLL_" + "DISENCHANT", MODULE)
        self.assertNotIn("OnPlayerGroupRoll" + "Disenchant", MODULE)
        self.assertIn("SERVERHOOK_ON_PACKET_SENT", DISENCHANT)
        self.assertIn("void OnPacketSent(WorldSession* session", DISENCHANT)
        self.assertIn("AddNativeTransmogDisenchantScript()", MODULE)

    def test_packet_is_attributed_only_to_authenticated_winner(self) -> None:
        self.assertIn("packet.GetOpcode() != SMSG_LOOT_ROLL_WON", DISENCHANT)
        self.assertIn("packet.size() != 34", DISENCHANT)
        self.assertIn("winner = session->GetPlayer()", DISENCHANT)
        self.assertIn("winnerGuid == winner->GetGUID()", DISENCHANT)
        self.assertIn("rollType == ROLL_DISENCHANT", DISENCHANT)
        self.assertIn("rollNumber >= 1 && rollNumber <= 100", DISENCHANT)

    def test_original_item_uses_shared_collection_service(self) -> None:
        self.assertIn("DisenchantRoll = 7", COLLECTION_H)
        self.assertIn("sObjectMgr->GetItemTemplate(itemEntry)", DISENCHANT)
        self.assertIn("AcquisitionSource::DisenchantRoll", DISENCHANT)


if __name__ == "__main__":
    unittest.main()
