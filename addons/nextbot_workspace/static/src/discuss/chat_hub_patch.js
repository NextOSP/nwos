import { ChatHub } from "@mail/core/common/chat_hub_model";
import { fields } from "@mail/core/common/record";
import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

/**
 * NextBot no longer lives in Discuss: its conversations are hidden server-side
 * and bot messages are posted silently. These patches keep NextBot threads out
 * of the remaining client-side surfaces (messaging menu, sidebar, chathub) even
 * when a thread record reaches the store, e.g. restored from localStorage.
 */
patch(Thread.prototype, {
    setup() {
        super.setup();
        this.displayToSelf = fields.Attr(false, {
            /** @this {import("models").Thread} */
            compute() {
                if (this.isNextBotThread) {
                    return false;
                }
                return (
                    this.self_member_id?.is_pinned ||
                    (["channel", "group"].includes(this.channel_type) &&
                        this.hasSelfAsMember &&
                        !this.parent_channel_id)
                );
            },
            onUpdate() {
                this.onPinStateUpdated();
            },
        });
    },
    get isNextBotThread() {
        const bot = this.store.nwosbot;
        if (!bot || this.model !== "discuss.channel") {
            return false;
        }
        if (!["chat", "group"].includes(this.channel_type)) {
            return false;
        }
        return Boolean(
            this.correspondent?.persona?.eq(bot) ||
                this.channel_member_ids?.some((member) => member.persona?.eq(bot))
        );
    },
});

patch(ChatHub.prototype, {
    async _load(str) {
        await super._load(str);
        // Drop chat windows persisted in localStorage before NextBot moved out
        // of Discuss, so no floating bot bubble is restored on reload.
        for (const chatWindow of [...this.opened, ...this.folded]) {
            if (chatWindow.thread?.isNextBotThread) {
                chatWindow.close({ force: true });
            }
        }
    },
});
