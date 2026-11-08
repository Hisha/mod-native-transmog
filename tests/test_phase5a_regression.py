#!/usr/bin/env python3
"""Phase 5A protocol regression coverage for login, NPC open, state, sets, and tooltips."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = (ROOT / "src/NativeTransmogProtocol.h").read_text()
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text()
SERVICE = (ROOT / "src/NativeTransmogService.cpp").read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text()


class SetResponseModel:
    """Small executable model of the Lua request ownership/state rules."""

    def __init__(self):
        self.request_id = 0
        self.active = None
        self.rows = {}
        self.visible = []
        self.shown = True

    def begin(self, kind, set_id=None, expected=0):
        self.request_id += 1
        self.active = dict(id=self.request_id, kind=kind, set_id=set_id, expected=expected)
        self.rows = {}
        return self.request_id

    def row(self, request_id, index, value):
        if not self.shown or not self.active or request_id != self.active["id"]:
            return
        if 1 <= index <= 32:
            self.rows[index] = value

    def finish(self, request_id):
        if not self.shown or not self.active or request_id != self.active["id"]:
            return False
        expected = self.active["expected"]
        result = [self.rows[index] for index in range(1, expected + 1) if index in self.rows]
        self.active = None
        if len(result) != expected:
            return False
        self.visible = result
        return True

    def close(self):
        self.shown = False
        self.request_id += 1
        self.active = None


class SetNavigationModel:
    """Executable model of independent page and detail request state."""

    def __init__(self):
        self.page = 0
        self.next_page = 8
        self.has_next = True
        self.history = []
        self.filter = 0
        self.page_request = None
        self.detail_request = None
        self.selected = None
        self.request_id = 0

    def select(self, set_id):
        self.request_id += 1
        self.selected = set_id
        self.detail_request = (self.request_id, set_id)
        return self.request_id

    def change_filter(self, value):
        self.filter = value
        self.history = []
        return self.request_page(0)

    def request_page(self, page):
        self.request_id += 1
        self.page_request = (self.request_id, self.filter, page)
        self.detail_request = None
        self.selected = None
        return self.request_id

    def finish_detail(self, request_id, set_id):
        if self.detail_request != (request_id, set_id):
            return False
        self.detail_request = None
        return True


def protocol_version() -> str:
    match = re.search(r"constexpr std::uint32_t Version = (\d+);", PROTOCOL)
    if not match:
        raise AssertionError("shared protocol version is missing")
    return match.group(1)


def client_version() -> str:
    match = re.search(r'local PREFIX, VERSION = "NTRANSMOG", "(\d+)"', LUA)
    if not match:
        raise AssertionError("client protocol version is missing")
    return match.group(1)


def response_commands() -> set[str]:
    body = MODULE[MODULE.index("bool IsNativeTransmogResponse"):MODULE.index("void RefreshOnlineVisibleEquipment")]
    return set(re.findall(r'command == "([A-Z]+)"', body))


class PhaseFiveAProtocolRegressionTests(unittest.TestCase):
    def test_xml_generated_pagination_names_match_lua_globals(self):
        self.assertIn('<Button name="NativeTransmogCollectionsFramePrevious"', XML)
        self.assertIn("NativeTransmogCollectionsFramePrevious", LUA)
        self.assertIn("NativeTransmogCollectionsFrameNext", LUA)
        self.assertNotIn("NativeTransmogFrameSetsPrevious", LUA)

    def test_set_response_lifecycle_is_bounded_and_request_owned(self):
        for marker in ("activeSetPageRequest", "activeSetDetailRequest", "matchingSetRequest",
                       "cancelSetRequest", "SET_PAGE_SIZE", "MAXIMUM_SET_PIECES"):
            self.assertIn(marker, LUA)
        self.assertIn('request.phase~="PAGE"', LUA)
        self.assertIn('request.phase~="ROWS"', LUA)
        self.assertIn('request.phase~="INFO"', LUA)
        self.assertIn('request.phase~="PIECES"', LUA)
        self.assertIn("incomingPieces[pieceIndex]=", LUA)
        self.assertIn("#completedPieces~=selectedSet.total", LUA)
        self.assertIn("setPieces={}; setStatus", LUA)

    def test_selection_preserves_catalog_navigation_and_filter(self):
        state = SetNavigationModel()
        state.page = 16
        state.next_page = 24
        state.history = [0, 8]
        state.filter = 1
        request = state.select(217)
        self.assertEqual((state.page, state.next_page, state.history, state.filter), (16, 24, [0, 8], 1))
        self.assertTrue(state.has_next)
        self.assertTrue(state.finish_detail(request, 217))
        self.assertTrue(state.has_next)

    def test_filter_intentionally_resets_page_and_cancels_detail(self):
        state = SetNavigationModel()
        state.page = 16
        state.history = [0, 8]
        state.select(217)
        state.change_filter(2)
        self.assertEqual(state.filter, 2)
        self.assertEqual(state.history, [])
        self.assertIsNone(state.detail_request)
        self.assertEqual(state.page_request[2], 0)

    def test_delayed_detail_and_rapid_switching_are_request_owned(self):
        state = SetNavigationModel()
        first = state.select(217)
        second = state.select(875)
        self.assertFalse(state.finish_detail(first, 217))
        self.assertEqual(state.selected, 875)
        self.assertTrue(state.finish_detail(second, 875))
        self.assertEqual(state.page, 0)

    def test_repeated_responses_and_maximum_size_are_idempotent(self):
        state = SetResponseModel()
        request = state.begin("SETDETAIL", 217, 32)
        for index in range(1, 33):
            state.row(request, index, index)
            state.row(request, index, index)  # repeated SETPIECE replaces, never appends
        self.assertTrue(state.finish(request))
        self.assertEqual(state.visible, list(range(1, 33)))
        self.assertFalse(state.finish(request))  # repeated terminator is stale

    def test_rapid_selection_close_and_late_messages_cannot_replace_current_rows(self):
        state = SetResponseModel()
        first = state.begin("SETDETAIL", 217, 8)
        state.row(first, 1, "judgement")
        second = state.begin("SETDETAIL", 875, 5)
        state.row(first, 2, "stale")
        for index in range(1, 6):
            state.row(second, index, f"t9-{index}")
        self.assertTrue(state.finish(second))
        self.assertEqual(state.visible, [f"t9-{index}" for index in range(1, 6)])
        late = state.begin("SETS", expected=8)
        state.close()
        state.row(late, 1, "late")
        self.assertFalse(state.finish(late))

    def test_pagination_replaces_only_the_requested_page(self):
        state = SetResponseModel()
        first = state.begin("SETS", expected=8)
        for index in range(1, 9):
            state.row(first, index, index)
        self.assertTrue(state.finish(first))
        second = state.begin("SETS", expected=2)
        state.row(first, 1, "old page")
        state.row(second, 1, 9)
        state.row(second, 2, 10)
        self.assertTrue(state.finish(second))
        self.assertEqual(state.visible, [9, 10])

    def test_protocol_version_compatibility(self):
        self.assertEqual(protocol_version(), "4")
        self.assertEqual(client_version(), protocol_version())
        self.assertIn("version != protocol::Version", WARDROBE)
        self.assertIn("std::to_string(protocol::Version)", SERVICE)
        self.assertNotIn('"\\t2\\tOPEN\\t"', SERVICE)
        self.assertNotIn('"NTRANSMOG\\t2\\t', MODULE)

    def test_login_sync_reaches_state_delivery(self):
        entering_world = LUA[LUA.index('event=="PLAYER_ENTERING_WORLD"'):LUA.index("local prefix,message,channel,sender")]
        self.assertIn('VERSION.."\\tSYNC"', entering_world)
        self.assertIn('parts[2] == "SYNC" && fields.empty()', WARDROBE)
        self.assertIn("SendEquipmentState(player, 0)", WARDROBE)
        self.assertIn("STATE", response_commands())

    def test_npc_open_uses_the_shared_version_and_reaches_lua(self):
        send_open = SERVICE[SERVICE.index("void Service::SendOpen"):SERVICE.index("void Service::SendClose")]
        self.assertIn("protocol::Version", send_open)
        self.assertIn('"\\tOPEN\\t"', send_open)
        self.assertIn("OPEN", response_commands())
        self.assertIn('command=="OPEN" and fields[3]', LUA)
        self.assertIn("WardrobeService::Instance().SendEquipmentState(player, token)", SERVICE)

    def test_state_delivery_restores_tooltip_state(self):
        state_branch = LUA[LUA.index('if command=="STATE"'):LUA.index('elseif string.sub(command,1,6)=="CUSTOM"')]
        self.assertIn('fields[3]~="0"', state_branch)
        self.assertIn("overrideStates[wireSlot]", state_branch)
        tooltip = LUA[LUA.index("local function appearanceTooltipText"):LUA.index("local function updateEquipmentSlot")]
        self.assertIn("overrideStates[wireSlot]", tooltip)
        self.assertIn('return "Appearance: Hidden"', tooltip)
        self.assertIn('return "Transmogrified to: "..name', tooltip)

    def test_phase5a_set_browsing_responses_are_all_dispatched(self):
        emitted = set(re.findall(r'Send\(player, "(SET[A-Z]*)\\t', WARDROBE))
        expected = {"SETPAGE", "SET", "SETEND", "SETINFO", "SETPIECE", "SETDETAILEND"}
        self.assertEqual(emitted, expected)
        self.assertTrue(emitted <= response_commands())
        for command in expected:
            self.assertIn(f'command=="{command}"', LUA)
        self.assertIn('sendReadOnly("SETS"', LUA)
        self.assertIn('sendReadOnly("SETDETAIL"', LUA)

    def test_request_and_response_vocabularies_do_not_overlap(self):
        requests = set(re.findall(r'parts\[2\] == "([A-Z]+)"', WARDROBE))
        self.assertTrue({"SYNC", "CAT", "SETS", "SETDETAIL", "APPLY", "HIDE", "REMOVE"} <= requests)
        self.assertFalse(requests & response_commands())


if __name__ == "__main__":
    unittest.main()
