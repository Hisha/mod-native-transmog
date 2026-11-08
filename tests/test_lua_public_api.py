#!/usr/bin/env python3
"""Lua 5.1 compilation and Native Transmog public callback regressions."""

from pathlib import Path
import unittest
import zipfile

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
LUA_PATH = ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua"
EPF_PATH = ROOT / "content/mod-native-transmog.epf"
LUA_MEMBER = "client/Interface/FrameXML/NativeTransmogFrame.lua"
PUBLIC_CALLBACKS = (
    "NativeTransmog_EndRotation",
    "NativeTransmog_OpenCollections",
    "NativeTransmog_OpenAuthorized",
)


def load_client_lua(source: str) -> LuaRuntime:
    lua = LuaRuntime()
    lua.globals().StaticPopupDialogs = lua.table()
    lua.globals().SlashCmdList = lua.table()
    lua.execute(source)
    return lua


class LuaPublicApiTests(unittest.TestCase):
    def test_source_compiles_under_lua51_and_exports_callbacks(self) -> None:
        lua = load_client_lua(LUA_PATH.read_text(encoding="utf-8"))
        lua_type = lua.eval("type")
        for callback in PUBLIC_CALLBACKS:
            with self.subTest(callback=callback):
                self.assertEqual(lua_type(lua.globals()[callback]), "function")

    def test_epf_lua_matches_source_and_exports_callbacks(self) -> None:
        with zipfile.ZipFile(EPF_PATH) as archive:
            packaged = archive.read(LUA_MEMBER)
        self.assertEqual(packaged, LUA_PATH.read_bytes())
        lua = load_client_lua(packaged.decode("utf-8"))
        lua_type = lua.eval("type")
        for callback in PUBLIC_CALLBACKS:
            with self.subTest(callback=callback):
                self.assertEqual(lua_type(lua.globals()[callback]), "function")


if __name__ == "__main__":
    unittest.main()
