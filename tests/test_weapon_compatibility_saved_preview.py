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
SAVED_SLOTS = tuple(range(1, 13)) + (14,)
HIDDEN_SLOTS = {3, 10}


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


def saved_fixture():
    """Representative 13-piece outfit: two hides and only Ranged unspecified."""
    return {
        slot: {"state": 1, "entry": 0} if slot in HIDDEN_SLOTS
        else {"state": 0, "entry": 5000 + slot}
        for slot in SAVED_SLOTS
    }


def preview_wire_rows(pieces):
    return [(index, slot, piece["state"], piece["entry"], "ok")
            for index, (slot, piece) in enumerate(pieces.items(), 1)]


def decode_preview(rows):
    loaded = {}
    for _, slot, state, entry, result in rows:
        if result == "ok" and (state == 1 or entry > 0):
            loaded[slot] = {"is_hide": state == 1, "entry": entry}
    return loaded


def reconstruct_preview(physical, selections):
    """Model the fallback's baseline-first, selections-second reconstruction."""
    rendered = dict(physical)
    for slot, selection in selections.items():
        if selection["is_hide"]:
            rendered.pop(slot, None)
    for slot, selection in selections.items():
        if not selection["is_hide"]:
            rendered[slot] = selection["entry"]
    return rendered


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

    def test_thirteen_saved_states_survive_wire_decode_with_slot_identity(self):
        pieces = saved_fixture()
        decoded = decode_preview(preview_wire_rows(pieces))
        self.assertEqual(set(decoded), set(SAVED_SLOTS))
        for slot in SAVED_SLOTS:
            self.assertEqual(decoded[slot]["entry"], pieces[slot]["entry"])

    def test_hide_and_unspecified_remain_three_distinct_states(self):
        decoded = decode_preview(preview_wire_rows(saved_fixture()))
        self.assertTrue(decoded[3]["is_hide"])
        self.assertTrue(decoded[10]["is_hide"])
        self.assertNotIn(13, decoded)
        self.assertNotEqual(decoded.get(13), decoded[3])

    def test_fallback_rebuild_keeps_every_saved_appearance_after_hides(self):
        decoded = decode_preview(preview_wire_rows(saved_fixture()))
        physical = {slot: 9000 + slot for slot in range(1, 15)}
        first = reconstruct_preview(physical, decoded)
        refreshed = reconstruct_preview(physical, decoded)
        expected_selected = {slot: 5000 + slot for slot in SAVED_SLOTS
                             if slot not in HIDDEN_SLOTS}
        self.assertEqual({slot: first[slot] for slot in expected_selected}, expected_selected)
        self.assertNotIn(3, first)
        self.assertNotIn(10, first)
        self.assertEqual(first[13], physical[13])
        self.assertEqual(refreshed, first)
        self.assertEqual((first[11], first[12]), (5011, 5012))

        preview = LUA[LUA.index("local function prepareOutfitModel"):
                      LUA.index("local function twoLineAppearanceLabel")]
        self.assertLess(preview.index("prepareOutfitModel(model,selections)"),
                        preview.index("applyOutfitAppearance(model,wireSlot,selections[wireSlot])"))
        self.assertIn("NativeTransmog_RebuildModelOutfit(model,NativeTransmogWardrobeState.selections)", LUA)
        self.assertIn("local current=overrideStates[wireSlot]", preview)
        self.assertIn("current.state==1", preview)
        self.assertIn("current.state~=2", preview)

    def test_collections_normal_view_keeps_slot_state_for_tooltips(self):
        renderer = LUA[LUA.index("renderPieces=function()"):
                       LUA.index("local function requestSets")]
        piece_row = LUA.index("local function createPieceRow")
        tooltip = LUA[LUA.index('row:SetScript("OnEnter"', piece_row):
                      LUA.index('row:SetScript("OnLeave"', piece_row)]
        self.assertIn("for wireSlot=1,#SLOT_ORDER", renderer)
        self.assertIn("piecesBySlot[piece.slot]=piece", renderer)
        self.assertIn("row.savedSlot=wireSlot", renderer)
        self.assertIn('slotName.." — Hide Appearance"', tooltip)
        self.assertIn('slotName.." — Unspecified"', tooltip)
        self.assertIn('slotName.." — Saved Appearance"', tooltip)
        self.assertIn('self.savedSlot==10 and "cloak"', tooltip)

    def test_completion_errors_and_timeout_clear_request_state(self):
        self.assertIn('piece.result=="ok"', LUA)
        self.assertIn('"; unavailable: "', LUA)
        self.assertIn('operation=="CUSTOMPREVIEW" then NativeTransmogWardrobeState.load=nil', LUA)
        self.assertIn("NativeTransmogWardrobeState.load=nil; pending=nil", LUA)

    def test_preview_load_is_read_only_and_terminates(self):
        load = LUA[LUA.index("function NativeTransmog_LoadSavedSet"):
                   LUA.index("local function submitOutfitSave")]
        self.assertIn('sendRequest("CUSTOMPREVIEW"', load)
        self.assertNotIn('sendRequest("APPLY"', load)
        self.assertNotIn('sendRequest("CUSTOMCONFIRM"', load)
        completion = LUA[LUA.index('elseif command=="CUSTOMPREVIEWEND"'):
                         LUA.index('elseif command=="CUSTOMPAGE"')]
        self.assertIn("NativeTransmogWardrobeState.load=nil; pending=nil", completion)


if __name__ == "__main__":
    unittest.main()
