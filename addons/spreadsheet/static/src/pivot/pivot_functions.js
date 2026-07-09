// @ts-check

import { _t } from "@web/core/l10n/translation";

import * as spreadsheet from "@nwos/o-spreadsheet";

const { arg, isMatrix, toJsDate, toString } = spreadsheet.helpers;
const { functionRegistry } = spreadsheet.registries;

/**
 * @typedef {import("@spreadsheet").CustomFunctionDescription} CustomFunctionDescription
 * @typedef {import("@nwos/o-spreadsheet").FPayload} FPayload
 */

//--------------------------------------------------------------------------
// Spreadsheet functions
//--------------------------------------------------------------------------

// NWOS.FILTER.VALUE

const NWOS_FILTER_VALUE = /** @satisfies {CustomFunctionDescription} */ ({
    description: _t("Return the current value of a spreadsheet filter."),
    args: [arg("filter_name (string)", _t("The label of the filter whose value to return."))],
    category: "NWOS",
    /**
     * @param {FPayload} filterName
     */
    compute: function (filterName) {
        const unEscapedFilterName = toString(filterName).replaceAll('\\"', '"');
        return this.getters.getFilterDisplayValue(unEscapedFilterName);
    },
});

// NWOS.FILTER.VALUE.V18 / NWOS.FILTER.LABEL

const NWOS_FILTER_LABEL = /** @satisfies {CustomFunctionDescription} */ ({
    description: _t("Return the label of the current value of a spreadsheet filter."),
    args: [arg("filter_name (string)", _t("The label of the filter whose value to return."))],
    category: "NWOS",
    compute: function (filterName) {
        const filter = this.getters.getGlobalFilterByName(toString(filterName, this.locale));
        const value = this["NWOS.FILTER.VALUE"](filterName);
        if (filter?.type === "relation") {
            const csvIds = toString(value[0][0]);
            if (!csvIds) {
                return value;
            }
            const ids = csvIds.split(",").map((id) => parseInt(id, 10));
            const result = this.nwosDataProvider.serverData.get(
                filter.modelName,
                "web_search_read",
                [[["id", "in", ids]], { display_name: {} }]
            );
            return result.records.map((record) => record.display_name).join(", ");
        }
        if (filter?.type !== "date" || !isMatrix(value)) {
            return value;
        }
        const startValue = value[0][0];
        const endValue = value[1][0];
        if (!toString(startValue) && !toString(endValue)) {
            return "";
        }
        const start = toJsDate(startValue, this.locale);
        const end = toJsDate(endValue, this.locale);
        const endOfMonth = toJsDate(this["MONTH.END"](endValue), this.locale);
        if (start.getDate() !== 1 || end.getDate() !== endOfMonth.getDate()) {
            return value;
        } else if (start.getMonth() === end.getMonth()) {
            return String(start.getMonth() + 1).padStart(2, "0") + "/" + start.getFullYear();
        } else if (end.getMonth() - start.getMonth() === 2) {
            const quarter = Math.floor(start.getMonth() / 3) + 1;
            return "Q" + quarter + "/" + start.getFullYear();
        } else if (start.getFullYear() === end.getFullYear()) {
            return toString(start.getFullYear(), this.locale);
        }
        return value;
    },
});

const NWOS_FILTER_VALUE_V18 = /** @satisfies {CustomFunctionDescription} */ ({
    ...NWOS_FILTER_LABEL,
    description: _t(
        "Compatibility version of NWOS.FILTER.VALUE for v18 spreadsheets. Required for date filters. Optional for others."
    ),
    hidden: true,
});

functionRegistry
    .add("NWOS.FILTER.VALUE", NWOS_FILTER_VALUE)
    .add("NWOS.FILTER.VALUE.V18", NWOS_FILTER_VALUE_V18)
    .add("NWOS.FILTER.LABEL", NWOS_FILTER_LABEL);
