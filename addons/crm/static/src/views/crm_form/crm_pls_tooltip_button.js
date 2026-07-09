import { Component, status, useState } from "@nwos/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { localization } from "@web/core/l10n/localization";
import { registry } from '@web/core/registry';
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";


export class CrmPlsTooltip extends Component {
    static props = {
        aiProviderName: { optional: true, type: [String, Boolean] },
        close: { optional: true, type: Function },
        dashArrayVals: {type: String},
        isLoading: { optional: true, type: Boolean },
        low3Data: { optional: true, type: Array },
        probability: { type: Number },
        teamName: { optional: true, type: [String, Boolean] },
        top3Data: { optional: true, type: Array },
    };
    static template = "crm.PlsTooltip";
}


export class CrmPlsTooltipButton extends Component {
    static template = "crm.PlsTooltipButton";
    static props = {...standardWidgetProps};

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({ isLoading: false });
        this.tooltipRequestId = 0;
        this.popover = usePopover(CrmPlsTooltip, {
            popoverClass: 'mt-2 me-2',
            position: "bottom-start",
        });
    }

    async onClickPlsTooltipButton(ev) {
        const tooltipButtonEl = ev.currentTarget;
        if (this.popover.isOpen) {
            this.tooltipRequestId++;
            this.state.isLoading = false;
            this.popover.close();
        } else {
            const requestId = ++this.tooltipRequestId;
            this.state.isLoading = true;
            this.popover.open(tooltipButtonEl, {
                isLoading: true,
                dashArrayVals: "",
                low3Data: [],
                probability: this.props.record.data.probability || 0,
                top3Data: [],
            });

            try {
                // Apply pending changes. They may change probability
                await this.props.record.save();
                if (status(this) === "destroyed" || requestId !== this.tooltipRequestId) {
                    return;
                }
                if (!this.props.record.resId) {
                    this.popover.close();
                    return;
                }

                // This recomputes probability, and returns all tooltip data
                const tooltipData = await this.orm.call(
                    "crm.lead",
                    "prepare_pls_tooltip_data",
                    [this.props.record.resId]
                ) || {};
                if (status(this) === "destroyed" || requestId !== this.tooltipRequestId) {
                    return;
                }

                // Update the form
                await this.props.record.load();
                if (
                    status(this) === "destroyed" ||
                    requestId !== this.tooltipRequestId ||
                    !this.popover.isOpen
                ) {
                    return;
                }

                // Hard set wheel dimensions, see o_crm_pls_tooltip_wheel in scss and xml
                const probability = tooltipData.probability || 0;
                const progressWheelPerimeter = 2 * Math.PI * 25;
                const progressBarDashLength = progressWheelPerimeter * probability / 100.0;
                const progressBarDashGap = progressWheelPerimeter - progressBarDashLength;
                let dashArrayVals = progressBarDashLength + ' ' + progressBarDashGap;
                if (localization.direction === "rtl") {
                    dashArrayVals = 0 + ' ' + 0.5 * progressWheelPerimeter + ' ' + dashArrayVals;
                }
                this.popover.open(tooltipButtonEl, {
                    'aiProviderName': tooltipData.ai_provider_name,
                    'dashArrayVals': dashArrayVals,
                    'low3Data': tooltipData.low_3_data || [],
                    'probability': probability,
                    'teamName': tooltipData.team_name,
                    'top3Data': tooltipData.top_3_data || [],
                });
            } catch (error) {
                if (requestId === this.tooltipRequestId) {
                    this.popover.close();
                }
                throw error;
            } finally {
                if (requestId === this.tooltipRequestId) {
                    this.state.isLoading = false;
                }
            }
        }
    }
}

registry.category("view_widgets").add("pls_tooltip_button", {
    component: CrmPlsTooltipButton
});
