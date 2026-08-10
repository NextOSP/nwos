import { patch } from "@web/core/utils/patch";
import { createElement, setAttributes } from "@web/core/utils/xml";
import { FormCompiler } from "@web/views/form/form_compiler";

/**
 * Splice an approval-banner hook into every compiled form view.
 *
 * The node is inert: its `t-if` is evaluated at render time, so forms of
 * models without an approval rule cost nothing. Same technique mail uses to
 * inject the chatter (addons/mail/static/src/chatter/web/form_compiler.js).
 */
patch(FormCompiler.prototype, {
    compile(node, params) {
        const res = super.compile(node, params);
        if (params && params.isSubView) {
            return res; // never inside x2many sub-forms
        }
        try {
            const hook = createElement("div", { class: "o_approval_banner_hook" });
            setAttributes(hook, { "t-if": "__comp__.hasApprovalBanner" });

            const banner = createElement("t");
            setAttributes(banner, {
                "t-component": "__comp__.approvalComponents.ApprovalBanner",
                record: "__comp__.props.record",
            });
            hook.appendChild(banner);

            const sheetBg = res.querySelector(".o_form_sheet_bg");
            if (sheetBg) {
                sheetBg.insertBefore(hook, sheetBg.firstChild);
            } else {
                res.prepend(hook);
            }
        } catch (error) {
            // A broken banner must never take the whole form view down.
            console.error("nwos_approval: could not inject the banner", error);
        }
        return res;
    },
});
