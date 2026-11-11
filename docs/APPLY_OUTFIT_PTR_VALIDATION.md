# Apply Outfit PTR deployment and validation

Automated tests and a successful worldserver link do not establish PTR gameplay success. Complete the checks below on
the build-12340 PTR before recording gameplay acceptance.

## Deployment requirements

1. Deploy the rebuilt `worldserver` containing this module's server changes.
2. Deploy the newly generated `content/mod-native-transmog.epf` through the existing FrameForge → EPF →
   mod-content-manager → Portalkeeper protected-FrameXML pipeline. The server and EPF must be deployed together because
   the client now sends `CUSTOMAPPLYOUTFIT`.
3. Keep `AddonChannel = 1` in `worldserver.conf`, install `mod_native_transmog.conf`, and keep
   `NativeTransmog.Application.Enable = 1` and `NativeTransmog.CustomSets.Enable = 1`.
4. Ensure the existing character migrations through
   `data/sql/db-characters/updates/2026_11_08_00_native_transmog_custom_set.sql` are applied. This change adds no new
   database migration and requires no AzerothCore core patch, standalone addon, Content Manager code change, or
   Portalkeeper code change.
5. Restart worldserver and restart the PTR client so neither side retains an older protocol implementation.

## TempJudge acceptance

- [ ] Interact with an authorized Transmogrifier and open Transmogrify.
- [ ] Select `TempJudge`; verify the Tier 2 Judgement armor, Scarlet Crusade Tabard, Tankard O' Terror main hand, and
  Aegis of the Scarlet Commander off hand appear in the preview.
- [ ] Verify Shirt and Back preview as hidden, Ranged remains unchanged, and no red warning is shown merely because an
  explicitly hidden Shirt or Back slot is empty.
- [ ] Verify **Apply Outfit** is enabled only after the valid preview finishes loading.
- [ ] Click **Apply Outfit** once and verify server-confirmed `Saved outfit applied.` feedback.
- [ ] Close Transmogrify and verify those appearances are visible, Shirt and Back are hidden, and Ranged is unchanged.
- [ ] Record equipped item IDs and stats before and after; verify they are identical.
- [ ] Reopen Transmogrify and verify `TempJudge` still exists and has not changed.

## Failure and replay checks

- [ ] Make one saved appearance unavailable or equip an incompatible target and verify application reports the failing
  slot and writes no other slot.
- [ ] Move out of NPC authorization range and verify the request is rejected.
- [ ] Double-click or resend an identical request ID and verify it is not applied twice.
- [ ] Drop a response and verify the button leaves pending state after timeout and presents a failure instead of
  remaining disabled indefinitely.
