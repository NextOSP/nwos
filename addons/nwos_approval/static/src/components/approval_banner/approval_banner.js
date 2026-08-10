import { Component, onWillStart, useState } from "@nwos/owl";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";

export class ApprovalBanner extends Component {
    static template = "nwos_approval.ApprovalBanner";
    static props = { record: Object };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null });
        onWillStart(() => this.fetch());
        useRecordObserver((record) => {
            void record.resId;
            return this.fetch();
        });
    }

    async fetch() {
        const { resModel, resId } = this.props.record;
        if (!resId) {
            this.state.data = null;
            return;
        }
        this.state.data = await this.orm.call("approval.request", "approval_banner_data", [], {
            res_model: resModel,
            res_id: resId,
        });
    }

    get visible() {
        return Boolean(this.state.data && this.state.data.enabled);
    }

    get data() {
        return this.state.data || {};
    }

    get currentStep() {
        return (this.data.steps || []).find((step) => step.is_current);
    }

    get alertClass() {
        return (
            {
                pending: "alert-warning",
                approved: "alert-success",
                done: "alert-success",
                rejected: "alert-danger",
                error: "alert-danger",
                cancel: "alert-secondary",
            }[this.data.state] || "alert-info"
        );
    }

    stepClass(step) {
        if (step.status === "approved") {
            return "text-bg-success";
        }
        if (step.status === "rejected") {
            return "text-bg-danger";
        }
        if (step.is_current) {
            return "text-bg-warning fw-bold";
        }
        return "text-bg-secondary opacity-50";
    }

    stepIcon(step) {
        if (step.status === "approved") {
            return "fa fa-check";
        }
        if (step.status === "rejected") {
            return "fa fa-times";
        }
        return "fa fa-hourglass-half";
    }

    stepTooltip(step) {
        const approved = (step.approved_by || []).join(", ");
        return approved
            ? `${step.name} — approved by ${approved}`
            : `${step.name} — ${step.approver_names}`;
    }

    async runAction(method) {
        await this.action.doActionButton({
            type: "object",
            name: method,
            resModel: "approval.request",
            resId: this.data.id,
            resIds: [this.data.id],
            onClose: async () => {
                await this.props.record.load();
                await this.fetch();
            },
        });
        await this.props.record.load();
        await this.fetch();
    }

    onApprove() {
        return this.runAction("approval_action_approve");
    }

    onReject() {
        return this.runAction("approval_action_reject");
    }
}
