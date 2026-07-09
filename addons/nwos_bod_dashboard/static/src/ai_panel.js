import { _t } from "@web/core/l10n/translation";
import { Component, useState, useRef } from "@nwos/owl";
import { rpc } from "@web/core/network/rpc";

export class BodAiPanel extends Component {
    static template = "nwos_bod_dashboard.BodAiPanel";
    static props = {
        available: { type: Boolean, optional: true },
        getContext: { type: Function, optional: true },
        onClose: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            question: "",
            pending: false,
            messages: [], // { role: 'user'|'assistant'|'error', text }
        });
        this.inputRef = useRef("input");
        this.suggestions = [
            _t("How is revenue trending vs the previous period?"),
            _t("Who are our top 5 customers this period?"),
            _t("How much is overdue in receivables?"),
        ];
    }

    async ask(question) {
        question = (question || this.state.question).trim();
        if (!question || this.state.pending) {
            return;
        }
        this.state.messages.push({ role: "user", text: question });
        this.state.question = "";
        this.state.pending = true;
        try {
            const context = this.props.getContext ? this.props.getContext() : null;
            const res = await rpc("/nwos_bod/ask_ai", { question, context });
            if (res && res.error) {
                this.state.messages.push({ role: "error", text: res.error });
            } else {
                this.state.messages.push({
                    role: "assistant",
                    text: (res && res.answer) || _t("No answer."),
                });
            }
        } catch (error) {
            const detail =
                error?.data?.message ||
                error?.message ||
                _t("The AI request failed. Please try again.");
            this.state.messages.push({
                role: "error",
                text: detail,
            });
        } finally {
            this.state.pending = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.ask();
        }
    }
}
