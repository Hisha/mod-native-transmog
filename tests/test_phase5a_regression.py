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
    def test_protocol_version_compatibility(self):
        self.assertEqual(protocol_version(), "3")
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
        state_branch = LUA[LUA.index('if command=="STATE"'):LUA.index('elseif command=="SETPAGE"')]
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
