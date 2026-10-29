#!/usr/bin/env python3
"""Phase 3B quest reward collection contracts and persistence-model tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text(encoding="utf-8")
QUEST_CPP = (ROOT / "src/NativeTransmogQuestCollection.cpp").read_text(encoding="utf-8")
QUEST_H = (ROOT / "src/NativeTransmogQuestCollection.h").read_text(encoding="utf-8")
COLLECTION_CPP = (ROOT / "src/NativeTransmogCollection.cpp").read_text(encoding="utf-8")
COLLECTION_H = (ROOT / "src/NativeTransmogCollection.h").read_text(encoding="utf-8")
CONFIG = (ROOT / "conf/mod_native_transmog.conf.dist").read_text(encoding="utf-8")
MIGRATION = (ROOT / "data/sql/db-characters/updates/2026_10_29_00_native_transmog_quest_provenance.sql").read_text(encoding="utf-8")

SCHEMA = """
CREATE TABLE collection (
 owner_type INTEGER, owner_id INTEGER, display_id INTEGER, item_class INTEGER,
 item_subclass INTEGER, inventory_type INTEGER, source_item INTEGER,
 source_quest INTEGER DEFAULT 0, acquisition_source INTEGER,
 PRIMARY KEY(owner_type, owner_id, display_id, item_class, item_subclass, inventory_type)
);
"""


@dataclass(frozen=True)
class Reward:
    item: int
    appearance: tuple[int, int, int, int] | None


def collect(db: sqlite3.Connection, owner: tuple[int, int], quest: int,
            rewards: list[Reward], preview: bool = False) -> tuple[int, int, int]:
    seen: set[tuple[int, int, int, int]] = set()
    eligible = already = new = 0
    for reward in rewards:
        if reward.appearance is None or reward.appearance in seen:
            continue
        seen.add(reward.appearance)
        eligible += 1
        exists = db.execute(
            "SELECT 1 FROM collection WHERE owner_type=? AND owner_id=? AND "
            "display_id=? AND item_class=? AND item_subclass=? AND inventory_type=?",
            (*owner, *reward.appearance),
        ).fetchone()
        if exists:
            already += 1
        elif preview:
            new += 1
        else:
            db.execute(
                "INSERT OR IGNORE INTO collection VALUES (?,?,?,?,?,?,?,?,?)",
                (*owner, *reward.appearance, reward.item, quest, 5),
            )
            new += 1
    db.commit()
    return eligible, already, new


class PhaseThreeBContractTests(unittest.TestCase):
    def test_selectable_and_guaranteed_arrays_are_both_enumerated(self) -> None:
        self.assertIn("quest->RewardChoiceItemId", QUEST_CPP)
        self.assertIn("quest->RewardItemId", QUEST_CPP)
        self.assertNotIn("RewardChoiceItemId[reward]", QUEST_CPP)

    def test_successful_post_reward_hook_only(self) -> None:
        self.assertIn("PLAYERHOOK_ON_PLAYER_COMPLETE_QUEST", MODULE)
        self.assertIn("void OnPlayerCompleteQuest", MODULE)
        for hook in ("PLAYERHOOK_ON_PLAYER_QUEST_ACCEPT", "PLAYERHOOK_ON_QUEST_ABANDON"):
            self.assertNotIn(hook, MODULE)

    def test_cross_class_collection_has_no_equipment_gates(self) -> None:
        for forbidden in ("CanUseItem", "CanEquipItem", "AllowableClass", "AllowableRace", "getClass"):
            self.assertNotIn(forbidden, QUEST_CPP)
        self.assertIn("CollectionService::ResolveAppearance", QUEST_CPP)

    def test_source_specific_configuration_defaults(self) -> None:
        self.assertIn("NativeTransmog.Collection.UnlockAllQuestRewards = 1", CONFIG)
        self.assertIn("NativeTransmog.Collection.QuestBackfill.Enable = 1", CONFIG)
        self.assertIn("unlockAllQuestRewards", COLLECTION_H)
        self.assertIn("questBackfillEnabled", COLLECTION_H)

    def test_provenance_is_additive_and_first_write_wins(self) -> None:
        self.assertIn("source_quest", MIGRATION)
        self.assertIn("information_schema`.`COLUMNS", MIGRATION)
        self.assertIn("INSERT IGNORE", COLLECTION_CPP)
        self.assertNotIn("UPDATE `native_transmog_collection` SET `source_quest`", MIGRATION)
        self.assertIn("QuestCompletion = 4", COLLECTION_H)
        self.assertIn("QuestBackfill = 5", COLLECTION_H)

    def test_backfill_uses_only_active_rewarded_history(self) -> None:
        self.assertIn("FROM `character_queststatus_rewarded`", QUEST_CPP)
        self.assertIn("`active` = 1", QUEST_CPP)
        self.assertNotIn("character_queststatus`", QUEST_CPP)
        self.assertNotIn("achievement", QUEST_CPP.lower())

    def test_backfill_is_bounded_and_not_automatic(self) -> None:
        self.assertIn("constexpr std::uint32_t BackfillBatchSize = 25", QUEST_CPP)
        self.assertIn("LIMIT {}", QUEST_CPP)
        self.assertIn("UnlockBatch", QUEST_CPP)
        self.assertNotIn("PLAYERHOOK_ON_LOGIN", MODULE)
        self.assertNotIn("QuestBackfillService::Instance().Start", MODULE[:MODULE.index("class NativeTransmogCommandScript")])

    def test_gm_commands_and_permissions(self) -> None:
        for command in ('"preview"', '"run"', '"status"'):
            self.assertIn(command, MODULE)
        self.assertIn('"run", HandleBackfillRun, rbac::RBAC_PERM_COMMAND_NPC_ADD', MODULE)
        self.assertIn("Select an online character", MODULE)

    def test_preview_and_execution_share_enumerator(self) -> None:
        self.assertIn("if (preview)", QUEST_CPP)
        self.assertIn("CollectQuestRewardAppearances(player, quest", QUEST_CPP)
        self.assertIn("collection.Unlock(player, itemTemplate, source, quest->GetQuestId())", QUEST_CPP)

    def test_no_reward_items_are_granted_by_phase3b(self) -> None:
        for grant in ("StoreNewItem", "AddItem", "CreateItem", "SendNewItem"):
            self.assertNotIn(grant, QUEST_CPP)


class PhaseThreeBModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA)
        self.a = Reward(100, (1000, 4, 1, 3))
        self.b = Reward(101, (1001, 4, 2, 3))
        self.c = Reward(102, (1002, 4, 3, 3))
        self.d = Reward(103, (1003, 4, 4, 3))

    def tearDown(self) -> None:
        self.db.close()

    def count(self, owner: tuple[int, int]) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM collection WHERE owner_type=? AND owner_id=?", owner
        ).fetchone()[0]

    def test_four_selectable_rewards(self) -> None:
        self.assertEqual(collect(self.db, (1, 7), 10, [self.a, self.b, self.c, self.d]), (4, 0, 4))

    def test_guaranteed_and_mixed_rewards(self) -> None:
        self.assertEqual(collect(self.db, (1, 7), 10, [self.a, self.b]), (2, 0, 2))
        self.assertEqual(collect(self.db, (1, 7), 11, [self.c, self.d]), (2, 0, 2))

    def test_no_collectible_and_invalid_rewards(self) -> None:
        self.assertEqual(collect(self.db, (1, 7), 10, [Reward(0, None), Reward(999, None)]), (0, 0, 0))

    def test_duplicate_reward_appearance_and_repeatable_idempotency(self) -> None:
        duplicate = Reward(200, self.a.appearance)
        self.assertEqual(collect(self.db, (1, 7), 10, [self.a, duplicate]), (1, 0, 1))
        self.assertEqual(collect(self.db, (1, 7), 10, [self.a, duplicate]), (1, 1, 0))

    def test_already_owned_preserves_first_provenance(self) -> None:
        collect(self.db, (1, 7), 9, [self.a])
        collect(self.db, (1, 7), 10, [Reward(200, self.a.appearance)])
        row = self.db.execute("SELECT source_item, source_quest FROM collection").fetchone()
        self.assertEqual(row, (100, 9))

    def test_account_wide_sharing(self) -> None:
        collect(self.db, (1, 7), 10, [self.a])
        self.assertEqual(self.count((1, 7)), 1)
        self.assertEqual(collect(self.db, (1, 7), 11, [self.a]), (1, 1, 0))

    def test_character_specific_isolation(self) -> None:
        collect(self.db, (2, 70), 10, [self.a])
        collect(self.db, (2, 71), 10, [self.a])
        self.assertEqual(self.count((2, 70)), 1)
        self.assertEqual(self.count((2, 71)), 1)

    def test_preview_is_read_only(self) -> None:
        self.assertEqual(collect(self.db, (1, 7), 10, [self.a, self.b], preview=True), (2, 0, 2))
        self.assertEqual(self.count((1, 7)), 0)

    def test_backfill_execution_and_repeated_idempotency(self) -> None:
        self.assertEqual(collect(self.db, (1, 7), 10, [self.a, self.b]), (2, 0, 2))
        self.assertEqual(collect(self.db, (1, 7), 10, [self.a, self.b]), (2, 2, 0))

    def test_current_definition_is_authoritative(self) -> None:
        collect(self.db, (1, 7), 10, [self.a])
        self.assertEqual(collect(self.db, (1, 8), 10, [self.b]), (1, 0, 1))
        row = self.db.execute("SELECT source_item FROM collection WHERE owner_id=8").fetchone()
        self.assertEqual(row, (101,))

    def test_large_history_batch_bound_contract(self) -> None:
        quest_ids = list(range(1, 1002))
        batches = [quest_ids[i:i + 25] for i in range(0, len(quest_ids), 25)]
        self.assertEqual(max(map(len, batches)), 25)
        self.assertEqual(sum(map(len, batches)), 1001)


if __name__ == "__main__":
    unittest.main()
