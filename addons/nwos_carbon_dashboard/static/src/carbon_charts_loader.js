import { loadBundle } from "@web/core/assets";

/**
 * Lazily load the vendored @carbon/charts UMD bundle (+ its CSS) and return the
 * library global. The UMD build (dist/umd/bundle.umd.js) exposes `window.Charts`
 * with d3 bundled in, so no separate d3 is required. `loadBundle` is cached and
 * idempotent, so this is safe to call from every chart component.
 *
 * @returns {Promise<object>} the `Charts` namespace (LineChart, DonutChart, ...)
 */
export async function loadCarbonCharts() {
    await loadBundle("nwos_carbon_dashboard.carbon_charts_lib");
    if (!window.Charts) {
        throw new Error("@carbon/charts failed to load (window.Charts is undefined)");
    }
    return window.Charts;
}
