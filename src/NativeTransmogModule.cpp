#include "NativeTransmogService.h"

#include "AllCreatureScript.h"
#include "Chat.h"
#include "CommandScript.h"
#include "Config.h"
#include "Creature.h"
#include "Log.h"
#include "Player.h"
#include "RBAC.h"
#include "ScriptMgr.h"

#include <cstdint>

using namespace Acore::ChatCommands;

namespace
{
native_transmog::ServiceConfig serviceConfig;
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

        native_transmog::Service::Instance().Configure(serviceConfig);
        if (reload)
            LOG_INFO("server.loading", "Native Transmog Phase 2 configuration reloaded.");
    }

    void OnStartup() override
    {
        if (!serviceConfig.enabled)
        {
            LOG_INFO("server.loading", "Native Transmog is disabled by configuration.");
            return;
        }

        native_transmog::Service::Instance().LoadRegistrations();
        LOG_INFO("server.loading",
            "Native Transmog Phase 2 NPC service initialized (dedicated: {}, custom: {}, spawn registrations: {}).",
            serviceConfig.defaultNpcEnabled, serviceConfig.customNpcEnabled, serviceConfig.allowSpawnRegistration);
        LOG_INFO("server.loading",
            "Native Transmog weapon compatibility options remain reserved for a later application phase "
            "(two-hand-on-one-hand: {}, one-hand-on-two-hand: {}).",
            allowTwoHandAppearanceOnOneHand, allowOneHandAppearanceOnTwoHand);
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
          PLAYERHOOK_ON_SEND_LIST_INVENTORY, PLAYERHOOK_ON_BEFORE_RECEIVE_SPELL_LIST_FROM_TRAINER }) { }

    void OnPlayerUpdate(Player* player, std::uint32_t diff) override
    {
        native_transmog::Service::Instance().UpdateSession(player, diff);
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        native_transmog::Service::Instance().CloseSession(player, false);
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
        static ChatCommandTable rootCommands = {
            { "npc", npcCommands }
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
};
}

void AddNativeTransmogModuleScripts()
{
    new NativeTransmogWorldScript();
    new NativeTransmogCreatureScript();
    new NativeTransmogPlayerScript();
    new NativeTransmogCommandScript();
}
