import { Component, onWillStart, onMounted, onPatched, onWillUnmount, useRef, useState } from "@nwos/owl";
import { loadCarbonCharts } from "../carbon_charts_loader";

/**
 * Mounts a single @carbon/charts chart (already adapted to `{className, data,
 * options}` by chart_adapter) into a ref div.
 *
 * The library is loaded in this component's own onWillStart, so only the chart
 * area waits on it — the rest of the dashboard (KPIs, tables, sidebar) renders
 * immediately. Drawing happens in onMounted/onPatched (so the ref div is
 * guaranteed to be in the DOM — avoids the earlier "el is null" race), and the
 * chart is only rebuilt when its data/type actually changes.
 */
export class CarbonChart extends Component {
    static template = "nwos_carbon_dashboard.CarbonChart";
    static props = {
        spec: Object, // { className, data, options } from runtimeToCarbonChart
    };

    setup() {
        this.rootRef = useRef("chart");
        this._chart = null;
        this._sig = null;
        this.libState = useState({ ready: Boolean(window.Charts) });

        onWillStart(async () => {
            try {
                await loadCarbonCharts();
                this.libState.ready = true;
            } catch (e) {
                console.error("[CarbonChart] failed to load @carbon/charts", e);
            }
        });

        onMounted(() => this.renderChart());
        onPatched(() => this.renderChart());
        onWillUnmount(() => this.destroyChart());
    }

    _signature(spec) {
        return spec.className + "|" + JSON.stringify(spec.data);
    }

    renderChart() {
        const el = this.rootRef.el;
        const spec = this.props.spec;
        const Charts = window.Charts;
        if (!el || !Charts || !spec) {
            return;
        }
        const sig = this._signature(spec);
        if (this._chart && sig === this._sig) {
            return; // nothing changed
        }
        this.destroyChart();
        const Klass = Charts[spec.className];
        if (!Klass) {
            return;
        }
        try {
            this._chart = new Klass(el, { data: spec.data, options: spec.options });
            this._sig = sig;
        } catch (e) {
            console.error("[CarbonChart] construct failed", spec.className, e);
        }
    }

    destroyChart() {
        if (this._chart) {
            try {
                this._chart.destroy();
            } catch {
                // ignore: carbon may already have torn down on DOM removal
            }
            this._chart = null;
            this._sig = null;
        }
        if (this.rootRef.el) {
            this.rootRef.el.replaceChildren();
        }
    }
}
