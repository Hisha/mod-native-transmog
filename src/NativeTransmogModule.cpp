#include "NativeTransmogCollection.h"
#include "NativeTransmogQuestCollection.h"
#include "NativeTransmogService.h"

#include "AllCreatureScript.h"
#include "Chat.h"
#include "CommandScript.h"
#include "Config.h"
#include "Creature.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Log.h"
#include "Player.h"
#include "QuestDef.h"
#include "RBAC.h"
#include "ScriptMgr.h"

#include <cstdint>

using namespace Acore::ChatCommands;

namespace
{
native_transmog::ServiceConfig serviceConfig;
native_transmog::CollectionConfig collectionConfig;
bool allowTwoHandAppearanceOnOneHand = false;
bool allowOneHandAppearanceOnTwoHand = false;

char const* ScopeName(native_transmog::RegistrationScope scope)
{
    return scope == native_transmog::RegistrationScope::CreatureEntry ? "entry" : "spawn";
}

char const* ResolutionName(native_transmog::ServiceResolution resolution)
{
    switch (resolution)
    {
        case native_transmog::ServiceResolution::Dedicated: return "dedicated";
        case native_transmog::ServiceResolution::CreatureEntry: return "creature-entry";
        case native_transmog::ServiceResolution::Spawn: return "spawn";
        default: return "none";
    }
}

Creature* SelectedCreature(ChatHandler* handler)
{
    Creature* creature = handler ? handler->getSelectedCreature() : nullptr;
    if (!creature && handler)
        handler->SendErrorMessage("Select a creature first.");
    return creature;
}

Player* SelectedOrSelfPlayer(ChatHandler* handler)
{
    if (!handler)
        return nullptr;
    if (Player* selected = handler->getSelectedPlayer())
        return selected;
    return handler->GetPlayer();
}

bool AddSelected(ChatHandler* handler, native_transmog::RegistrationScope scope)
{
    Creature* creature = SelectedCreature(handler);
    if (!creature)
        return false;

    std::uint32_t id = creature->GetEntry();
    if (scope == native_transmog::RegistrationScope::Spawn)
    {
        id = static_cast<std::uint32_t>(creature->GetSpawnId());
        if (!id)
        {
            handler->SendErrorMessage("The selected creature has no persistent spawn ID; use entry registration for dynamic creatures.");
            return false;
        }
    }

    bool reenabled = false;
    if (!native_transmog::Service::Instance().AddRegistration(scope, id, reenabled))
    {
        handler->SendErrorMessage("Transmogrifier {} {} is already enabled or this registration scope is disabled/unavailable.",
            ScopeName(scope), id);
        return false;
    }

    handler->PSendSysMessage("Native Transmog: {} {} registration {} (effective immediately).",
        reenabled ? "re-enabled" : "added", ScopeName(scope), id);
    return true;
}

bool RemoveSelected(ChatHandler* handler, native_transmog::RegistrationScope scope)
{
    Creature* creature = SelectedCreature(handler);
    if (!creature)
        return false;

    std::uint32_t id = scope == native_transmog::RegistrationScope::CreatureEntry
        ? creature->GetEntry() : static_cast<std::uint32_t>(creature->GetSpawnId());
    if (!id)
    {
        handler->SendErrorMessage("The selected creature has no persistent spawn ID.");
        return false;
    }
    if (!native_transmog::Service::Instance().RemoveRegistration(scope, id))
    {
        handler->SendErrorMessage("No enabled Transmogrifier {} registration exists for {}.", ScopeName(scope), id);
        return false;
    }

    handler->PSendSysMessage("Native Transmog: disabled {} registration {} (effective immediately).",
        ScopeName(scope), id);
    return true;
}

class NativeTransmogWorldScript final : public WorldScript
{
public:
    NativeTransmogWorldScript() : WorldScript("NativeTransmogWorldScript",
        { WORLDHOOK_ON_AFTER_CONFIG_LOAD, WORLDHOOK_ON_STARTUP }) { }

    void OnAfterConfigLoad(bool reload) override
    {
        serviceConfig.enabled = sConfigMgr->GetOption<bool>("NativeTransmog.Enable", true);
        serviceConfig.defaultNpcEnabled = sConfigMgr->GetOption<bool>("NativeTransmog.DefaultNPC.Enable", true);
        serviceConfig.customNpcEnabled = sConfigMgr->GetOption<bool>("NativeTransmog.CustomNPC.Enable", true);
        serviceConfig.allowSpawnRegistration =
            sConfigMgr->GetOption<bool>("NativeTransmog.CustomNPC.AllowSpawnRegistration", true);
        allowTwoHandAppearanceOnOneHand = sConfigMgr->GetOption<bool>(
            "NativeTransmog.AllowTwoHandAppearanceOnOneHand", false);
        allowOneHandAppearanceOnTwoHand = sConfigMgr->GetOption<bool>(
            "NativeTransmog.AllowOneHandAppearanceOnTwoHand", false);
        collectionConfig.enabled = serviceConfig.enabled &&
            sConfigMgr->GetOption<bool>("NativeTransmog.Collection.Enable", true);
        collectionConfig.accountWide =
            sConfigMgr->GetOption<bool>("NativeTransmog.Collection.AccountWide", true);
        collectionConfig.unlockOnAcquire =
            sConfigMgr->GetOption<bool>("NativeTransmog.Collection.UnlockOnAcquire", true);
        collectionConfig.unlockAllQuestRewards =
            sConfigMgr->GetOption<bool>("NativeTransmog.Collection.UnlockAllQuestRewards", true);
        collectionConfig.questBackfillEnabled =
            sConfigMgr->GetOption<bool>("NativeTransmog.Collection.QuestBackfill.Enable", true);

        native_transmog::Service::Instance().Configure(serviceConfig);
        native_transmog::CollectionService::Instance().Configure(collectionConfig);
        native_transmog::QuestBackfillService::Instance().Configure(
            collectionConfig.enabled && collectionConfig.questBackfillEnabled);
        if (reload && collectionConfig.enabled)
            native_transmog::CollectionService::Instance().Initialize();
        if (reload)
            LOG_INFO("server.loading",
                "Native Transmog Phase 3B configuration reloaded "
                "(collection: {}, scope: {}, acquire: {}, quest rewards: {}, backfill: {}).",
                collectionConfig.enabled, collectionConfig.accountWide ? "account" : "character",
                collectionConfig.unlockOnAcquire, collectionConfig.unlockAllQuestRewards,
                collectionConfig.questBackfillEnabled);
    }

    void OnStartup() override
    {
        if (!serviceConfig.enabled)
        {
            LOG_INFO("server.loading", "Native Transmog is disabled by configuration.");
            return;
        }

        native_transmog::Service::Instance().LoadRegistrations();
        if (collectionConfig.enabled)
            native_transmog::CollectionService::Instance().Initialize();
        LOG_INFO("server.loading",
            "Native Transmog Phase 2 NPC service initialized (dedicated: {}, custom: {}, spawn registrations: {}).",
            serviceConfig.defaultNpcEnabled, serviceConfig.customNpcEnabled, serviceConfig.allowSpawnRegistration);
        LOG_INFO("server.loading",
            "Native Transmog weapon compatibility options remain reserved for a later application phase "
            "(two-hand-on-one-hand: {}, one-hand-on-two-hand: {}).",
            allowTwoHandAppearanceOnOneHand, allowOneHandAppearanceOnTwoHand);
        LOG_INFO("server.loading",
            "Native Transmog Phase 3B collection initialized "
            "(enabled: {}, scope: {}, unlock on acquire: {}, quest rewards: {}, backfill: {}).",
            collectionConfig.enabled, collectionConfig.accountWide ? "account-wide" : "character-specific",
            collectionConfig.unlockOnAcquire, collectionConfig.unlockAllQuestRewards,
            collectionConfig.questBackfillEnabled);
    }
};

class NativeTransmogCreatureScript final : public AllCreatureScript
{
public:
    NativeTransmogCreatureScript() : AllCreatureScript("NativeTransmogCreatureScript") { }

    bool CanCreatureGossipHello(Player* player, Creature* creature) override
    {
        native_transmog::ServiceResolution resolution = native_transmog::Service::Instance().Resolve(creature);
        if (resolution == native_transmog::ServiceResolution::None)
            return false;

        native_transmog::Service::Instance().AuthorizeInteraction(player, creature);
        // The dedicated template has no other gossip to render. Registered
        // existing NPCs must continue through their normal gossip/script path.
        return resolution == native_transmog::ServiceResolution::Dedicated;
    }
};

class NativeTransmogPlayerScript final : public PlayerScript
{
public:
    NativeTransmogPlayerScript() : PlayerScript("NativeTransmogPlayerScript",
        { PLAYERHOOK_ON_UPDATE, PLAYERHOOK_ON_BEFORE_LOGOUT, PLAYERHOOK_ON_MAP_CHANGED,
          PLAYERHOOK_ON_SEND_LIST_INVENTORY, PLAYERHOOK_ON_BEFORE_RECEIVE_SPELL_LIST_FROM_TRAINER,
          PLAYERHOOK_ON_STORE_NEW_ITEM, PLAYERHOOK_ON_AFTER_MOVE_ITEM_TO_INVENTORY,
          PLAYERHOOK_ON_AFTER_STORE_OR_EQUIP_NEW_ITEM, PLAYERHOOK_ON_PLAYER_COMPLETE_QUEST }) { }

    void OnPlayerUpdate(Player* player, std::uint32_t diff) override
    {
        native_transmog::Service::Instance().UpdateSession(player, diff);
        native_transmog::QuestBackfillService::Instance().Update(player, diff);
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        native_transmog::Service::Instance().CloseSession(player, false);
        native_transmog::CollectionService::Instance().ReleasePlayer(player);
    }

    void OnPlayerMapChanged(Player* player) override
    {
        native_transmog::Service::Instance().CloseSession(player);
    }

    void OnPlayerSendListInventory(Player* player, ObjectGuid vendorGuid, std::uint32_t&) override
    {
        if (!player)
            return;
        Creature* creature = player->GetNPCIfCanInteractWith(vendorGuid, UNIT_NPC_FLAG_NONE);
        native_transmog::Service::Instance().AuthorizeInteraction(player, creature);
    }

    void OnPlayerBeforeReceiveSpellListFromTrainer(Player* player, Creature* trainer,
        WorldPackets::NPC::TrainerList&) override
    {
        native_transmog::Service::Instance().AuthorizeInteraction(player, trainer);
    }

    void OnPlayerStoreNewItem(Player* player, Item* item, std::uint32_t) override
    {
        native_transmog::CollectionService::Instance().Unlock(
            player, item, native_transmog::AcquisitionSource::NewItem);
    }

    void OnPlayerAfterMoveItemToInventory(Player* player, Item* item, bool) override
    {
        native_transmog::CollectionService::Instance().Unlock(
            player, item, native_transmog::AcquisitionSource::InventoryTransfer);
    }

    void OnPlayerAfterStoreOrEquipNewItem(Player* player, std::uint32_t, Item* item, std::uint8_t,
        std::uint8_t, std::uint8_t, ItemTemplate const*, Creature*, VendorItem const*, bool stored) override
    {
        // Stored vendor items already pass through StoreNewItem. Direct-to-slot
        // purchases use EquipNewItem and need this focused path.
        if (!stored)
            native_transmog::CollectionService::Instance().Unlock(
                player, item, native_transmog::AcquisitionSource::Vendor);
    }

    void OnPlayerCompleteQuest(Player* player, Quest const* quest) override
    {
        if (!collectionConfig.enabled || !collectionConfig.unlockAllQuestRewards)
            return;
        native_transmog::QuestCollectionStats stats = native_transmog::CollectQuestRewardAppearances(
            player, quest, native_transmog::AcquisitionSource::QuestCompletion, false);
        if (stats.newAppearances || stats.unresolvedRecords)
            LOG_DEBUG("module.native_transmog",
                "Quest {} completion collected {} of {} eligible appearances ({} already owned, {} unresolved).",
                quest ? quest->GetQuestId() : 0, stats.newAppearances, stats.eligibleAppearances,
                stats.alreadyCollected, stats.unresolvedRecords);
    }
};

class NativeTransmogCommandScript final : public CommandScript
{
public:
    NativeTransmogCommandScript() : CommandScript("NativeTransmogCommandScript") { }

    ChatCommandTable GetCommands() const override
    {
        static ChatCommandTable addCommands = {
            { "entry", HandleAddEntry, rbac::RBAC_PERM_COMMAND_NPC_ADD, Console::No },
            { "spawn", HandleAddSpawn, rbac::RBAC_PERM_COMMAND_NPC_ADD, Console::No }
        };
        static ChatCommandTable removeCommands = {
            { "entry", HandleRemoveEntry, rbac::RBAC_PERM_COMMAND_NPC_DELETE, Console::No },
            { "spawn", HandleRemoveSpawn, rbac::RBAC_PERM_COMMAND_NPC_DELETE, Console::No }
        };
        static ChatCommandTable npcCommands = {
            { "add", addCommands },
            { "remove", removeCommands },
            { "list", HandleList, rbac::RBAC_PERM_COMMAND_NPC_INFO, Console::Yes },
            { "info", HandleInfo, rbac::RBAC_PERM_COMMAND_NPC_INFO, Console::No }
        };
        static ChatCommandTable backfillCommands = {
            { "preview", HandleBackfillPreview, rbac::RBAC_PERM_COMMAND_NPC_INFO, Console::No },
            { "run", HandleBackfillRun, rbac::RBAC_PERM_COMMAND_NPC_ADD, Console::No },
            { "status", HandleBackfillStatus, rbac::RBAC_PERM_COMMAND_NPC_INFO, Console::No }
        };
        static ChatCommandTable collectionCommands = {
            { "info", HandleCollectionInfo, rbac::RBAC_PERM_COMMAND_NPC_INFO, Console::No },
            { "list", HandleCollectionList, rbac::RBAC_PERM_COMMAND_NPC_INFO, Console::No },
            { "count", HandleCollectionCount, rbac::RBAC_PERM_COMMAND_NPC_INFO, Console::No },
            { "backfill", backfillCommands }
        };
        static ChatCommandTable rootCommands = {
            { "npc", npcCommands },
            { "collection", collectionCommands }
        };
        static ChatCommandTable root = {
            { "nativetransmog", rootCommands }
        };
        return root;
    }

    static bool HandleAddEntry(ChatHandler* handler) { return AddSelected(handler, native_transmog::RegistrationScope::CreatureEntry); }
    static bool HandleAddSpawn(ChatHandler* handler) { return AddSelected(handler, native_transmog::RegistrationScope::Spawn); }
    static bool HandleRemoveEntry(ChatHandler* handler) { return RemoveSelected(handler, native_transmog::RegistrationScope::CreatureEntry); }
    static bool HandleRemoveSpawn(ChatHandler* handler) { return RemoveSelected(handler, native_transmog::RegistrationScope::Spawn); }

    static bool HandleList(ChatHandler* handler)
    {
        auto registrations = native_transmog::Service::Instance().ListRegistrations();
        handler->PSendSysMessage("Native Transmog registrations ({} rows):", registrations.size());
        for (native_transmog::Registration const& registration : registrations)
            handler->PSendSysMessage("  {} {}: {}", ScopeName(registration.scope), registration.id,
                registration.enabled ? "enabled" : "disabled");
        std::uint32_t dedicatedEntry = native_transmog::Service::Instance().DedicatedCreatureEntry();
        if (dedicatedEntry)
            handler->PSendSysMessage("  dedicated entry {}: Content Manager symbol dedicated-transmogrifier", dedicatedEntry);
        else
            handler->SendSysMessage("  dedicated entry: unavailable (managed resource is not ACTIVE/APPLIED and loaded)");
        return true;
    }

    static bool HandleInfo(ChatHandler* handler)
    {
        Creature* creature = SelectedCreature(handler);
        if (!creature)
            return false;
        handler->PSendSysMessage("Native Transmog NPC: entry {}, spawn {}, resolution {}.", creature->GetEntry(),
            static_cast<std::uint32_t>(creature->GetSpawnId()),
            ResolutionName(native_transmog::Service::Instance().Resolve(creature)));
        return true;
    }

    static bool HandleCollectionInfo(ChatHandler* handler)
    {
        Player* player = handler ? handler->GetPlayer() : nullptr;
        if (!player)
            return false;
        native_transmog::CollectionService& collection = native_transmog::CollectionService::Instance();
        native_transmog::CollectionOwner owner = collection.OwnerFor(player);
        handler->PSendSysMessage(
            "Native Transmog collection: enabled {}, database {}, scope {}, owner {}, count {}.",
            collection.IsEnabled(), collection.IsDatabaseAvailable(),
            owner.type == native_transmog::CollectionOwnerType::Account ? "account-wide" : "character-specific",
            owner.id, collection.Count(player));
        handler->SendSysMessage("Collection eligibility is independent of class/proficiency; "
            "appearance application is not implemented in Phase 3B.");
        return true;
    }

    static bool HandleCollectionCount(ChatHandler* handler)
    {
        Player* player = handler ? handler->GetPlayer() : nullptr;
        if (!player)
            return false;
        native_transmog::CollectionService& collection = native_transmog::CollectionService::Instance();
        handler->PSendSysMessage("Native Transmog current {} collection contains {} appearances.",
            collection.IsAccountWide() ? "account-wide" : "character-specific", collection.Count(player));
        return true;
    }

    static bool HandleCollectionList(ChatHandler* handler)
    {
        Player* player = handler ? handler->GetPlayer() : nullptr;
        if (!player)
            return false;
        constexpr std::uint32_t PageSize = 50;
        native_transmog::CollectionService& collection = native_transmog::CollectionService::Instance();
        std::vector<native_transmog::AppearanceRecord> records = collection.List(player, {}, 0, PageSize);
        std::uint32_t total = collection.Count(player);
        handler->PSendSysMessage("Native Transmog {} collection (showing {} of {}, maximum {}):",
            collection.IsAccountWide() ? "account-wide" : "character-specific", records.size(), total, PageSize);
        for (native_transmog::AppearanceRecord const& record : records)
        {
            ItemTemplate const* source = collection.ResolveSourceItem(record);
            handler->PSendSysMessage(
                "  display {} class {} subclass {} inventory {} | source item {}{} quest {} | "
                "acquired by {} via {} at {}",
                record.appearance.displayId, record.appearance.itemClass, record.appearance.itemSubclass,
                record.appearance.inventoryType, record.sourceItem,
                source ? "" : " (template missing)", record.sourceQuest, record.acquiringCharacter,
                native_transmog::CollectionService::SourceName(record.acquisitionSource), record.acquiredAt);
        }
        if (total > records.size())
            handler->SendSysMessage("  Output is bounded to the first 50 records in deterministic appearance order.");
        return true;
    }

    static bool StartBackfill(ChatHandler* handler, bool preview)
    {
        Player* target = SelectedOrSelfPlayer(handler);
        if (!target)
        {
            handler->SendErrorMessage("Select an online character or execute the command in game for yourself.");
            return false;
        }
        if (handler->HasLowerSecurity(target))
            return false;

        std::string error;
        if (!native_transmog::QuestBackfillService::Instance().Start(target, preview, error))
        {
            handler->SendErrorMessage("Native Transmog quest backfill: {}", error);
            return false;
        }

        handler->PSendSysMessage(
            "Native Transmog quest backfill {} started for {} (GUID {}). Processing is bounded to 25 reliably "
            "rewarded quests per batch; use '.nativetransmog collection backfill status' with the same target.",
            preview ? "preview" : "run", target->GetName(), target->GetGUID().GetCounter());
        return true;
    }

    static bool HandleBackfillPreview(ChatHandler* handler)
    {
        return StartBackfill(handler, true);
    }

    static bool HandleBackfillRun(ChatHandler* handler)
    {
        return StartBackfill(handler, false);
    }

    static bool HandleBackfillStatus(ChatHandler* handler)
    {
        Player* target = SelectedOrSelfPlayer(handler);
        if (!target)
        {
            handler->SendErrorMessage("Select the online character whose backfill status you want to inspect.");
            return false;
        }
        if (handler->HasLowerSecurity(target))
            return false;

        native_transmog::QuestBackfillStatus status =
            native_transmog::QuestBackfillService::Instance().Status(target);
        if (status.state == native_transmog::BackfillState::NotStarted)
        {
            handler->PSendSysMessage("Native Transmog quest backfill: no job recorded for {}.", target->GetName());
            return true;
        }

        handler->PSendSysMessage(
            "Native Transmog quest backfill {} {} for {} (GUID {}, {} owner {}): quests {}, "
            "eligible {}, already collected {}, {} {}, unresolved {}, ineligible reward items {}, cursor {}.",
            status.preview ? "preview" : "run",
            native_transmog::QuestBackfillService::StateName(status.state), status.targetName,
            status.targetCharacter,
            status.owner.type == native_transmog::CollectionOwnerType::Account ? "account" : "character",
            status.owner.id, status.stats.completedQuestsExamined, status.stats.eligibleAppearances,
            status.stats.alreadyCollected, status.preview ? "would unlock" : "newly unlocked",
            status.stats.newAppearances, status.stats.unresolvedRecords, status.stats.ineligibleItems,
            status.lastQuest);
        if (!status.error.empty())
            handler->PSendSysMessage("  Error: {}", status.error);
        return true;
    }
};
}

void AddNativeTransmogModuleScripts()
{
    new NativeTransmogWorldScript();
    new NativeTransmogCreatureScript();
    new NativeTransmogPlayerScript();
    new NativeTransmogCommandScript();
}
