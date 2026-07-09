import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const commandRegistry = registry.category("discuss.channel_commands");

commandRegistry.add("clear", {
    condition: ({ store }) => store.self_partner && !store.self.main_user_id.share,
    help: _t("Clear the pending NextBot action"),
    methodName: "execute_command_clear",
});
