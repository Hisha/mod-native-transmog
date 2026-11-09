# Native Warpweaver installation and PTR deployment

## Installed world data

Native Transmog owns creature entry **14999992**. The normal AzerothCore module world updater installs:

- `creature_template`: **Warpweaver**, subname **Transmogrifier**, level 80, neutral faction 35, gossip flag only, no AI or creature script;
- `creature_template_model`: display `19646`, scale `1.0`, probability `1.0`;
- nine `creature` rows at the audited Stormwind, Ironforge, Darnassus, Thunder Bluff, Orgrimmar, Exodar, Shattrath, Silvermoon, and Dalaran coordinates, each with a 300-second respawn;
- `native_transmog_installation` and `native_transmog_default_spawn` ownership/history rows.

The fresh-database installer is `data/sql/db-world/base/001_native_transmog_npc_service.sql`. Existing realms receive the identical transaction through `data/sql/db-world/updates/2026_11_09_00_native_warpweavers.sql`.

The verified PTR schema names the template column `creature.id` and defines `creature.guid` as an unsigned `AUTO_INCREMENT` primary key. Each insert omits `guid`, reads `LAST_INSERT_ID()`, and records it. This avoids fixed-range and `MAX(guid)` collisions. Every spawn explicitly sets `spawnMask = 1`, `phaseMask = 1`, `spawntimesecs = 300`, and `curhealth = 1`. A transaction and SQL exception handler make the marker, template, model, spawns, and history atomic.

The installer reserves the durable `default-warpweavers-v1` marker with `INSERT IGNORE` at the start of the transaction. A replay—or a concurrent second execution after the first commits—observes that reservation and returns without inspecting or rewriting live NPC rows. A failed installation rolls the marker back with the other changes. Consequently, an administrator may move, customize, or intentionally delete any installed spawn without the module recreating it. Worldserver startup performs validation/loading only and never writes world data.

If entry `14999992` already exists before the marker, the migration accepts it only when its complete Warpweaver identity and sole model row match. Any other occupant raises SQLSTATE `45000` and rolls back without changing creature data. Entry `190010`, its model, its spawns, and all legacy Transmog tables are intentionally untouched.

## Existing PTR preflight

1. Stop the PTR worldserver and back up the world and character databases.
2. Record these read-only baselines:

   ```sql
   SELECT * FROM creature_template WHERE entry IN (190010, 14999992);
   SELECT * FROM creature_template_model WHERE CreatureID IN (190010, 14999992);
   SELECT guid, id, map, position_x, position_y, position_z
   FROM creature WHERE id IN (190010, 14999992) ORDER BY id, guid;
   ```

3. Check `<PTR_CORE>/modules`, the configured module include/exclude list, CMake output, and the prior worldserver startup log for `mod-transmog`. The inspected local Playerbot checkout at revision `e7e2e288e` has no legacy module checkout, but that does not prove a previously deployed binary omitted it.
4. If legacy `mod-transmog` is present, remove/exclude its source from the PTR build and rebuild. Do not drop its tables or delete/modify entry `190010`; retained records are harmless when its code is not loaded and provide a rollback path.

## Deploy

1. Place this repository at `<PTR_CORE>/modules/mod-native-transmog` and configure/build AzerothCore normally.
2. Run the normal AzerothCore database updater. Do not paste the migration into a startup script and do not add an NPC-creation world hook.
3. Build `content/mod-native-transmog.epf`, activate it through Content Manager, and publish it through the established Portalkeeper path. Content Manager supplies client FrameXML only; it no longer allocates the server NPC.
4. Start worldserver and confirm the log does not report an invalid native Warpweaver template. Run `.nativetransmog npc list`; it should report dedicated entry `14999992`.

## Database verification

```sql
SELECT entry, name, subname, minlevel, maxlevel, faction, npcflag, AIName, ScriptName
FROM creature_template WHERE entry = 14999992;

SELECT CreatureID, Idx, CreatureDisplayID, DisplayScale, Probability
FROM creature_template_model WHERE CreatureID = 14999992;

SELECT c.guid, h.slot, h.city, c.id, c.map, c.spawnMask, c.phaseMask,
       c.position_x, c.position_y, c.position_z, c.orientation,
       c.spawntimesecs, c.curhealth
FROM native_transmog_default_spawn h
LEFT JOIN creature c ON c.guid = h.spawn_guid AND c.id = 14999992
ORDER BY h.slot;

SELECT COUNT(*) AS live_defaults FROM creature WHERE id = 14999992;
SELECT * FROM native_transmog_installation WHERE component = 'default-warpweavers-v1';
```

Expect one template, one model, nine joined live defaults on initial deployment, and one marker. Run the updater a second time and restart worldserver; the counts and GUIDs must remain unchanged. Then, on a disposable PTR copy, move one NPC and delete another, replay the SQL, and confirm the moved row remains moved and the deleted row remains absent.

## In-game verification

- Visit all nine coordinates and verify name, subname, appearance, scale, and respawn.
- Click each NPC repeatedly. Each click must produce one native Wardrobe open, no gossip page, and no legacy menu.
- Verify movement out of range, combat, map change, despawn, and logout close authorization as before.
- Verify Collections, acquisition, saved/custom sets, appearance application/removal, tooltips, and `/wardrobe` preview regressions.
- Confirm no legacy module startup banner, command surface, or entry-`190010` gossip behavior remains active.

If migration fails, retain the updater error and restore the database backup only if the transaction/DDL state requires it. If runtime validation fails, restore the prior binary/client build while leaving the backed-up legacy records intact.
