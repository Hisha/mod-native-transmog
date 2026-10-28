#include "Config.h"
#include "Log.h"
#include "ScriptMgr.h"

namespace
{
struct NativeTransmogConfig
{
    bool enabled = true;
    bool allowTwoHandAppearanceOnOneHand = false;
    bool allowOneHandAppearanceOnTwoHand = false;
};

NativeTransmogConfig config;

class NativeTransmogWorldScript final : public WorldScript
{
public:
    NativeTransmogWorldScript() : WorldScript("NativeTransmogWorldScript",
        { WORLDHOOK_ON_AFTER_CONFIG_LOAD, WORLDHOOK_ON_STARTUP })
    {
    }

    void OnAfterConfigLoad(bool reload) override
    {
        config.enabled = sConfigMgr->GetOption<bool>("NativeTransmog.Enable", true);
        config.allowTwoHandAppearanceOnOneHand = sConfigMgr->GetOption<bool>(
            "NativeTransmog.AllowTwoHandAppearanceOnOneHand", false);
        config.allowOneHandAppearanceOnTwoHand = sConfigMgr->GetOption<bool>(
            "NativeTransmog.AllowOneHandAppearanceOnTwoHand", false);

        if (reload)
            LOG_INFO("server.loading", "Native Transmog Phase 1 configuration reloaded.");
    }

    void OnStartup() override
    {
        if (!config.enabled)
        {
            LOG_INFO("server.loading", "Native Transmog is disabled by configuration.");
            return;
        }

        LOG_INFO("server.loading", "Native Transmog Phase 1 wardrobe prototype initialized.");
        LOG_INFO("server.loading",
            "Native Transmog weapon compatibility options are reserved and are not enforced in Phase 1 "
            "(two-hand-on-one-hand: {}, one-hand-on-two-hand: {}).",
            config.allowTwoHandAppearanceOnOneHand, config.allowOneHandAppearanceOnTwoHand);
    }
};
}

void AddNativeTransmogModuleScripts()
{
    new NativeTransmogWorldScript();
}
