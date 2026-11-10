#!/usr/bin/env python3
"""Phase 3C application contracts and executable persistence/compatibility models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP_CPP = (ROOT / "src/NativeTransmogApplication.cpp").read_text(encoding="utf-8")
APP_H = (ROOT / "src/NativeTransmogApplication.h").read_text(encoding="utf-8")
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text(encoding="utf-8")
CONFIG = (ROOT / "conf/mod_native_transmog.conf.dist").read_text(encoding="utf-8")
SQL_PATHS = (
    ROOT / "data/sql/db-characters/base/002_native_transmog_item_override.sql",
    ROOT / "data/sql/db-characters/updates/2026_11_01_00_native_transmog_item_override.sql",
)

SCHEMA = """
CREATE TABLE native_transmog_item_override (
 item_guid INTEGER PRIMARY KEY, owner_guid INTEGER NOT NULL, appearance_item INTEGER NOT NULL,
 display_id INTEGER NOT NULL, item_class INTEGER NOT NULL, item_subclass INTEGER NOT NULL,
 inventory_type INTEGER NOT NULL, applied_at INTEGER NOT NULL
);
"""


@dataclass(frozen=True)
class ItemKind:
    item_class: int
    subclass: int
    inventory: int


def compatible(target: ItemKind, source: ItemKind) -> bool:
    if target.item_class != source.item_class:
        return False
    if target.item_class == 4:
        return target.subclass == source.subclass and (
            target.inventory == source.inventory or {target.inventory, source.inventory} == {5, 20}
        )
    target_one, source_one = target.inventory in {13, 21, 22}, source.inventory in {13, 21, 22}
    target_two, source_two = target.inventory == 17, source.inventory == 17
    if target_one and source_two:
        return False
    if target_two and source_one:
        return False
    if target_one and source_one:
        return ((target.subclass in {0, 4, 7} and source.subclass in {0, 4, 7}) or
                target.subclass == source.subclass)
    if target_two and source_two:
        return ((target.subclass in {1, 5, 6, 8} and source.subclass in {1, 5, 6, 8}) or
                target.subclass == source.subclass)
    return target.subclass == source.subclass and target.inventory == source.inventory


class PhaseThreeCContractTests(unittest.TestCase):
    def test_independent_item_instance_schema(self) -> None:
        for path in SQL_PATHS:
            sql = path.read_text(encoding="utf-8")
            self.assertIn("CREATE TABLE IF NOT EXISTS `native_transmog_item_override`", sql)
            self.assertIn("PRIMARY KEY (`item_guid`)", sql)
            for column in ("owner_guid", "appearance_item", "display_id", "item_class",
                           "item_subclass", "inventory_type", "applied_at"):
                self.assertIn(f"`{column}`", sql)
            self.assertNotIn("FOREIGN KEY", sql.upper())
            self.assertNotIn("custom_transmogrification", sql)

    def test_server_authority_and_collection_ownership(self) -> None:
        self.assertIn("ApplicationAuthorization::GmDiagnostic", MODULE)
        self.assertIn("Service::Instance().ValidateSession(player)", APP_CPP)
        self.assertIn("CollectionService::Instance().IsCollected(player, appearance)", APP_CPP)
        self.assertNotIn("ownerGuid, appearance", APP_H)

    def test_compatibility_is_revalidated_server_side(self) -> None:
        validate = APP_CPP[APP_CPP.index("ApplicationResult CompatibilityValidator::Validate"):]
        validate = validate[:validate.index("ApplicationService& ApplicationService::Instance")]
        for contract in ("AllowableClass", "AllowableRace", "RequiredSkill", "RequiredSpell",
                         "GetArmorProficiency", "GetWeaponProficiency",
                         "ArmorSubclassMismatch", "WeaponSubclassMismatch",
                         "IsOneHandMeleeSubclass", "IsTwoHandMeleeSubclass"):
            self.assertIn(contract, validate if contract != "AllowableClass" else APP_CPP)

    def test_lifecycle_and_visible_synchronization_hooks(self) -> None:
        for hook in ("PLAYERHOOK_ON_LOGIN", "PLAYERHOOK_ON_AFTER_SET_VISIBLE_ITEM_SLOT",
                     "PLAYERHOOK_ON_AFTER_MOVE_ITEM_FROM_INVENTORY",
                     "GLOBALHOOK_ON_ITEM_DEL_FROM_DB", "GLOBALHOOK_ON_MIRRORIMAGE_DISPLAY_ITEM"):
            self.assertIn(hook, MODULE)
        self.assertIn("PLAYER_VISIBLE_ITEM_1_ENTRYID", APP_CPP)
        self.assertIn("transaction->Append", APP_CPP)
        self.assertIn("player->SetVisibleItemSlot", APP_CPP)

    def test_application_persists_before_cache_and_render(self) -> None:
        apply = APP_CPP[APP_CPP.index("ApplicationResult ApplicationService::Apply"):]
        apply = apply[:apply.index("ApplicationResult ApplicationService::Remove")]
        self.assertLess(apply.index("CharacterDatabase.DirectExecute"), apply.index("_overrides["))
        self.assertLess(apply.index("_overrides["), apply.index("SetVisibleItemSlot"))
        self.assertIn("ON DUPLICATE KEY UPDATE", apply)

    def test_safe_removal_and_gm_diagnostics(self) -> None:
        self.assertIn('"apply", HandleAppearanceApply, rbac::RBAC_PERM_COMMAND_NPC_ADD', MODULE)
        self.assertIn('"remove", HandleAppearanceRemove, rbac::RBAC_PERM_COMMAND_NPC_DELETE', MODULE)
        self.assertIn('"info", HandleAppearanceInfo, rbac::RBAC_PERM_COMMAND_NPC_INFO', MODULE)
        self.assertIn("AND `owner_guid` = {}", APP_CPP)
        self.assertIn("NoOverride", APP_H)

    def test_configuration_directions_are_independent(self) -> None:
        self.assertIn("NativeTransmog.Application.Enable = 1", CONFIG)
        self.assertIn("NativeTransmog.AllowTwoHandAppearanceOnOneHand = 0", CONFIG)
        self.assertIn("NativeTransmog.AllowOneHandAppearanceOnTwoHand = 0", CONFIG)

    def test_no_legacy_integration_or_core_resource_ids(self) -> None:
        combined = APP_CPP + APP_H + MODULE + "".join(path.read_text() for path in SQL_PATHS)
        self.assertNotIn("custom_transmogrification", combined)
        self.assertNotIn("mod-transmog", combined)


class PhaseThreeCModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA)

    def tearDown(self) -> None:
        self.db.close()

    def upsert(self, item_guid: int, owner: int, appearance: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO native_transmog_item_override VALUES (?,?,?,?,?,?,?,?)",
            (item_guid, owner, appearance, appearance + 1000, 4, 1, 5, 1),
        )
        self.db.commit()

    def test_item_instance_reapplication_is_idempotent(self) -> None:
        self.upsert(10, 7, 100)
        self.upsert(10, 7, 101)
        self.assertEqual(self.db.execute(
            "SELECT owner_guid, appearance_item FROM native_transmog_item_override"
        ).fetchall(), [(7, 101)])

    def test_transfer_and_delete_cleanup(self) -> None:
        self.upsert(10, 7, 100)
        self.db.execute("DELETE FROM native_transmog_item_override WHERE item_guid=?", (10,))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM native_transmog_item_override").fetchone()[0], 0)

    def test_armor_subclass_and_chest_robe_rules(self) -> None:
        self.assertTrue(compatible(ItemKind(4, 1, 5), ItemKind(4, 1, 20)))
        self.assertFalse(compatible(ItemKind(4, 1, 5), ItemKind(4, 2, 5)))
        self.assertFalse(compatible(ItemKind(4, 1, 3), ItemKind(4, 1, 5)))

    def test_weapon_groups_cross_subclass_but_never_handedness(self) -> None:
        one = ItemKind(2, 0, 13)
        two = ItemKind(2, 1, 17)
        self.assertFalse(compatible(one, two))
        self.assertFalse(compatible(two, one))
        self.assertTrue(compatible(one, ItemKind(2, 4, 13)))
        self.assertTrue(compatible(one, ItemKind(2, 7, 13)))
        self.assertTrue(compatible(two, ItemKind(2, 5, 17)))
        self.assertTrue(compatible(two, ItemKind(2, 6, 17)))
        self.assertTrue(compatible(two, ItemKind(2, 8, 17)))
        self.assertFalse(compatible(one, ItemKind(2, 15, 13)))


if __name__ == "__main__":
    unittest.main()
