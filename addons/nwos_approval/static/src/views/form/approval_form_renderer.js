import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { FormRenderer } from "@web/views/form/form_renderer";

import { ApprovalBanner } from "@nwos_approval/components/approval_banner/approval_banner";

patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        this.approvalComponents = { ApprovalBanner };
    },

    /**
     * Synchronous fast path: models without an approval rule never render the
     * banner and never issue an RPC. The list comes from session_info.
     */
    get hasApprovalBanner() {
        const record = this.props.record;
        if (!record || !record.resId) {
            return false;
        }
        return (session.approval_models || []).includes(record.resModel);
    },
});
