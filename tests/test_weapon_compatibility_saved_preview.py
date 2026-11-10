#!/usr/bin/env python3
"""Focused regressions for grouped weapons and NPC saved-outfit preview loading."""

from dataclasses import dataclass
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APPLICATION = (ROOT / "src/NativeTransmogApplication.cpp").read_text()
CUSTOM = (ROOT / "src/NativeTransmogCustomSet.cpp").read_text()
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
ONE_HAND = {0, 4, 7}
TWO_HAND = {1, 5, 6, 8}


@dataclass(frozen=True)
class Appearance:
    subclass: int
    collected: bool = True
    proficient: bool = True
    name: str = "appearance"


def compatible_subclasses(target_subclass: int, two_hand: bool) -> set[int]:
    group = TWO_HAND if two_hand else ONE_HAND
    return group if target_subclass in group else {target_subclass}


def catalog(rows, target_subclass, two_hand, query="", cursor=0, page_size=2):
    subclasses = compatible_subclasses(target_subclass, two_hand)
    matches = [row for row in rows if row.collected and row.proficient and
               row.subclass in subclasses and query.lower() in row.name.lower()]
    return matches[cursor:cursor + page_size], len(matches)


class WeaponCompatibilityTests(unittest.TestCase):
    def test_paladin_one_hand_and_two_hand_groups(self):
        rows = [Appearance(0), Appearance(4), Appearance(7), Appearance(1),
                Appearance(5), Appearance(6), Appearance(8)]
        one, _ = catalog(rows, 7, False, page_size=20)
        two, _ = catalog(rows, 8, True, page_size=20)
        self.assertEqual({row.subclass for row in one}, ONE_HAND)
        self.assertEqual({row.subclass for row in two}, TWO_HAND)

    def test_incompatible_uncollected_and_unproficient_are_excluded(self):
        rows = [Appearance(4), Appearance(7, collected=False),
                Appearance(0, proficient=False), Appearance(6)]
        page, total = catalog(rows, 7, False, page_size=20)
        self.assertEqual((page, total), ([Appearance(4)], 1))

    def test_search_filters_full_group_before_pagination(self):
        rows = [Appearance(0, name="first axe"), Appearance(7, name="first sword"),
                Appearance(4, name="later judgement mace")]
        page, total = catalog(rows, 7, False, query="judgement", page_size=1)
        self.assertEqual((page[0].subclass, total), (4, 1))
        handler = WARDROBE[WARDROBE.index("void WardrobeService::HandleCatalog"):
                           WARDROBE.index("void WardrobeService::HandleHide")]
        self.assertLess(handler.index("ResolveCanonical"), handler.index("matched >= cursor"))

    def test_catalog_and_application_share_explicit_groups(self):
        self.assertIn("CompatibleWeaponSubclasses(itemTemplate)", WARDROBE)
        for marker in ("ITEM_SUBCLASS_WEAPON_AXE", "ITEM_SUBCLASS_WEAPON_MACE",
                       "ITEM_SUBCLASS_WEAPON_SWORD", "ITEM_SUBCLASS_WEAPON_POLEARM"):
            self.assertIn(marker, APPLICATION)
        self.assertIn("CompatibleWeaponSubclasses(itemTemplate)", WARDROBE)
        self.assertIn("ValidateForTarget", WARDROBE)
        self.assertIn("CompatibilityValidator::Validate", APPLICATION)

    def test_handedness_and_security_rejections_remain(self):
        validator = APPLICATION[APPLICATION.index("ApplicationResult CompatibilityValidator::Validate"):
                                APPLICATION.index("ApplicationService& ApplicationService::Instance")]
        self.assertIn("targetOneHand && sourceTwoHand", validator)
        self.assertIn("return ApplicationResult::TwoHandOnOneHandDisabled", validator)
        self.assertIn("targetTwoHand && sourceOneHand", validator)
        self.assertIn("return ApplicationResult::OneHandOnTwoHandDisabled", validator)
        apply = APPLICATION[APPLICATION.index("ApplicationResult ApplicationService::Apply"):
                            APPLICATION.index("ApplicationResult ApplicationService::Hide")]
        self.assertLess(apply.index("IsCollected(player, appearance)"),
                        apply.index("CompatibilityValidator::Validate"))


class SavedPreviewTests(unittest.TestCase):
    def test_preview_response_vocabulary_reaches_framexml(self):
        for command in ("CUSTOMPREVIEWINFO", "CUSTOMPREVIEWPIECE", "CUSTOMPREVIEWEND"):
            self.assertIn(f'command == "{command}"', MODULE)

    def test_preview_rechecks_ownership_and_target_compatibility(self):
        self.assertIn("IsCollected(player, piece.appearance)", CUSTOM)
        preview = WARDROBE[WARDROBE.index("void WardrobeService::HandleCustomPreview"):
                           WARDROBE.index("void WardrobeService::HandleCustomSaveOutfit")]
        self.assertIn("GetItemByPos", preview)
        self.assertIn("ValidateForTarget", preview)
        self.assertIn("ApplicationService::ResultName(result)", preview)

    def test_multi_slot_mapping_preserves_valid_mace_and_shield(self):
        handler = LUA[LUA.index('if command=="CUSTOMPREVIEWINFO"'):
                      LUA.index('elseif command=="CUSTOMPAGE"')]
        self.assertIn("loaded[piece.slot]", handler)
        self.assertIn("NativeTransmogWardrobeState.selections=loaded", handler)
        self.assertIn("rebuildOutfitPreview()", handler)
        selections = {slot: entry for slot, entry, result in
                      ((11, 1001, "ok"), (12, 1002, "ok"),
                       (1, 0, "appearance is not collected")) if result == "ok"}
        self.assertEqual(selections, {11: 1001, 12: 1002})

    def test_completion_errors_and_timeout_clear_request_state(self):
        self.assertIn('piece.result=="ok"', LUA)
        self.assertIn('"; unavailable: "', LUA)
        self.assertIn('operation=="CUSTOMPREVIEW" then NativeTransmogWardrobeState.load=nil', LUA)
        self.assertIn("NativeTransmogWardrobeState.load=nil; pending=nil", LUA)


if __name__ == "__main__":
    unittest.main()
