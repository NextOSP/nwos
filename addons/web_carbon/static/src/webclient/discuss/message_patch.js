/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Message } from "@mail/core/common/message";

/**
 * Right-align the user's own messages in the Discuss app AND popup chat windows
 * — but NOT the record chatter (or any other embedding).
 *
 * Core gates `isAlignedRight` on `env.inChatWindow`, so own messages only
 * right-align inside chat windows; the Discuss app leaves them left. We key off
 * the THREAD'S MODEL instead: channels, DMs and chat windows are all
 * `discuss.channel`, while the chatter's thread is the record's own model
 * (crm.lead, purchase.order, …). So own messages right-align on every real chat
 * surface and the chatter stays a normal left-aligned log with avatars + names.
 * (The `inDiscussApp` env flag doesn't reliably reach the Message component in
 * this build, hence the data-based signal.) Pairs with the scoped
 * `.o-mail-Discuss, .o-mail-ChatWindow` rules in components/discuss.scss.
 */
patch(Message.prototype, {
    get isAlignedRight() {
        return Boolean(
            this.props.thread?.model === "discuss.channel" &&
                this.props.message.isSelfAuthored
        );
    },
});
