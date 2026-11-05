# Phase 5A data and protocol design

## Scope and evidence boundary

Phase 5A presents a reviewed catalog of Blizzard class armor. It does not attempt to infer cosmetic ensembles.

`ItemSet.dbc` is the client data definition for a gameplay item set: localized name, up to 17 item IDs in the 3.3.5a file layout, eight set-bonus spells and thresholds, and optional skill requirements. AzerothCore's `ItemSetEntry` exposes the localized name, the first ten item IDs, the bonus arrays, and skill requirements. The core loads it into `sItemSetStore` and validates nonzero `item_template.ItemSet` values against that store.

`ItemSet.dbc` has no field that distinguishes tier armor, class PvP armor, crafted sets, dungeon sets, trinket/ring sets, and other gameplay groupings. Automatic admission based on `ItemSet`, a class mask, a name, or an ID interval therefore cannot implement the intended browser without false positives. The catalog uses an explicit reviewed ItemSet-ID allowlist. For an admitted identity, the loaded DBC and `item_template.ItemSet` remain authoritative for its name and membership. The database column retains server variants beyond the ten item IDs exposed by the runtime structure. A visually coordinated collection with `ItemSet = 0` is not discovered. No membership is derived from item names, display IDs, armor subclass, or web data.

This produces two deliberately different categories:

- A curated appearance set has a reviewed ItemSet identity in the allowlist and valid loaded DBC/template data. Phase 5A supports this category.
- A gameplay item set can have a valid ItemSet identity without being suitable for the appearance browser. It is excluded unless explicitly reviewed.
- A cosmetic ensemble may merely share art. It may have no ItemSet identity and may include offset pieces. Phase 5A does not support it. The `SetCatalog` boundary permits a future explicit, independently validated ensemble provider without changing the browser or progress protocol.

## Discovery and class filtering

The catalog is built once during world startup and configuration reload, after item templates and DBC stores are available. Every eligible armor or weapon appearance is resolved through `CollectionService::ResolveAppearance`. Nonvisual inventory types are omitted.

For each admitted set, the index records the intersection of nonempty explicit playable `AllowableClass` masks. This prevents broad test/template alternatives from widening a class-specific family. Sets with no explicit class evidence, or contradictory masks with an empty intersection, are excluded conservatively. A player sees a set only when that mask includes the player's class. Individual faction/race variants are filtered by `AllowableRace` when totals and details are produced. This means:

- sets explicitly restricted to another class are excluded;
- damage, healing, and tank sets remain separate when their ItemSet IDs are separate;
- distinct ItemSet IDs remain distinct even if their art is similar;
- armor proficiency alone is never treated as evidence of class ownership;
- generic or ambiguous sets are not guessed into a class catalog.

Representative verified fixtures from AzerothCore's WotLK `item_template` data are:

- Judgement Armor: ItemSet 217; Judgement Spaulders 16953 and Judgement Crown 16955; explicit paladin mask 2.
- Turalyon Tier 9 variants: ItemSet 875; Turalyon's Headpiece of Conquest 48564, Triumph 48577/48582, and base 48902; explicit paladin mask 2. These demonstrate multiple item variants under one authentic gameplay-set identity.

The IDs above were read from the installed AzerothCore base world SQL, not inferred from names or external sources. The live catalog still requires the set ID to resolve in the loaded DBC.

### Curated catalog and installed-data audit

A deterministic audit of AzerothCore WotLK base `item_template` at core revision `8a4e76eac8c4ccebf547113afe7b51d6c3e91641` found 390 class-restricted gameplay-set candidates. That result is evidence that automatic classification is too broad, not an inclusion list.

The initial reviewed catalog contains these 93 ItemSet identities:

- Classic Tier 1: 201, 202, 203, 204, 205, 206, 207, 208, 209.
- Classic Tier 2: 210, 211, 212, 213, 214, 215, 216, 217, 218.
- WotLK arena class/spec armor families: 765, 766, 767, 768, 769, 770, 771, 772, 773, 774, 775, 776, 777, 778, 779, 780. The authentic data groups season variants as alternatives under each identity.
- Death knight Tier 7: 792 and 793.
- WotLK Tier 9: 843 through 880, with every ID written individually in `CuratedSetIds`; this is a documented grouping, not a runtime numeric-range rule.
- WotLK Tier 10: 883 through 901, likewise represented by explicit IDs.

Every other valid gameplay ItemSet is excluded from the main browser because it has not been explicitly classified as one of those reviewed armor categories. In particular, 881 and 882 are shard/ring gameplay sets, not armor ensembles. Dungeon, crafted, resistance, weapon, trinket, and miscellaneous sets are not admitted merely because they have a class mask, bonus, suggestive name, or nearby numeric ID. Additional Blizzard visual ensembles can be added only by reviewing a concrete ItemSet ID and its actual template membership. The startup log is authoritative for a realm because a curated ID is still rejected when its DBC identity, visual template, or class evidence is unavailable.

All 93 curated IDs resolve in that audited base template data with nonempty class-mask intersections: 18 identities have eight visual armor slots and 75 have five. This audit checks the build input; the runtime still performs every DBC, appearance, class, and race check rather than trusting the audit count.

## Piece grouping and collection progress

The existing durable appearance identity is `(DisplayInfoID, item class, item subclass, inventory type)`. Completion requirements are grouped by visual equipment slot within one authentic ItemSet identity. Every item entry in that slot remains an alternative carrying its own complete composite identity; the group is collected when any race-eligible alternative identity is collected. This is necessary for authentic WotLK data such as ItemSet 875, which contains 20 Tier 9 entries and several difficulty/display variants but is still a five-slot armor set. It prevents variants in one slot from inflating the denominator while never matching collection state by display ID alone.

After race filtering:

- total is the number of eligible visual equipment-slot groups;
- collected is the number for which `CollectionService::IsCollected(player, identity)` succeeds for at least one race-eligible alternative;
- missing is `total - collected`;
- complete means `total > 0 && collected == total`.

This preserves the configured account-wide or character-specific collection owner because all checks go through `CollectionService`; there is no set-unlock table and exact item ownership is irrelevant.

## Acquisition source index

Source metadata is generated deterministically at world startup, not during browsing:

- direct vendor rows from `npc_vendor`, joined to `creature_template`, become `Sold by: <vendor>`;
- direct creature loot becomes `Drops from: <creature>`;
- `reference_loot_template` is expanded with a cycle guard and a maximum depth of eight, then connected to creatures through `creature_loot_template`; this reports the actual dropping creature rather than an intermediate reference row;
- fixed and choice rewards in loaded quest templates become `Reward from: <quest>`.

Up to three distinct sources are retained per visual group and transport text is sanitized and bounded. A vendor row remains a vendor source when `ExtendedCost` is nonzero and is labeled as a token/currency exchange; the catalog does not claim that a token itself drops the finished item. Unresolved items say `Source unknown`.

Not presently indexed: gameobject/container loot, crafting, mail/event/script rewards, PvP ranking, the contents/cost names of extended-cost exchanges, and location/instance names. These omissions prefer an honest unknown source to speculation. Refresh is deterministic: restart worldserver or reload module configuration, which rebuilds the immutable index.

## Transport

`NTRANSMOG` protocol version 3 adds read-only operations while retaining all version-2 mutation semantics:

- `SETS <requestId> <filter> <cursor>`: filter 0 all, 1 incomplete, 2 complete. Cursor is bounded and pages contain at most eight summaries. Replies echo the request ID in `SETPAGE`, zero or more `SET`, and `SETEND`.
- `SETDETAIL <requestId> <setId>`: the supplied ID is accepted only if it is in the startup catalog and appropriate to the authenticated player's class. Replies echo the request ID in one bounded header, eligible `SETPIECE` rows carrying entry, slot, progress, source, and authoritative server item name, and `SETDETAILEND`.

Inputs use strict unsigned parsing, exact field counts, the existing request-length bound, cooldown, stable name/ID ordering, and no custom opcode. Set browsing does not require an NPC session. `CAT`, `APPLY`, `HIDE`, and `REMOVE` retain their existing server-issued NPC token and mutation snapshot checks. No client-supplied appearance or item identity is trusted.

Set response ownership is a client-side state machine keyed by request ID, operation kind, expected set ID, and response phase. A page accepts at most eight unique rows; a detail accepts at most 32 ordinal pieces. Repeated rows are idempotent, a repeated header cannot erase accumulated pieces, and incomplete terminators do not publish partial data. Selection changes, mode changes, timeouts, and frame closure invalidate the active request, so late replies cannot mutate hidden or newer UI state.

## UI and preview

The native wardrobe now has `Appearances` and `Sets` modes. Appearances retains the Phase 4 paper doll, per-slot catalog, pagination, native tooltips, and authorized controls. Sets provides All/Incomplete/Complete filters, paged set rows with progress, visible collected/missing piece rows, native item tooltips, and bounded source text.

Selecting a set rebuilds the existing `DressUpModel` locally with `SetUnit("player")`, `Undress()`, and ordered `TryOn(item)` calls. Rotation remains unchanged. Reset Preview calls `SetUnit("player")`, restoring the unit's current server-confirmed visible equipment/overrides. No item is equipped, overridden, purchased, or applied.

WotLK's DressUpModel is last-write-wins for a slot and has no modern transmog-set API. It cannot reliably display non-dressable relics, hidden modern geometry rules, or every weapon/off-hand combination; Phase 5A sends one deterministic representative per grouped visual and uses only supported 3.3.5a calls.

### Item-name resolution

The generic `Item <entry>` label was not caused by a bad set member or a missing server template. The client UI called `GetItemInfo(entry)`, which returns `nil` until that build's local item cache has resolved the entry, while the protocol carried only the numeric entry and source text. The server already resolves the same representative through `ObjectMgr` and therefore now appends its authoritative `ItemTemplate::Name1` to `SETPIECE`. The row uses a cached localized client name first, the authoritative server name second, and `Item <entry>` only when neither side can resolve a name. The item ID and native hyperlink are never substituted.

## Performance and failure behavior

DBC/template discovery and source expansion occur once at startup/reload. Player requests scan only the in-memory class catalog and make cached collection-identity lookups. Network pages are fixed at eight sets; detail size is capped at 32 visual identities (with a startup warning if corrupt/custom data exceeds it). Missing DBC rows, invalid display data, unavailable source rows, and race-ineligible pieces are skipped safely.

No database schema change is required.
