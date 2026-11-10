# Weapon compatibility and saved-outfit PTR validation

This checklist covers the grouped-melee and saved-preview routing correction. Automated results do not substitute for
the build-12340 PTR checks below.

## Deployment

1. Build and deploy `mod-native-transmog` in the isolated Playerbot PTR worldserver. Keep `mod-transmog` excluded.
2. Deploy the rebuilt `content/mod-native-transmog.epf` through the existing FrameForge → EPF → Content Manager →
   Portalkeeper pipeline.
3. Restart the PTR worldserver and client. No SQL migration, core patch, standalone addon, persistence migration, or
   protocol-version change is required. Do not modify or recreate `TempJudge`.
4. The version-5 `CUSTOMPREVIEWPIECE` response has one additive trailing eligibility-result field. Server and EPF must
   therefore be deployed together. A mixed deployment can time out or reject saved pieces.
5. Existing `NativeTransmog.AllowTwoHandAppearanceOnOneHand` and
   `NativeTransmog.AllowOneHandAppearanceOnTwoHand` values may remain in realm configuration; they are legacy no-op
   compatibility settings and cannot enable handedness crossing.

## Acceptance

- [ ] Equip a one-handed sword on a paladin and confirm collected one-handed swords, axes, and maces appear.
- [ ] Search for an eligible axe/mace known to sort beyond the first page and confirm it is found on the first result
  page; uncollected, unproficient, two-handed, ranged, and unrelated subclasses remain absent.
- [ ] Apply a collected one-handed axe or mace appearance and confirm it succeeds; forge or replay an uncollected or
  incompatible request and confirm the server rejects it.
- [ ] Equip a two-handed sword and confirm collected two-handed swords, axes, maces, and polearms appear and apply.
- [ ] Confirm one-handed/two-handed crossing remains rejected in both directions. Confirm shields remain shields and
  ranged behavior is unchanged.
- [ ] Re-equip the weapon and shield expected by `TempJudge`, select it in the NPC dropdown, and confirm the saved
  mace, shield, and all other eligible saved slots appear on the existing character preview.
- [ ] Confirm loading `TempJudge` does not change equipped items or write appearance overrides.
- [ ] If a saved slot is genuinely unavailable, confirm the status names that slot and reason while all other valid
  slots still preview.
- [ ] Confirm success, explicit server failure, and a deliberately dropped response all leave no indefinite pending
  request; the dropped response must end in the bounded timeout state.
- [ ] Close and reopen Transmogrify and confirm `TempJudge` remains listed and unchanged.
- [ ] Confirm Collections, item names/tooltips, slot search, Head portrait, preview rotation/reset, and normal final
  custom-set application still work.

Record the PTR core/module/client artifact hashes, the character and equipped entries, representative appearance
entries, screenshots, and server/client logs for each failure.
