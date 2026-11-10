#!/usr/bin/env python3
"""Focused contracts for the isolated three-view model-position diagnostic."""

from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
PROBE_LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogModelPositionProbe.lua").read_text(
    encoding="utf-8"
)
PROBE_XML_PATH = ROOT / "content/client/Interface/FrameXML/NativeTransmogModelPositionProbe.xml"
PROBE_XML = PROBE_XML_PATH.read_text(encoding="utf-8")
WARDROBE_LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(
    encoding="utf-8"
)
WARDROBE_XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text(
    encoding="utf-8"
)


def section(start: str, end: str) -> str:
    begin = PROBE_LUA.index(start)
    return PROBE_LUA[begin:PROBE_LUA.index(end, begin)]


class ModelPositionDiagnosticContracts(unittest.TestCase):
    def test_three_large_xml_owned_models_exist_only_in_diagnostic(self) -> None:
        root = ET.parse(PROBE_XML_PATH).getroot()
        models = [node for node in root.iter() if node.tag.endswith("DressUpModel")]
        self.assertEqual(len(models), 3)
        self.assertEqual(PROBE_XML.count('<Size x="220" y="300" />'), 3)
        self.assertEqual(WARDROBE_XML.count("<DressUpModel"), 3)  # main, portrait, Collections
        self.assertNotIn("ModelPositionProbe", WARDROBE_XML + WARDROBE_LUA)

    def test_views_differ_only_by_requested_z(self) -> None:
        prepare = section("local function probePrepareViews", "function NativeTransmog_ModelPositionProbe_Open")
        rows = re.findall(r'label="([^"]+)",x=([^,]+),y=PROBE_Y,z=([^,]+),model=', prepare)
        self.assertEqual(rows, [
            ("Negative Z", "0", "-2"),
            ("Default Z", "0", "0"),
            ("Positive Z", "0", "2"),
        ])
        self.assertEqual(PROBE_XML.count("(0, -0.13,"), 3)

    def test_every_view_uses_the_same_initialization_and_transform(self) -> None:
        initialise = section("local function probeInitialiseAll", "local function probeReapplyAll")
        ordered = [
            "view.model:ClearModel()",
            "view.model:SetPosition(view.x,view.y,view.z)",
            'view.model:SetUnit("player")',
            "view.model:Undress()",
            "view.model:TryOn(probeItemLink)",
            "probeApplyTransform(view)",
            "view.model:Show()",
        ]
        offsets = [initialise.index(token) for token in ordered]
        self.assertEqual(offsets, sorted(offsets))
        transform = section("local function probeApplyTransform", "local function probeInitialise")
        for token in (
            "model:SetCamera(PROBE_CAMERA)",
            "model:SetFacing(PROBE_FACING)",
            "model:SetModelScale(PROBE_SCALE)",
            "model:SetPosition(view.x,view.y,view.z)",
        ):
            self.assertIn(token, transform)
        self.assertNotIn("SetRotation", PROBE_LUA)

    def test_initialization_calls_are_measured_and_position_is_last_writer(self) -> None:
        initialise = section("local function probeInitialiseAll", "local function probeReapplyAll")
        for phase in ("after SetUnit", "after Undress", "after TryOn", "immediate after requested position"):
            self.assertIn(f'"{phase}"', initialise)
        self.assertLess(initialise.index("view.model:TryOn(probeItemLink)"), initialise.index("probeApplyTransform(view)"))

    def test_bounded_measurement_schedule_and_reapplication(self) -> None:
        self.assertIn("local PROBE_TIMES = { 0, .05, .25, .50, 1.00 }", PROBE_LUA)
        update = section("function NativeTransmog_ModelPositionProbe_OnUpdate", "function NativeTransmog_ModelPositionProbe_OnHide")
        self.assertIn("elapsed>=PROBE_TIMES[probeStep]", update)
        self.assertIn("probeReapplyAll(sampleTime,elapsed)", update)
        self.assertIn("probeStarted=nil; probeStep=nil", update)
        self.assertIn('SetScript("OnUpdate",nil)', update)
        self.assertNotIn("<OnUpdate>", PROBE_XML)
        reapply = section("local function probeReapplyAll", "local function probeFindItem")
        self.assertLess(reapply.index('"before reapply"'), reapply.index("view.model:Undress()"))
        self.assertLess(reapply.index("view.model:TryOn(probeItemLink)"), reapply.index("probeApplyTransform(view)"))
        self.assertIn('"after reapply"', reapply)

    def test_open_close_command_and_cleanup_are_isolated(self) -> None:
        self.assertIn('SLASH_NATIVETRANSMOGMODELTEST1="/nativetransmogmodeltest"', PROBE_LUA)
        self.assertIn('SLASH_NATIVETRANSMOGMODELTEST2="/ntmodelprobe"', PROBE_LUA)
        toggle = section("function NativeTransmog_ModelPositionProbe_Toggle", "SLASH_NATIVETRANSMOGMODELTEST1")
        self.assertIn("NativeTransmog_ModelPositionProbe_Close()", toggle)
        self.assertIn("NativeTransmog_ModelPositionProbe_Open(argument)", toggle)
        cleanup = section("function NativeTransmog_ModelPositionProbe_OnHide", "function NativeTransmog_ModelPositionProbe_Toggle")
        self.assertIn("probeStarted=nil; probeStep=nil", cleanup)
        self.assertIn("view.model:Hide(); view.model:ClearModel()", cleanup)
        self.assertNotIn("NativeTransmogFrame:", PROBE_LUA + PROBE_XML)
        self.assertNotIn("sendRequest", PROBE_LUA)

    def test_normal_wardrobe_does_not_invoke_diagnostic_and_head_is_unchanged(self) -> None:
        self.assertNotIn("ModelPositionProbe", WARDROBE_LUA + WARDROBE_XML)
        self.assertIn("local PORTRAIT_CAMERA_SECONDS, PORTRAIT_MODEL_SCALE = .25, 1.30", WARDROBE_LUA)
        self.assertIn("local PORTRAIT_MODEL_X, PORTRAIT_MODEL_Y, PORTRAIT_MODEL_Z = 0, -.13, 0", WARDROBE_LUA)
        framing = WARDROBE_LUA[WARDROBE_LUA.index("local CATALOG_PORTRAIT_FRAMING"):
                                WARDROBE_LUA.index("-- The retail reconstruction")]
        self.assertEqual(framing.count("={camera="), 1)
        self.assertIn("HEAD={camera=0", framing)

    def test_probe_lua_compiles_as_lua_51(self) -> None:
        lua = LuaRuntime()
        lua.globals().SlashCmdList = lua.table()
        lua.execute(PROBE_LUA)
        self.assertEqual(lua.eval("type")(lua.globals().NativeTransmog_ModelPositionProbe_Toggle), "function")

    def test_runtime_open_samples_and_close_clear_all_models(self) -> None:
        lua = LuaRuntime()
        lua.execute(r'''
            SlashCmdList = {}
            now = 10
            chat = {}
            DEFAULT_CHAT_FRAME = { AddMessage=function(self,message) table.insert(chat,message) end }
            function GetTime() return now end
            function GetItemInfo(query) return "Probe Item", "item:12345:0:0:0:0:0:0:0" end
            function GetInventoryItemLink() return "item:12345:0:0:0:0:0:0:0" end
            function makeModel(name)
              local model={name=name,x=0,y=0,z=0,scale=1,calls={}}
              local function called(self,value) table.insert(self.calls,value) end
              function model:Hide() called(self,"Hide") end
              function model:Show() called(self,"Show") end
              function model:ClearModel() called(self,"ClearModel") end
              function model:SetPosition(x,y,z) self.x=x; self.y=y; self.z=z; called(self,"SetPosition") end
              function model:GetPosition() return self.x,self.y,self.z end
              function model:SetUnit(unit) called(self,"SetUnit:"..unit) end
              function model:Undress() called(self,"Undress") end
              function model:TryOn(link) called(self,"TryOn:"..link) end
              function model:SetCamera(camera) called(self,"SetCamera:"..camera) end
              function model:SetFacing(facing) called(self,"SetFacing:"..facing) end
              function model:SetModelScale(scale) self.scale=scale; called(self,"SetModelScale:"..scale) end
              function model:GetModelScale() return self.scale end
              return model
            end
            NativeTransmogModelPositionProbeNegativeModel=makeModel("negative")
            NativeTransmogModelPositionProbeDefaultModel=makeModel("default")
            NativeTransmogModelPositionProbePositiveModel=makeModel("positive")
            NativeTransmogModelPositionProbe={shown=false}
            function NativeTransmogModelPositionProbe:Show() self.shown=true end
            function NativeTransmogModelPositionProbe:SetScript(script,handler) self[script]=handler end
            function NativeTransmogModelPositionProbe:Hide()
              self.shown=false
              NativeTransmog_ModelPositionProbe_OnHide(self)
            end
            function NativeTransmogModelPositionProbe:IsShown() return self.shown end
        ''')
        lua.execute(PROBE_LUA)
        lua.globals().NativeTransmog_ModelPositionProbe_Toggle("")
        self.assertTrue(lua.eval("NativeTransmogModelPositionProbe.shown"))
        self.assertEqual(lua.eval("NativeTransmogModelPositionProbeNegativeModel.z"), -2)
        self.assertEqual(lua.eval("NativeTransmogModelPositionProbeDefaultModel.z"), 0)
        self.assertEqual(lua.eval("NativeTransmogModelPositionProbePositiveModel.z"), 2)
        initial_sequences = [
            lua.eval(f'table.concat({name}.calls,",")')
            for name in (
                "NativeTransmogModelPositionProbeNegativeModel",
                "NativeTransmogModelPositionProbeDefaultModel",
                "NativeTransmogModelPositionProbePositiveModel",
            )
        ]
        self.assertEqual(len(set(initial_sequences)), 1)

        for elapsed in (.05, .25, .50, 1.00):
            lua.execute(f"now=10+{elapsed}")
            lua.globals().NativeTransmog_ModelPositionProbe_OnUpdate()
        chat_text = lua.eval(r'table.concat(chat,"\n")')
        for target in ("0.05", "0.25", "0.50", "1.00"):
            self.assertIn(f"target={target}", chat_text)
        self.assertIn("sampling complete", chat_text)

        lua.globals().NativeTransmog_ModelPositionProbe_Toggle("")
        self.assertFalse(lua.eval("NativeTransmogModelPositionProbe.shown"))
        for name in (
            "NativeTransmogModelPositionProbeNegativeModel",
            "NativeTransmogModelPositionProbeDefaultModel",
            "NativeTransmogModelPositionProbePositiveModel",
        ):
            self.assertTrue(lua.eval(f'{name}.calls[#{name}.calls]=="ClearModel"'))


if __name__ == "__main__":
    unittest.main()
