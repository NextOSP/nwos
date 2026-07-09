import { Component } from "@nwos/owl";

/**
 * A Carbon KPI tile rendered from an o-spreadsheet *scorecard* runtime (a flat
 * object with no chartJsConfig). Shows the big key value, its description, and a
 * baseline delta row colored by direction. No charting library involved.
 */
export class CarbonKpiCard extends Component {
    static template = "nwos_carbon_dashboard.CarbonKpiCard";
    static props = {
        runtime: Object, // getChartRuntime(scorecardId)
    };

    get title() {
        return this.props.runtime.title?.text || "";
    }
    get keyValue() {
        return this.props.runtime.keyValue ?? "";
    }
    get keyDescr() {
        return this.props.runtime.keyDescr || "";
    }
    get baselineDisplay() {
        return this.props.runtime.baselineDisplay || "";
    }
    get baselineDescr() {
        return this.props.runtime.baselineDescr || "";
    }
    /** @returns {"up"|"down"|"neutral"} */
    get arrow() {
        return this.props.runtime.baselineArrow || "neutral";
    }
    get arrowGlyph() {
        return { up: "▲", down: "▼", neutral: "" }[this.arrow];
    }
    get progressBar() {
        return this.props.runtime.progressBar;
    }
    get progressPercent() {
        const pb = this.progressBar;
        if (!pb) {
            return 0;
        }
        return Math.max(0, Math.min(100, Math.abs(Number(pb.value) || 0) * 100));
    }
}
