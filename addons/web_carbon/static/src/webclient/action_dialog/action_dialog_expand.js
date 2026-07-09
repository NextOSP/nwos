/**
 * Add a "view in full" affordance to act_window target="new" dialogs.
 *
 * FormViewDialog already exposes an expand button (via its `onExpand`/`canExpand`
 * props), but plain `act_window target="new"` actions are rendered by ActionDialog,
 * which offers no way to pop the record out to its full-page form. For large
 * records (a sale order, an invoice…) the cramped dialog hides most of the form,
 * so we add an expand button in the header that reopens the same record full-page.
 *
 * Non-invasive: patches the ActionDialog component; the button itself is added in
 * action_dialog_expand.xml (which extends web.ActionDialog.header).
 */
import { patch } from "@web/core/utils/patch";
import { ActionDialog } from "@web/webclient/actions/action_dialog";

patch(ActionDialog.prototype, {
    /** Only for act_window form dialogs bound to a saved record. */
    get canExpandRecord() {
        const p = this.props.actionProps;
        return !!(
            this.props.actionType === "ir.actions.act_window" &&
            p &&
            p.type === "form" &&
            p.resModel &&
            typeof p.resId === "number" &&
            p.resId
        );
    },

    /** Close the dialog and reopen the record in its full-page form view. */
    expandRecordToFull() {
        const p = this.props.actionProps;
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: p.resModel,
            res_id: p.resId,
            views: [[false, "form"]],
            target: "current",
            context: p.context || {},
        });
        this.props.close();
    },
});
