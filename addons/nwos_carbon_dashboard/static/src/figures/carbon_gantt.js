import { Component, onWillStart, useState } from "@nwos/owl";
import { useService } from "@web/core/utils/hooks";

// Carbon status colors for the manufacturing order states.
const STATE_COLORS = {
    draft: "#8d8d8d", // gray-50
    confirmed: "#0f62fe", // blue-60
    progress: "#1192e8", // cyan-50
    to_close: "#8a3ffc", // purple-60
    done: "#24a148", // green-50
    cancel: "#da1e28", // red-60
};
const STATE_LABELS = {
    draft: "Draft",
    confirmed: "Confirmed",
    progress: "In Progress",
    to_close: "To Close",
    done: "Done",
    cancel: "Cancelled",
};

/**
 * A lightweight, Carbon-styled Gantt/timeline of manufacturing orders. Each MO
 * is a horizontal bar from date_start to date_finished, positioned on a shared
 * time axis and colored by status. @carbon/charts has no Gantt, so this is a
 * plain OWL + CSS component fed directly from mrp.production.
 */
export class CarbonGantt extends Component {
    static template = "nwos_carbon_dashboard.CarbonGantt";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ tasks: [], loading: true });
        onWillStart(async () => {
            try {
                this.state.tasks = await this.orm.searchRead(
                    "mrp.production",
                    [["date_start", "!=", false]],
                    ["name", "date_start", "date_finished", "date_deadline", "state", "product_qty"],
                    { limit: 20, order: "date_start desc" }
                );
            } catch {
                this.state.tasks = [];
            }
            this.state.loading = false;
        });
    }

    /** Open a manufacturing order's form view. */
    openMO(id) {
        if (!id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    _parse(d) {
        return d ? new Date(String(d).replace(" ", "T")) : null;
    }
    _fmt(d) {
        return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    }

    /**
     * Computed rows + weekly ticks on a fixed pixel-per-day scale, so bar
     * durations are visible and the timeline scrolls horizontally when the date
     * range is wide.
     */
    get gantt() {
        const DAY = 86400000;
        const PX_PER_DAY = 22; // 1 week ≈ 154px → weeks are prominent, timeline scrolls
        const bars = [];
        for (const t of this.state.tasks) {
            const s = this._parse(t.date_start);
            if (!s) {
                continue;
            }
            let e = this._parse(t.date_finished) || this._parse(t.date_deadline) || s;
            if (e < s) {
                e = s;
            }
            bars.push({ id: t.id, name: t.name, state: t.state, start: s, end: e });
        }
        if (!bars.length) {
            return { rows: [], ticks: [], width: 0 };
        }
        bars.sort((a, b) => a.start - b.start);
        // Snap the range to whole days and pad a few days each side.
        const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
        const min = startOfDay(new Date(Math.min(...bars.map((b) => b.start))));
        min.setDate(min.getDate() - 2);
        const max = startOfDay(new Date(Math.max(...bars.map((b) => b.end))));
        max.setDate(max.getDate() + 4);
        const width = Math.max(1, Math.round(((max - min) / DAY) * PX_PER_DAY));

        const rows = bars.map((b) => {
            const leftPx = ((b.start - min) / DAY) * PX_PER_DAY;
            let widthPx = ((b.end - b.start) / DAY) * PX_PER_DAY;
            if (widthPx < PX_PER_DAY) {
                widthPx = PX_PER_DAY; // at least a day wide
            }
            return {
                id: b.id,
                name: b.name,
                leftPx: Math.round(leftPx),
                widthPx: Math.round(widthPx),
                color: STATE_COLORS[b.state] || "#8d8d8d",
                stateLabel: STATE_LABELS[b.state] || b.state,
                tip: `${b.name} · ${STATE_LABELS[b.state] || b.state} (${this._fmt(b.start)} → ${this._fmt(b.end)})`,
            };
        });

        // Weekly ticks from the Monday on/before the start.
        const ticks = [];
        const firstMonday = new Date(min);
        const dow = (firstMonday.getDay() + 6) % 7; // 0 = Monday
        firstMonday.setDate(firstMonday.getDate() - dow);
        for (let t = new Date(firstMonday); t <= max; t.setDate(t.getDate() + 7)) {
            const leftPx = ((t - min) / DAY) * PX_PER_DAY;
            if (leftPx >= 0 && leftPx <= width) {
                ticks.push({
                    leftPx: Math.round(leftPx),
                    label: t.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
                });
            }
        }
        return { rows, ticks, width };
    }
}
