import { Store } from "@mail/core/common/store_service";

import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { escape } from "@web/core/utils/strings";

/** @type {import("models").Store} */
const nextBotStorePatch = {
    handleClickOnLink(ev, thread) {
        const suggestion = ev.target.closest("a.o_nextbot_suggestion");
        if (suggestion) {
            ev.preventDefault();
            let message = suggestion.dataset.nextbotMessage;
            const href = suggestion.getAttribute("href") || "";
            if (!message && href.startsWith("#nextbot-message=")) {
                message = decodeURIComponent(href.slice("#nextbot-message=".length));
            }
            message ||= suggestion.textContent.trim();
            if (message && thread?.post) {
                suggestion.classList.add("disabled");
                Promise.resolve(thread.post(`<p>${escape(message)}</p>`))
                    .then(() => this.onLinkFollowed(thread))
                    .catch(() => suggestion.classList.remove("disabled"));
            }
            return true;
        }
        const link = ev.target.closest("a.o_nextbot_record_modal");
        if (link) {
            const model = link.dataset.oeModel;
            const id = Number(link.dataset.oeId);
            if (model && id) {
                ev.preventDefault();
                Promise.resolve(
                    this.env.services.action.doAction({
                        type: "ir.actions.act_window",
                        res_model: model,
                        views: [[false, "form"]],
                        res_id: id,
                        target: "new",
                        context: user.context,
                    })
                ).then(() => this.onLinkFollowed(thread));
                return true;
            }
        }
        return super.handleClickOnLink(...arguments);
    },
};

patch(Store.prototype, nextBotStorePatch);
