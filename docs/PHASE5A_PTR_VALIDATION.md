# Phase 5A stabilization PTR deployment and validation

This stabilization changes both the protected client FrameXML and the C++ world module. It has no SQL migration, configuration addition, protocol-version change, custom outfit, cost, or full-set application path.

## Exact deployment requirements

1. Record the current PTR core/module revisions, worldserver hash, active Content Manager build, EPF/MPQ hash, and Portalkeeper generation. Back up the prior module binary and active client build. Confirm the target is PTR and `mod-transmog` remains excluded from this isolated build.
2. Build and link `worldserver` from the reviewed module checkout against the PTR Playerbot/AzerothCore revision. Install the resulting server artifact through the normal PTR process. A module-only hot copy is insufficient because `NativeTransmogSetCatalog.cpp` and `NativeTransmogWardrobe.cpp` changed.
3. Keep protocol version 3 and the existing configuration. No database updater or manual SQL is required.
4. Build `content/mod-native-transmog.epf` twice with `python3 content/build_epf.py`, confirm identical SHA-256 values, and run `python3 content/build_epf.py --check`.
5. Put that EPF in the existing PTR Content Manager discovery location. Run `.content validate mod-native-transmog`, `.content build`, record the new STAGED build and hash, then `.content activate <new-build-number>`. Confirm `.content build list` reports that exact build ACTIVE/APPLIED with protected FrameXML parity.
6. Restart the PTR worldserver and publish the activated isolated client generation through the existing Portalkeeper flow. Do not install loose FrameXML, a standalone addon, or modify the cumulative TOC manually.
7. Launch the prepared build-12340 client with Lua errors enabled. A client restart is required so protected FrameXML is reloaded.

## Required PTR checks

- Open and close the NPC wardrobe repeatedly; switch between Appearances and Sets and confirm existing application, authorization, tooltips, overrides, and pagination are unchanged.
- Page forward/back through All, Incomplete, and Complete. Confirm expansion/family and PvE/PvP labels and stable eight-row pagination. On a non-first page, select several sets and confirm Previous/Next, the page, and the filter remain unchanged while details load. Filter changes must return to their first page. Repeatedly select sets with different piece counts, including eight-piece Judgement Armor and five-piece Turalyon's Garb, and rapidly select another set before the first detail finishes.
- Close the wardrobe immediately after page and detail requests, reopen it, and confirm late replies neither raise Lua errors nor replace current rows.
- Confirm Judgement remains 8/8 for the known collected character and previews all eight pieces. Confirm Turalyon remains 5/5 and alternate templates sharing its appearances do not inflate the total. Previewing either set must not unlock or apply anything.
- Hover every Judgement row plus representative Classic/TBC/Wrath items with direct loot, vendor/token exchange, currency exchange, quest, crafting, multiple, and unresolved sources. For Justicar Chestpiece confirm Magtheridon/Magtheridon's Lair appears before Chestguard of the Fallen Champion and the Shattrath exchange NPC; it must not say Magtheridon drops the finished chest. For Redemption Handguards confirm Original Naxxramas, Tier 3 quest, required materials, and current availability are separate lines. Confirm the native tooltip still shows quality, stats, requirements, and set bonuses; Source appears once; and the tooltip does not cover the Sets panel.
- Check a deliberately long item name at supported UI scales. Confirm the row ellipsis, equipment slot, collected/missing mark, icon, and 40-pixel bounds do not overlap; the tooltip must show the full native name.
- Confirm the documented catalog appears for every class/faction: Classic Tiers 1–3; TBC Tiers 4–6, level-70 honor, and arena families; Wrath Tiers 7–10 and arena families. Verify specialization/faction variants, including Turalyon/Liadrin visibility, and confirm unrelated gameplay sets such as 881/882 are absent.
- Inspect the startup log and record the loaded identity/visual-variant/source counts. The audited base-data expectation is 263 ItemSet identities and 540 browser variants; a differing realm count must be explained by its loaded DBC/templates before approval.
- Preserve client Lua logs, worldserver startup catalog count/source summary, screenshots, active build/hash, and the exact character/class used.

Rollback requires reactivating the recorded prior Content Manager build, restoring the prior compatible worldserver/module artifact, and restarting PTR. No database rollback is needed.
