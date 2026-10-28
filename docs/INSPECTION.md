# Source inspection record

Inspection date: 2026-10-28. Revisions are the local checked-out commits used to design Phase 1.

| Project | Revision | Relevant locations and conclusion |
| --- | --- | --- |
| `mod-native-transmog` | `73745fedeabc95b623146244fd1db526f58a24e7` (pre-implementation) | Existing repository contained only MIT `LICENSE` and a one-line `README.md`. |
| `Hisha/mod-content-manager` | `e9927be2c2f0e262b8513a68f23805fc5f136191` | `src/ContentPackage.cpp` parses/validates Schema 3 and FrameXML declarations; `src/ContentFrameXml.cpp` validates load entries and composes the stock TOC; `src/ContentBuildService.cpp` owns cumulative collision preflight, staging, MPQ build, generated hashes, and build records; `src/ContentBuildPublisher.cpp`, `ContentBuildRegistry.cpp`, and `ContentPackageLifecycle.cpp` cover publish/activation/rollback state. `tests/schema3_tests.cpp`, `frame_xml_tests.cpp`, and `frameforge_wow_ui_tests.cpp` cover compatibility, ordering, collision behavior, and portable exports. |
| FrameForge | `1ccb522a23c31dba8626ca0b51220c86d63d9186` | `src/FrameForge.Core/Export/Wow335Export.cs` emits build-12340 manifest v2, `FrameForgeLayout.xml`, and asset manifests. `docs/WOW_335_EXPORT.md` documents the portable output. Phase 1's dynamic Lua is independently authored and carried as ordinary Schema 3 resources, so the exporter needs no extension. |
| AzerothCore Playerbot | `8a4e76eac8c4ccebf547113afe7b51d6c3e91641` (`Playerbot`) | `modules/CMakeLists.txt`, `ModulesLoader.cpp.in.cmake`, and `how_to_make_a_module.md` establish native module discovery/registration conventions. `data/sql/base/db_world/item_template.sql` was used to verify the test catalog IDs and inventory types. |
| `mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` | Installed alongside the core; no Phase 1 integration point or modification is needed. |
| Portalkeeper | `09703e8c8ad4680bafee865312c0615d3bb51c89` | `Models/RealmInfo.cs`, `Services/RealmConfigurationService.cs`, `RealmExecutableService.cs`, and `docs/isolated-runtime-checkpoint6.md` implement the established `protected-framexml` requirement, generation-2 selection, and isolated runtime preparation. No change is needed or made. The checkout had an unrelated untracked `scripts/__pycache__/`, which was not touched. |

The installed `azerothcore/mod-transmog` checkout was not present under the inspected AzerothCore `modules/` directory or the available local repositories. Consequently, no behavior or source was borrowed from it. Phase 1 has no SQL, hooks, opcodes, NPC service, or persistent state and therefore coexists by isolation; PTR validation must still confirm the separately installed realm module remains operational.

## Pipeline findings

1. Schema 3 is parsed by `ContentPackage`; older schemas and Schema 3 packages without optional FrameXML fields remain supported.
2. Raw XML/Lua resources are declared in `content[]` and staged at canonical `Interface/FrameXML/...` targets.
3. `clientFrameXml.loadEntries[]` adds a managed XML file after a unique verified stock entry. Phase 1 anchors after `DressUpFrame.xml` so the stock model support is loaded first.
4. The verified 2,820-byte build-12340 `FrameXML.toc` is an EPF input, not a raw MPQ target. The composer owns the cumulative output.
5. Target ownership and path folding make collisions case-insensitive; raw ownership of `FrameXML.toc`, duplicate targets, missing anchors, ambiguous anchors, and cycles fail validation/build.
6. Staged content flows into deterministic cumulative MPQ assembly, whole-MPQ/parity hashes, build activation, publication, and rollback through existing content-manager services.
7. A non-empty FrameXML declaration automatically records `protected-framexml`; Portalkeeper consumes the matching realm requirement and distributes/prepares the isolated client as already implemented.

No `mod-content-manager`, FrameForge, Portalkeeper, or AzerothCore core change is necessary for Phase 1.
