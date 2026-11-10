#!/usr/bin/env python3
"""Regression contracts for removal of the temporary model-position probe."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
FRAME_XML = CONTENT / "client/Interface/FrameXML"
LUA = (FRAME_XML / "NativeTransmogFrame.lua").read_text(encoding="utf-8")
XML = (FRAME_XML / "NativeTransmogFrame.xml").read_text(encoding="utf-8")
MANIFEST = json.loads((CONTENT / "manifest.json").read_text(encoding="utf-8"))


class RemovedModelPositionDiagnosticContracts(unittest.TestCase):
    def test_probe_sources_and_commands_are_absent(self) -> None:
        self.assertFalse((FRAME_XML / "NativeTransmogModelPositionProbe.lua").exists())
        self.assertFalse((FRAME_XML / "NativeTransmogModelPositionProbe.xml").exists())
        self.assertNotIn("nativetransmogmodeltest", LUA + XML)
        self.assertNotIn("ntmodelprobe", LUA + XML)
        self.assertNotIn("ModelPositionProbe", LUA + XML)

    def test_epf_no_longer_packages_or_loads_probe(self) -> None:
        serialized = json.dumps(MANIFEST)
        self.assertNotIn("NativeTransmogModelPositionProbe", serialized)
        self.assertEqual(len(MANIFEST["clientFrameXml"]["loadEntries"]), 1)

    def test_wardrobe_keeps_only_main_head_portrait_and_collections_models(self) -> None:
        self.assertEqual(XML.count("<DressUpModel"), 3)
        self.assertEqual(XML.count('name="NativeTransmogCatalogPortraitModel"'), 1)
        self.assertNotIn('CreateFrame("DressUpModel"', LUA)


if __name__ == "__main__":
    unittest.main()
