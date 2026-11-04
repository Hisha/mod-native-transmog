#include "NativeTransmogApplication.h"
#include "NativeTransmogCollection.h"
#include "NativeTransmogQuestCollection.h"
#include "NativeTransmogService.h"
#include "NativeTransmogWardrobe.h"

#include "AllCreatureScript.h"
#include "Chat.h"
#include "CommandScript.h"
#include "Config.h"
#include "Creature.h"
#include "GlobalScript.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Log.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "QuestDef.h"
#include "RBAC.h"
#include "ScriptMgr.h"

#include <cstdint>
#include <shared_mutex>

using namespace Acore::ChatCommands;

namespace
{
native_transmog::ServiceConfig serviceConfig;
native_transmog::CollectionConfig collectionConfig;
native_transmog::ApplicationConfig applicationConfig;
native_transmog::WardrobeConfig wardrobeConfig;

void RefreshOnlineVisibleEquipment()
{
    std::shared_lock<std::shared_mutex> lock(*HashMapHolder<Player>::GetLock());
    for (auto const& [guid, player] : ObjectAccessor::GetPlayers())
    {
        (void)guid;
        if (!player)
            continue;
        for (std::uint8_t slot = EQUIPMENT_SLOT_START; slot < EQUIPMENT_SLOT_END; ++slot)
            if (Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
                player->SetVisibleItemSlot(slot, item);
    }
}

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
        applicationConfig.enabled = serviceConfig.enabled &&
            sConfigMgr->GetOption<bool>("NativeTransmog.Application.Enable", true);
        applicationConfig.allowTwoHandAppearanceOnOneHand = sConfigMgr->GetOption<bool>(
            "NativeTransmog.AllowTwoHandAppearanceOnOneHand", false);
        applicationConfig.allowOneHandAppearanceOnTwoHand = sConfigMgr->GetOption<bool>(
            "NativeTransmog.AllowOneHandAppearanceOnTwoHand", false);
        applicationConfig.hideWeapons = sConfigMgr->GetOption<bool>("NativeTransmog.HideWeapons", false);
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
        wardrobeConfig.enabled = applicationConfig.enabled && collectionConfig.enabled;
        wardrobeConfig.pageSize = sConfigMgr->GetOption<std::uint32_t>(
            "NativeTransmog.Wardrobe.PageSize", 24);
        wardrobeConfig.requestCooldownMs = sConfigMgr->GetOption<std::uint32_t>(
            "NativeTransmog.Wardrobe.RequestCooldownMs", 250);
        wardrobeConfig.snapshotLifetimeMs = sConfigMgr->GetOption<std::uint32_t>(
            "NativeTransmog.Wardrobe.SnapshotLifetimeMs", 30000);

        native_transmog::Service::Instance().Configure(serviceConfig);
        native_transmog::CollectionService::Instance().Configure(collectionConfig);
        native_transmog::ApplicationService::Instance().Configure(applicationConfig);
        native_transmog::WardrobeService::Instance().Configure(wardrobeConfig);
        native_transmog::QuestBackfillService::Instance().Configure(
            collectionConfig.enabled && collectionConfig.questBackfillEnabled);
        if (reload && collectionConfig.enabled)
            native_transmog::CollectionService::Instance().Initialize();
        if (reload && applicationConfig.enabled)
            native_transmog::ApplicationService::Instance().Initialize();
        if (reload && wardrobeConfig.enabled)
            native_transmog::WardrobeService::Instance().Initialize();
        if (reload)
            RefreshOnlineVisibleEquipment();
        if (reload)
            LOG_INFO("server.loading",
                "Native Transmog Phase 4A configuration reloaded "
                "(collection: {}, scope: {}, acquire: {}, quest rewards: {}, backfill: {}, application: {}, "
                "two-hand-on-one-hand: {}, one-hand-on-two-hand: {}, hide-weapons: {}).",
                collectionConfig.enabled, collectionConfig.accountWide ? "account" : "character",
                collectionConfig.unlockOnAcquire, collectionConfig.unlockAllQuestRewards,
                collectionConfig.questBackfillEnabled, applicationConfig.enabled,
                applicationConfig.allowTwoHandAppearanceOnOneHand,
                applicationConfig.allowOneHandAppearanceOnTwoHand, applicationConfig.hideWeapons);
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
        if (applicationConfig.enabled)
            native_transmog::ApplicationService::Instance().Initialize();
        if (wardrobeConfig.enabled)
            native_transmog::WardrobeService::Instance().Initialize();
        LOG_INFO("server.loading",
            "Native Transmog Phase 2 NPC service initialized (dedicated: {}, custom: {}, spawn registrations: {}).",
            serviceConfig.defaultNpcEnabled, serviceConfig.customNpcEnabled, serviceConfig.allowSpawnRegistration);
        LOG_INFO("server.loading",
            "Native Transmog Phase 3B collection initialized "
            "(enabled: {}, scope: {}, unlock on acquire: {}, quest rewards: {}, backfill: {}).",
            collectionConfig.enabled, collectionConfig.accountWide ? "account-wide" : "character-specific",
            collectionConfig.unlockOnAcquire, collectionConfig.unlockAllQuestRewards,
            collectionConfig.questBackfillEnabled);
        LOG_INFO("server.loading",
            "Native Transmog Phase 4A application initialized "
            "(enabled: {}, two-hand-on-one-hand: {}, one-hand-on-two-hand: {}, hide-weapons: {}).",
            applicationConfig.enabled, applicationConfig.allowTwoHandAppearanceOnOneHand,
            applicationConfig.allowOneHandAppearanceOnTwoHand, applicationConfig.hideWeapons);
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
    using PlayerScript::OnPlayerCanUseChat;

    NativeTransmogPlayerScript() : PlayerScript("NativeTransmogPlayerScript",
        { PLAYERHOOK_ON_UPDATE, PLAYERHOOK_ON_LOGIN, PLAYERHOOK_ON_BEFORE_LOGOUT, PLAYERHOOK_ON_MAP_CHANGED,
          PLAYERHOOK_ON_SEND_LIST_INVENTORY, PLAYERHOOK_ON_BEFORE_RECEIVE_SPELL_LIST_FROM_TRAINER,
          PLAYERHOOK_ON_STORE_NEW_ITEM, PLAYERHOOK_ON_AFTER_MOVE_ITEM_TO_INVENTORY,
          PLAYERHOOK_ON_AFTER_MOVE_ITEM_FROM_INVENTORY, PLAYERHOOK_ON_AFTER_SET_VISIBLE_ITEM_SLOT,
          PLAYERHOOK_ON_EQUIP, PLAYERHOOK_ON_PLAYER_COMPLETE_QUEST, PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT }) { }

    void OnPlayerLogin(Player* player) override
    {
        native_transmog::ApplicationService::Instance().LoadPlayer(player);
    }

    void OnPlayerUpdate(Player* player, std::uint32_t diff) override
    {
        native_transmog::Service::Instance().UpdateSession(player, diff);
        native_transmog::QuestBackfillService::Instance().Update(player, diff);
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        native_transmog::Service::Instance().CloseSession(player, false);
        native_transmog::ApplicationService::Instance().ReleasePlayer(player);
        native_transmog::CollectionService::Instance().ReleasePlayer(player);
        native_transmog::WardrobeService::Instance().ReleasePlayer(player);
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

    void OnPlayerAfterMoveItemFromInventory(Player*, Item* item, std::uint8_t, std::uint8_t, bool) override
    {
        native_transmog::ApplicationService::Instance().RemoveForTransferredItem(item);
    }

    void OnPlayerEquip(Player* player, Item* item, std::uint8_t bag, std::uint8_t slot, bool) override
    {
        if (!player || !item || bag != INVENTORY_SLOT_BAG_0 || slot >= EQUIPMENT_SLOT_END)
            return;

        // OnPlayerEquip is post-success in the Playerbot core. Resolve the
        // authoritative slot anyway so an attempted or stale item can never
        // unlock an appearance.
        Item* equipped = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot);
        if (equipped != item || !equipped->IsEquipped() || equipped->GetOwnerGUID() != player->GetGUID())
            return;

        native_transmog::CollectionService::Instance().Unlock(
            player, equipped, native_transmog::AcquisitionSource::Equipment);
    }

    void OnPlayerAfterSetVisibleItemSlot(Player* player, std::uint8_t slot, Item* item) override
    {
        native_transmog::ApplicationService::Instance().ApplyVisible(player, slot, item);
        native_transmog::WardrobeService::Instance().EquipmentChanged(player, slot, item);
    }

    bool OnPlayerCanUseChat(Player* player, std::uint32_t type, std::uint32_t language,
        std::string& message, Player* receiver) override
    {
        if (type != CHAT_MSG_WHISPER || language != LANG_ADDON || !player || receiver != player)
            return true;
        if (message.rfind("NTRANSMOG\t", 0) != 0)
            return true;
        // Outbound server messages pass through Player::Whisper and therefore
        // this hook too. Let only the response vocabulary reach FrameXML;
        // consume every client-originated request/unknown version for our prefix.
        bool const response = message.rfind("NTRANSMOG\t2\tOPEN\t", 0) == 0 ||
            message.rfind("NTRANSMOG\t2\tCLOSE\t", 0) == 0 ||
            message.rfind("NTRANSMOG\t2\tSTATE\t", 0) == 0 ||
            message.rfind("NTRANSMOG\t2\tPAGE\t", 0) == 0 ||
            message.rfind("NTRANSMOG\t2\tITEM\t", 0) == 0 ||
            message.rfind("NTRANSMOG\t2\tEND\t", 0) == 0 ||
            message.rfind("NTRANSMOG\t2\tRESULT\t", 0) == 0;
        if (response)
            return true;
        native_transmog::WardrobeService::Instance().HandleAddonWhisper(player, message);
        return false;
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

class NativeTransmogGlobalScript final : public GlobalScript
{
public:
    NativeTransmogGlobalScript() : GlobalScript("NativeTransmogGlobalScript",
        { GLOBALHOOK_ON_ITEM_DEL_FROM_DB, GLOBALHOOK_ON_MIRRORIMAGE_DISPLAY_ITEM }) { }

    void OnItemDelFromDB(CharacterDatabaseTransaction transaction, ObjectGuid::LowType itemGuid) override
    {
        native_transmog::ApplicationService::Instance().RemoveForDeletedItem(transaction, itemGuid);
    }

    void OnMirrorImageDisplayItem(Item const* item, std::uint32_t& displayId) override
    {
        native_transmog::ApplicationService::Instance().ResolveMirrorImage(item, displayId);
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
        static ChatCommandTable appearanceCommands = {
            { "apply", HandleAppearanceApply, rbac::RBAC_PERM_COMMAND_NPC_ADD, Console::No },
            { "remove", HandleAppearanceRemove, rbac::RBAC_PERM_COMMAND_NPC_DELETE, Console::No },
            { "info", HandleAppearanceInfo, rbac::RBAC_PERM_COMMAND_NPC_INFO, Console::No }
        };
        static ChatCommandTable rootCommands = {
            { "npc", npcCommands },
            { "collection", collectionCommands },
            { "appearance", appearanceCommands }
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
            "Phase 3C revalidates ownership and compatibility whenever an appearance is applied.");
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

    static bool HandleAppearanceApply(ChatHandler* handler, std::uint8_t equipmentSlot,
        std::uint32_t appearanceItem)
    {
        Player* target = SelectedOrSelfPlayer(handler);
        if (!target)
            return false;
        if (handler->HasLowerSecurity(target))
            return false;
        native_transmog::ApplicationResult result = native_transmog::ApplicationService::Instance().Apply(
            target, equipmentSlot, appearanceItem, native_transmog::ApplicationAuthorization::GmDiagnostic);
        if (result != native_transmog::ApplicationResult::Ok)
        {
            handler->SendErrorMessage("Native Transmog diagnostic apply failed: {}.",
                native_transmog::ApplicationService::ResultName(result));
            return false;
        }
        handler->PSendSysMessage(
            "Native Transmog: applied collected appearance item {} to {} equipment slot {}.",
            appearanceItem, target->GetName(), equipmentSlot);
        return true;
    }

    static bool HandleAppearanceRemove(ChatHandler* handler, std::uint8_t equipmentSlot)
    {
        Player* target = SelectedOrSelfPlayer(handler);
        if (!target)
            return false;
        if (handler->HasLowerSecurity(target))
            return false;
        native_transmog::ApplicationResult result = native_transmog::ApplicationService::Instance().Remove(
            target, equipmentSlot, native_transmog::ApplicationAuthorization::GmDiagnostic);
        if (result != native_transmog::ApplicationResult::Ok)
        {
            handler->SendErrorMessage("Native Transmog diagnostic removal failed: {}.",
                native_transmog::ApplicationService::ResultName(result));
            return false;
        }
        handler->PSendSysMessage("Native Transmog: removed the appearance override from {} equipment slot {}.",
            target->GetName(), equipmentSlot);
        return true;
    }

    static bool HandleAppearanceInfo(ChatHandler* handler, std::uint8_t equipmentSlot)
    {
        Player* target = SelectedOrSelfPlayer(handler);
        if (!target || !native_transmog::IsSupportedEquipmentSlot(equipmentSlot))
            return false;
        if (handler->HasLowerSecurity(target))
            return false;
        Item* item = target->GetItemByPos(INVENTORY_SLOT_BAG_0, equipmentSlot);
        if (!item)
        {
            handler->SendErrorMessage("Native Transmog: {} has no item in equipment slot {}.",
                target->GetName(), equipmentSlot);
            return false;
        }
        native_transmog::AppearanceOverride appearanceOverride;
        if (!native_transmog::ApplicationService::Instance().GetOverride(item, appearanceOverride))
        {
            handler->PSendSysMessage("Native Transmog: item {} in {} slot {} has no appearance override.",
                item->GetGUID().GetCounter(), target->GetName(), equipmentSlot);
            return true;
        }
        if (appearanceOverride.state == native_transmog::OverrideState::Hidden)
            handler->PSendSysMessage("Native Transmog: item {} in {} slot {} is explicitly hidden.",
                appearanceOverride.itemGuid, target->GetName(), equipmentSlot);
        else
            handler->PSendSysMessage(
                "Native Transmog: item {} in {} slot {} uses appearance item {} (display {}, class {}, "
                "subclass {}, inventory {}).",
                appearanceOverride.itemGuid, target->GetName(), equipmentSlot, appearanceOverride.appearanceItem,
                appearanceOverride.appearance.displayId, appearanceOverride.appearance.itemClass,
                appearanceOverride.appearance.itemSubclass, appearanceOverride.appearance.inventoryType);
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
    new NativeTransmogGlobalScript();
    new NativeTransmogCommandScript();
}
