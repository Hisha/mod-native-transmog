# Phase 5A verified set catalog and UI design

## Scope and authority

Phase 5A is a read-only browser for Blizzard class armor represented by installed WotLK 3.3.5a
`ItemSet.dbc` and `item_template` data. It does not infer sets from names or numeric ranges. The explicit source of
truth is `src/NativeTransmogVerifiedCatalog.inc`; runtime membership, item names, displays, race/faction eligibility,
and native item tooltips still come from the loaded server/client data.

The catalog intentionally excludes crafting, profession, resistance, dungeon, weapon, trinket, holiday, and other
miscellaneous gameplay sets. ItemSet 881/882, for example, are shard/ring gameplay sets rather than armor ensembles.
Classic PvP ranking sets are also outside this pass; Classic coverage is Tiers 1, 2, 2.5, and 3. TBC coverage
includes Tiers 4–6, class-specific level-70 honor sets, and arena families. Wrath coverage includes Tiers 7–10 and
arena families. These are documented omissions, not candidates selected or rejected by name matching.

The pre-polish catalog contained 93 ItemSet identities. The completed catalog contains 263 verified identities:

| Expansion | Family | Category | Identities |
| --- | --- | --- | ---: |
| Classic | Tier 1 | PvE | 9 |
| Classic | Tier 2 | PvE | 9 |
| Classic | Tier 2.5 | PvE | 9 |
| Classic | Tier 3 | PvE/legacy | 9 |
| The Burning Crusade | Tier 4 | PvE | 17 |
| The Burning Crusade | Tier 5 | PvE | 17 |
| The Burning Crusade | Tier 6 | PvE | 17 |
| The Burning Crusade | Level 70 Honor | PvP | 47 |
| The Burning Crusade | Arena Seasons 1–4 plus DK Season 4 | PvP | 18 |
| Wrath of the Lich King | Tier 7 | PvE | 19 |
| Wrath of the Lich King | Tier 8 | PvE | 19 |
| Wrath of the Lich King | Tier 9 | PvE | 38 |
| Wrath of the Lich King | Tier 10 | PvE | 19 |
| Wrath of the Lich King | Arena Seasons 5–8 | PvP | 16 |

By verified class mask, the 263 identities cover Warrior 25, Paladin 41, Hunter 17, Rogue 17, Priest 30,
Death Knight 12, Shaman 43, Mage 17, Warlock 18, and Druid 43. Tier counts exceed class counts where a tier has
legitimate specialization or faction identities. TBC and Wrath PvP identities likewise retain class/spec variants.

The installed Playerbot base-data audit at revision `8a4e76eac8c4ccebf547113afe7b51d6c3e91641` resolves all 263
identities with the expected five- or eight-slot membership. `tests/verify_set_catalog.py` repeats that audit against
an `item_template.sql` input.

The retained cardinality fixtures are ItemSet 217 (Judgement Armor: items 16951–16958, including 16953 and 16955,
eight slots) and ItemSet 875 (Turalyon Tier 9: twenty templates including 48564, 48577, 48582, and 48902, five slots
per distinct visual variant). These fixtures guard both eight-piece progress and alternative-template deduplication.

## Visual identities and progress

One ItemSet identity can contain several item-level or season variants. The runtime groups alternatives only when
their full collection identity matches: display ID, item class, subclass, and inventory type. It then builds a
separate browser entry for every distinct installed ensemble signature, aligned by item level and deterministic item
ID order. Duplicate templates with the same composite appearance stay alternatives; distinct displays stay distinct.
Repeated signatures are suppressed.

Against the audited base data this produces 540 browser entries from 263 ItemSet identities: Classic PvE 36, TBC
PvE 51, TBC PvP 117, Wrath PvE 238, and Wrath PvP 98. The runtime startup count is authoritative if a realm's loaded
DBC/templates differ. Synthetic variant IDs are server-owned protocol identifiers; the original ItemSet ID remains
the first variant and membership never depends on collection ownership.

Progress counts one selected visual per equipment slot. Tier 1, Tier 2, Tier 3, and Tier 6 therefore count eight;
Tier 2.5, Tiers 4/5/7/8/9/10, and the PvP families count five. Collection checks use the unchanged account/character
collection service. Browsing and `DressUpModel:TryOn` never unlock, equip, apply, or purchase an item.

Faction flags (`ITEM_FLAG2_FACTION_HORDE`/`ALLIANCE`), allowable race, and explicit reviewed class masks are checked
before totals and representatives are exposed. This keeps Turalyon/Liadrin and comparable faction variants distinct
while hiding an ineligible faction's pieces. Tier 3 uses reviewed class masks because the legacy templates themselves
carry broad masks.

## Acquisition metadata

The immutable startup index is bounded to relevant catalog items, their extended-cost tokens, and quest materials,
with at most four unique source lines per item/piece. It uses:

- `npc_vendor` plus the loaded `ItemExtendedCost.dbc` store for token quantities, Honor, and Arena Point costs;
- direct creature loot and cycle-safe reference-loot expansion (maximum depth eight);
- creature spawn maps plus loaded `Map.dbc` names for raid/dungeon location context when present;
- guaranteed and choice quest rewards, spawned creature/gameobject quest starters, item quest starters, and required
  materials from loaded world data;
- loaded create-item spell effects for crafting sources.

For a token exchange, the resolved boss/raid line is emitted first, followed by the token and exchange NPC/location.
The index never converts that into a finished-item boss drop. A boss-only line for finished equipment is emitted only
when that equipment is itself present in direct/reference creature loot. Multiple authoritative paths are
deduplicated and retained. Gameobject/container loot, mail/event/script rewards, profession recipe availability,
PvP bracket/rating requirements, and scripted quest starters are not fully indexed. Ordinary unresolved pieces say
`Source not resolved in installed world data`; Tier 3 unresolved pieces say
`Legacy source unavailable in installed WotLK world data`. Loaded Tier 3 reward quests are labeled as Original
Naxxramas armor quests, list required materials, and report installed availability separately. A quest template alone
never proves availability; only a proven starter plus resolved material sources is labeled installed, while incomplete
or uncertain paths remain unverified.

Representative installed-data checks cover Judgement Crown 16955 in reference loot; Justicar Chestpiece 29062 with
extended cost 1200, whose loaded DBC cost is Chestguard of the Fallen Champion 29754 and whose reference loot traces
to Magtheridon 17257; Turalyon's Headpiece 48564 with extended cost 2686; Avenger's Crown 21387 as quest 8628's reward;
and Redemption Handguards 22426 as quest 9048's reward with four historical required materials and no proven current
chain. These fixtures exercise Classic boss/reference loot, TBC and Wrath exchanges, a normal quest reward, and legacy
availability; they do not imply that every catalog source has been manually checked.

## Sets UI and tooltips

The 900×540 wardrobe and character preview are unchanged. The left set list keeps All/Incomplete/Complete filters,
eight-row pagination, progress, a persistent selected-row highlight, and expansion/category/family metadata. The
right list uses fixed 40-pixel rows containing only icon, bounded item name, collected/missing mark, and equipment
slot. Names longer than 24 client characters receive an ellipsis; the full native item name remains in the tooltip.
Eight-piece sets fit inside the existing 336-pixel piece viewport.

Acquisition text is no longer rendered permanently in rows. Hover first builds the native item hyperlink tooltip,
preserving quality color, stats, requirements, set bonuses, and stock behavior, then appends one separated Source
section. Rebuilding the hyperlink on every hover prevents duplicate appended lines. The tooltip is anchored to the
left of the Sets panel so it does not cover the rows.

## Transport and failure behavior

Protocol version 3 is unchanged. `SETS` remains an eight-entry paged read-only request; `SETDETAIL` remains bounded
to 32 pieces. `SET` replies add expansion/family/category tail fields, which is compatible with the version-3 client
parser and does not change mutation semantics. Page and detail requests have independent request ownership and
timeout state. Selecting a set changes only detail state, so it cannot clear the current page, next cursor, history,
filter, or navigation buttons. Filter and page changes intentionally clear selection/detail state. Repeated rows
replace their ordinal, and stale replies after rapid selection, pagination, filtering, closure, or reopening are
ignored.

`CAT`, `APPLY`, `HIDE`, `REMOVE`, NPC authorization, persistence, and CharacterFrame tooltip synchronization are
unchanged. Set browsing does not require an NPC session. No schema or configuration change is required.

## Known limitations

WotLK `DressUpModel` is last-write-wins per slot and has no modern transmog-set API. Client cache misses can briefly
delay native icons/tooltips, although server-provided names keep rows meaningful. Installed custom/partial templates
can yield different startup counts and are logged rather than invented. Actual protected-FrameXML geometry, tooltip
placement at supported UI scales, scripted/event acquisition paths, profession recipe reachability, and every
race/gender model combination still require the PTR checks in `PHASE5A_PTR_VALIDATION.md`.
