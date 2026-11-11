"""Focused contracts for NPC-authorized saved-outfit application."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APPLICATION = (ROOT / "src/NativeTransmogApplication.cpp").read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
HEADER = (ROOT / "src/NativeTransmogWardrobe.h").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text()


def apply_model(current, saved, valid):
    """All-or-nothing model: None means explicit hide; absent means unchanged."""
    if not all(valid.get(slot, False) for slot in saved):
        return dict(current), False
    result = dict(current)
    for slot, appearance in saved.items():
        if appearance is None:
            result.pop(slot, None)
        else:
            result[slot] = appearance
    return result, True


class SavedOutfitBehaviorTests(unittest.TestCase):
    def test_multi_slot_apply_hides_and_preserves_unspecified(self):
        current = {1: 100, 3: 300, 10: 1000, 11: 1100, 12: 1200, 13: 1300}
        saved = {1: 201, 3: None, 10: None, 11: 211, 12: 212}
        applied, ok = apply_model(current, saved, {slot: True for slot in saved})
        self.assertTrue(ok)
        self.assertEqual(applied, {1: 201, 11: 211, 12: 212, 13: 1300})

    def test_invalid_piece_prevents_every_write(self):
        current = {1: 100, 11: 1100, 12: 1200}
        saved = {1: 201, 11: 211, 12: 212}
        for rejected in (11, 12):  # uncollected and incompatible representatives
            validation = {slot: slot != rejected for slot in saved}
            self.assertEqual(apply_model(current, saved, validation), (current, False))


class ServerApplicationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.handler = WARDROBE[
            WARDROBE.index("void WardrobeService::HandleCustomApplyOutfit"):
            WARDROBE.index("void WardrobeService::HandleCustomPreview")
        ]
        cls.batch = APPLICATION[
            APPLICATION.index("ApplicationResult ApplicationService::ApplyBatch"):
            APPLICATION.index("void ApplicationService::LoadPlayer")
        ]
        cls.validation = APPLICATION[
            APPLICATION.index("std::vector<BatchValidation> ApplicationService::ValidateBatch"):
            APPLICATION.index("ApplicationResult ApplicationService::ApplyBatch")
        ]

    def test_one_request_loads_owned_set_and_uses_batch_service(self):
        self.assertIn('parts[2] == "CUSTOMAPPLYOUTFIT"', WARDROBE)
        self.assertNotIn("CUSTOMPREFLIGHT", WARDROBE)
        self.assertNotIn("CUSTOMCONFIRM", WARDROBE)
        self.assertIn("CustomSetService::Instance().Load(player, setId, set)", self.handler)
        self.assertIn("ValidateBatch", self.handler)
        self.assertIn("ApplyBatch", self.handler)

    def test_npc_authorization_and_duplicate_request_guard(self):
        self.assertIn("Service::Instance().ValidateSession(player, token)", self.handler)
        self.assertIn("ApplicationAuthorization::NpcSession", self.handler)
        self.assertIn("lastCustomApplyRequestId", HEADER)
        self.assertIn("DUPLICATE_REQUEST", self.handler)

    def test_hidden_empty_slot_is_valid_and_becomes_a_noop(self):
        hidden_branch = self.validation[
            self.validation.index("selection.state == OverrideState::Hidden"):
            self.validation.index("else if (result == ApplicationResult::Ok)")
        ]
        self.assertNotIn("!target", hidden_branch)
        self.assertIn("!target && selection.state == OverrideState::Hidden", self.batch)
        preview = WARDROBE[
            WARDROBE.index("void WardrobeService::HandleCustomPreview"):
            WARDROBE.index("void WardrobeService::HandleCustomSaveOutfit")
        ]
        self.assertLess(preview.index("piece.state == CustomSetSelectionState::Hidden"),
                        preview.index("else if (!target)"))

    def test_uncollected_and_incompatible_appearances_are_rejected(self):
        self.assertIn("ApplicationResult::AppearanceNotCollected", self.handler)
        self.assertIn("CollectionService::Instance().IsCollected(player, appearance)", self.validation)
        self.assertIn("CompatibilityValidator::Validate", self.validation)
        for marker in ("IsOneHandMeleeSubclass", "IsTwoHandMeleeSubclass"):
            self.assertIn(marker, APPLICATION)

    def test_no_partial_write_and_equipped_items_are_not_mutated(self):
        self.assertLess(self.handler.index("validation[index].result != ApplicationResult::Ok"),
                        self.handler.index("ApplyBatch"))
        self.assertIn("CharacterDatabase.BeginTransaction()", self.batch)
        self.assertIn("CharacterDatabase.DirectCommitTransaction(transaction)", self.batch)
        self.assertNotIn("EquipItem", self.batch)
        self.assertNotIn("DestroyItem", self.batch)
        self.assertNotIn("SetEntry", self.batch)


class ClientApplicationContractTests(unittest.TestCase):
    def test_button_is_explicit_and_only_enabled_for_loaded_valid_outfit(self):
        self.assertIn('text="Apply Outfit"', XML)
        self.assertIn("NativeTransmog_ApplySavedOutfit", XML)
        self.assertIn("savedSetReady==savedSetId and not pending", LUA)
        load = LUA[LUA.index("function NativeTransmog_LoadSavedSet"):
                   LUA.index("local function submitOutfitSave")]
        self.assertIn('sendRequest("CUSTOMPREVIEW"', load)
        self.assertNotIn('sendRequest("CUSTOMAPPLYOUTFIT"', load)

    def test_click_sends_one_request_and_pending_blocks_duplicates(self):
        click = LUA[LUA.index("function NativeTransmog_ApplySavedOutfit"):
                    LUA.index("function NativeTransmog_NextPage")]
        self.assertEqual(click.count('sendRequest("CUSTOMAPPLYOUTFIT"'), 1)
        self.assertIn("or pending then", click)
        self.assertIn("pending={operation=operation,started=GetTime()}", LUA)

    def test_success_failure_timeout_and_preview_remain_handled(self):
        self.assertIn('setStatus("Saved outfit applied."', LUA)
        self.assertIn('"Saved outfit application failed: "', LUA)
        self.assertIn('operation=="CUSTOMPREVIEW" then NativeTransmogWardrobeState.load=nil; savedSetReady=nil', LUA)
        self.assertIn("rebuildOutfitPreview(); refreshSelection()", LUA)
        self.assertIn("savedSetReady=#failures==0 and setId or nil", LUA)


if __name__ == "__main__":
    unittest.main()
