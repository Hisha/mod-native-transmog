#!/usr/bin/env python3
"""Static and package-level regression tests for the Phase 1 prototype."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
MANIFEST_PATH = CONTENT / "manifest.json"
EPF_PATH = CONTENT / "mod-native-transmog.epf"
LUA_PATH = CONTENT / "client/Interface/FrameXML/NativeTransmogFrame.lua"
XML_PATH = CONTENT / "client/Interface/FrameXML/NativeTransmogFrame.xml"
CATALOG_PATH = ROOT / "tests/catalog_expected.json"


class PhaseOneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.lua = LUA_PATH.read_text(encoding="utf-8")
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    def test_schema3_frame_xml_contract(self) -> None:
        self.assertEqual(self.manifest["schema"], 3)
        frame_xml = self.manifest["clientFrameXml"]
        self.assertEqual(
            frame_xml["stockTocSha256"],
            hashlib.sha256((CONTENT / frame_xml["stockTocSource"]).read_bytes()).hexdigest(),
        )
        self.assertEqual(frame_xml["loadEntries"], [{
            "target": "Interface/FrameXML/NativeTransmogFrame.xml",
            "after": "Interface/FrameXML/DressUpFrame.xml",
        }])

    def test_no_addon_loader_or_raw_toc_replacement(self) -> None:
        targets = [entry["target"].replace("\\", "/") for entry in self.manifest["content"]]
        self.assertFalse(any("Interface/AddOns/" in target for target in targets))
        self.assertNotIn("Interface/FrameXML/FrameXML.toc", targets)
        self.assertFalse(any(target.lower().endswith(".toc") for target in targets))

    def test_xml_is_well_formed_and_loads_lua_first(self) -> None:
        root = ET.parse(XML_PATH).getroot()
        names = [element.attrib.get("name") for element in root.iter()]
        self.assertIn("NativeTransmogFrame", names)
        children = list(root)
        self.assertTrue(children[0].tag.endswith("Script"))
        self.assertEqual(children[0].attrib["file"], "NativeTransmogFrame.lua")

    def test_prototype_behaviors_are_present(self) -> None:
        for token in (
            'model:SetUnit("player")',
            "getModel():TryOn(button.itemId)",
            "NativeTransmog_SelectSlot",
            "NativeTransmog_ResetPreview",
            "NativeTransmog_Rotate",
            'SLASH_NATIVETRANSMOG1 = "/wardrobe"',
        ):
            self.assertIn(token, self.lua)

    def test_catalog_is_deterministic_and_matches_fixture(self) -> None:
        all_ids = []
        for definition in self.catalog.values():
            all_ids.extend(definition["items"])
        self.assertEqual(len(all_ids), len(set(all_ids)))
        lua_ids = [int(value) for value in re.findall(r"\{ id = (\d+), name = ", self.lua)]
        self.assertCountEqual(lua_ids, all_ids)

    def test_configuration_defaults_and_registration(self) -> None:
        config = (ROOT / "conf/mod_native_transmog.conf.dist").read_text(encoding="utf-8")
        for line in (
            "NativeTransmog.Enable = 1",
            "NativeTransmog.AllowTwoHandAppearanceOnOneHand = 0",
            "NativeTransmog.AllowOneHandAppearanceOnTwoHand = 0",
        ):
            self.assertIn(line, config)
        loader = (ROOT / "src/mod_native_transmog_loader.cpp").read_text(encoding="utf-8")
        self.assertIn("Addmod_native_transmogScripts", loader)

    def test_epf_members_and_repeatability(self) -> None:
        expected = {"manifest.json"}
        expected.update(entry["source"] for entry in self.manifest["content"])
        expected.add(self.manifest["clientFrameXml"]["stockTocSource"])
        with zipfile.ZipFile(EPF_PATH) as archive:
            self.assertEqual(set(archive.namelist()), expected)
            self.assertEqual(json.loads(archive.read("manifest.json")), self.manifest)
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))

        with tempfile.TemporaryDirectory(prefix="native-transmog-test-") as directory:
            candidate = Path(directory) / "candidate.epf"
            script = (
                "import importlib.util, pathlib; "
                "p=pathlib.Path(sys.argv[1]); "
                "s=importlib.util.spec_from_file_location('builder', p); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "m.build(pathlib.Path(sys.argv[2]))"
            )
            subprocess.run(
                [sys.executable, "-c", "import sys; " + script,
                 str(CONTENT / "build_epf.py"), str(candidate)],
                check=True,
            )
            self.assertEqual(candidate.read_bytes(), EPF_PATH.read_bytes())


if __name__ == "__main__":
    unittest.main()
