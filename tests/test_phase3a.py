#!/usr/bin/env python3
"""Phase 3A collection contracts and executable persistence-model tests."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
COLLECTION_CPP = (ROOT / "src/NativeTransmogCollection.cpp").read_text(encoding="utf-8")
COLLECTION_H = (ROOT / "src/NativeTransmogCollection.h").read_text(encoding="utf-8")
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text(encoding="utf-8")
CONFIG = (ROOT / "conf/mod_native_transmog.conf.dist").read_text(encoding="utf-8")
SQL_PATHS = (
    ROOT / "data/sql/db-characters/base/001_native_transmog_collection.sql",
    ROOT / "data/sql/db-characters/updates/2026_10_28_00_native_transmog_collection.sql",
)

SQLITE_SCHEMA = """
CREATE TABLE native_transmog_collection (
 owner_type INTEGER NOT NULL, owner_id INTEGER NOT NULL, display_id INTEGER NOT NULL,
 item_class INTEGER NOT NULL, item_subclass INTEGER NOT NULL, inventory_type INTEGER NOT NULL,
 source_item INTEGER NOT NULL, acquiring_character INTEGER NOT NULL,
 acquired_at INTEGER NOT NULL, acquisition_source INTEGER NOT NULL,
 PRIMARY KEY(owner_type, owner_id, display_id, item_class, item_subclass, inventory_type)
);
CREATE INDEX owner_category ON native_transmog_collection
 (owner_type, owner_id, item_class, inventory_type);
"""


def insert_unlock(db: sqlite3.Connection, owner_type: int, owner_id: int,
                  key: tuple[int, int, int, int], source_item: int, character: int) -> None:
    db.execute(
        "INSERT OR IGNORE INTO native_transmog_collection VALUES (?,?,?,?,?,?,?,?,?,?)",
        (owner_type, owner_id, *key, source_item, character, int(time.time()), 1),
    )
    db.commit()


class PhaseThreeAContractTests(unittest.TestCase):
    def test_character_database_schema_is_idempotent_and_independent(self) -> None:
        for path in SQL_PATHS:
            sql = path.read_text(encoding="utf-8")
            self.assertIn("CREATE TABLE IF NOT EXISTS `native_transmog_collection`", sql)
            self.assertIn(
                "PRIMARY KEY (`owner_type`, `owner_id`, `display_id`, `item_class`, `item_subclass`, `inventory_type`)",
                sql,
            )
            for column in ("source_item", "acquiring_character", "acquired_at", "acquisition_source"):
                self.assertIn(f"`{column}`", sql)
            self.assertNotIn("FOREIGN KEY", sql.upper())
            self.assertNotIn("mod_transmog", sql.lower().replace("native_transmog", ""))

    def test_configuration_defaults_and_scope_preservation(self) -> None:
        for line in (
            "NativeTransmog.Collection.Enable = 1",
            "NativeTransmog.Collection.AccountWide = 1",
            "NativeTransmog.Collection.UnlockOnAcquire = 1",
        ):
            self.assertIn(line, CONFIG)
        self.assertNotIn("DELETE FROM `native_transmog_collection`", COLLECTION_CPP)
        self.assertNotIn("UPDATE `native_transmog_collection` SET `owner_type`", COLLECTION_CPP)

    def test_authenticated_owner_and_cross_class_collection(self) -> None:
        self.assertIn("player->GetSession()->GetAccountId()", COLLECTION_CPP)
        self.assertIn("player->GetGUID().GetCounter()", COLLECTION_CPP)
        resolver = COLLECTION_CPP[COLLECTION_CPP.index("bool CollectionService::ResolveAppearance"):]
        resolver = resolver[:resolver.index("char const* CollectionService::SourceName")]
        for forbidden in ("AllowableClass", "RequiredSkill", "CanUseItem", "CanEquipItem", "getClass"):
            self.assertNotIn(forbidden, resolver)

    def test_composite_identity_and_safe_eligibility(self) -> None:
        for field in ("displayId", "itemClass", "itemSubclass", "inventoryType"):
            self.assertIn(field, COLLECTION_H)
        self.assertIn("ITEM_CLASS_ARMOR", COLLECTION_CPP)
        self.assertIn("ITEM_CLASS_WEAPON", COLLECTION_CPP)
        for excluded in ("INVTYPE_NECK", "INVTYPE_FINGER", "INVTYPE_TRINKET", "INVTYPE_BAG", "INVTYPE_AMMO", "INVTYPE_RELIC"):
            resolver = COLLECTION_CPP[COLLECTION_CPP.index("bool CollectionService::ResolveAppearance"):]
            resolver = resolver[:resolver.index("char const* CollectionService::SourceName")]
            self.assertNotIn(f"case {excluded}", resolver)
        self.assertIn("!itemTemplate || !itemTemplate->DisplayInfoID", resolver)
        self.assertIn("sItemDisplayInfoStore.LookupEntry(itemTemplate->DisplayInfoID)", resolver)
        self.assertIn("if (!player || !player->GetSession()", COLLECTION_CPP)

    def test_central_acquisition_hooks_and_synchronous_insert(self) -> None:
        for hook in (
            "PLAYERHOOK_ON_STORE_NEW_ITEM",
            "PLAYERHOOK_ON_AFTER_MOVE_ITEM_TO_INVENTORY",
            "PLAYERHOOK_ON_AFTER_STORE_OR_EQUIP_NEW_ITEM",
        ):
            self.assertIn(hook, MODULE)
        self.assertIn("CharacterDatabase.DirectExecute", COLLECTION_CPP)
        self.assertIn("INSERT IGNORE", COLLECTION_CPP)
        self.assertNotIn("PLAYERHOOK_ON_LOGIN", MODULE)

    def test_query_api_filtering_order_and_missing_source_safety(self) -> None:
        for method in ("IsCollected", "List", "Count", "GetProvenance", "ResolveSourceItem"):
            self.assertIn(method, COLLECTION_H)
        self.assertIn("ORDER BY `item_class`, `inventory_type`, `item_subclass`, `display_id`", COLLECTION_CPP)
        self.assertIn("source ? \"\" : \" (template missing)\"", MODULE)

    def test_gm_commands_are_read_only_bounded_and_permissioned(self) -> None:
        for command in ('"info"', '"list"', '"count"'):
            self.assertIn(command, MODULE)
        self.assertGreaterEqual(MODULE.count("RBAC_PERM_COMMAND_NPC_INFO"), 5)
        self.assertIn("constexpr std::uint32_t PageSize = 50", MODULE)
        command_section = MODULE[MODULE.index("static ChatCommandTable collectionCommands"):]
        command_section = command_section[:command_section.index("static ChatCommandTable rootCommands")]
        self.assertNotIn("grant", command_section.lower())
        self.assertNotIn("remove", command_section.lower())


class PhaseThreeAPersistenceModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SQLITE_SCHEMA)

    def tearDown(self) -> None:
        self.db.close()

    def count(self, owner_type: int, owner_id: int) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM native_transmog_collection WHERE owner_type=? AND owner_id=?",
            (owner_type, owner_id),
        ).fetchone()[0]

    def test_account_wide_duplicate_and_shared_visual_identity(self) -> None:
        key = (1234, 4, 1, 5)
        insert_unlock(self.db, 1, 77, key, 100, 10)
        insert_unlock(self.db, 1, 77, key, 101, 11)
        self.assertEqual(self.count(1, 77), 1)
        row = self.db.execute("SELECT source_item, acquiring_character FROM native_transmog_collection").fetchone()
        self.assertEqual(row, (100, 10), "first provenance must remain stable")

    def test_character_scope_isolation_and_scope_switching(self) -> None:
        key = (1234, 4, 1, 5)
        insert_unlock(self.db, 1, 77, key, 100, 10)
        insert_unlock(self.db, 2, 10, key, 100, 10)
        self.assertEqual(self.count(2, 11), 0)
        insert_unlock(self.db, 2, 11, (2234, 4, 4, 5), 200, 11)
        self.assertEqual(self.count(1, 77), 1)
        self.assertEqual(self.count(2, 10), 1)
        self.assertEqual(self.count(2, 11), 1)

    def test_incompatible_categories_with_same_display_do_not_merge(self) -> None:
        insert_unlock(self.db, 1, 77, (1234, 4, 1, 5), 100, 10)
        insert_unlock(self.db, 1, 77, (1234, 4, 4, 5), 101, 10)
        insert_unlock(self.db, 1, 77, (1234, 2, 7, 13), 102, 10)
        self.assertEqual(self.count(1, 77), 3)

    def test_persistence_across_reopen_and_filtering(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".sqlite") as handle:
            db = sqlite3.connect(handle.name)
            db.executescript(SQLITE_SCHEMA)
            insert_unlock(db, 1, 77, (1234, 4, 1, 5), 100, 10)
            db.close()
            db = sqlite3.connect(handle.name)
            rows = db.execute(
                "SELECT display_id FROM native_transmog_collection "
                "WHERE owner_type=1 AND owner_id=77 AND item_class=4 AND inventory_type=5 "
                "ORDER BY item_class, inventory_type, item_subclass, display_id"
            ).fetchall()
            db.close()
        self.assertEqual(rows, [(1234,)])

    def test_large_collection_uses_owner_index(self) -> None:
        self.db.executemany(
            "INSERT INTO native_transmog_collection VALUES (?,?,?,?,?,?,?,?,?,?)",
            ((1, 77, i, 4, i % 7, 1 + i % 20, i, 10, 1, 1) for i in range(10_000)),
        )
        plan = self.db.execute(
            "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM native_transmog_collection "
            "WHERE owner_type=1 AND owner_id=77 AND item_class=4 AND inventory_type=5"
        ).fetchall()
        self.assertTrue(any("INDEX" in row[-1].upper() for row in plan), plan)
        self.assertEqual(self.count(1, 77), 10_000)


if __name__ == "__main__":
    unittest.main()
