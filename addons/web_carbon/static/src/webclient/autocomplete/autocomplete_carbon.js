/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";

/**
 * Carbon Dropdown / ComboBox width.
 *
 * An IBM Carbon dropdown's list box spans the full width of its control and
 * sits flush under it. Odoo's positioning hook only sets the menu's top/left,
 * leaving its width to the CSS default (content width, min 150px). On a wide
 * field that reads as a small floating box offset under the input — not a
 * Carbon dropdown.
 *
 * We hook the existing `onPositioned` callback (invoked on every reposition, so
 * it survives scroll/resize) to stretch the menu to the width of its visible
 * input control and align it to that control's left edge. This distinction
 * matters for composite product fields, whose outer field widget also contains
 * a description/configuration button. Fixed positioning and Odoo's automatic
 * flip-above-when-clipped behaviour are left untouched — we only override width
 * and horizontal origin. Outside an input wrapper/field (e.g. the search bar),
 * we fall back to the input width so nothing regresses.
 */
patch(AutoComplete.prototype, {
    get dropdownOptions() {
        const options = super.dropdownOptions;
        const previous = options.onPositioned;
        return {
            ...options,
            onPositioned: (popper, solution) => {
                previous?.(popper, solution);
                const input = this.targetDropdown;
                const anchor =
                    input?.closest(".o_input_dropdown") ||
                    input?.closest(".o_field_widget") ||
                    input;
                if (anchor && popper) {
                    const rect = anchor.getBoundingClientRect();
                    popper.style.width = `${rect.width}px`;
                    popper.style.minWidth = "0";
                    popper.style.left = `${rect.left}px`;
                }
            },
        };
    },
});
