/**
 * IBM Carbon data-visualization palette + helpers.
 *
 * The hexes are the official Carbon "categorical" sequence (14 colors) used to
 * color chart series. They are intentionally the data-viz palette, distinct
 * from the UI color tokens in web_carbon's carbon_tokens.scss, and live in JS
 * because they drive the @carbon/charts `options.color.scale` object.
 * https://carbondesignsystem.com/data-visualization/color-palettes/
 */
export const CARBON_CATEGORICAL = [
    "#6929c4", // purple 70
    "#1192e8", // cyan 50
    "#005d5d", // teal 70
    "#9f1853", // magenta 70
    "#fa4d56", // red 50
    "#570408", // red 90
    "#198038", // green 60
    "#002d9c", // blue 80
    "#ee538b", // magenta 50
    "#b28600", // yellow 50
    "#009d9a", // teal 50
    "#012749", // cyan 90
    "#8a3800", // orange 70
    "#a56eff", // purple 50
];

// Single-series brand color (Carbon Blue 60), matches web_carbon $carbon-blue-60.
export const CARBON_BRAND = "#0f62fe";

/**
 * Build a @carbon/charts `color.scale` mapping each group name to a categorical
 * color, cycling the palette. A single group falls back to the brand blue.
 *
 * @param {string[]} groups distinct series/group names (in display order)
 * @returns {Object<string,string>}
 */
export function buildColorScale(groups) {
    const scale = {};
    const unique = [...new Set(groups.filter((g) => g !== undefined && g !== null))];
    unique.forEach((group, i) => {
        scale[group] = unique.length === 1 ? CARBON_BRAND : CARBON_CATEGORICAL[i % CARBON_CATEGORICAL.length];
    });
    return scale;
}
