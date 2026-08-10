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
 *
 * `.o_field_tags` comes FIRST in the anchor list: in a many2many_tags field the
 * `.o_input_dropdown` wrapper is only the sliver of space left over next to the
 * existing tags, so anchoring to it produced a ~100px menu whose options were
 * all ellipsized ("Ne…", "Ser…"). The tags box is the visible control there.
 *
 * A narrow anchor (editable list cell, a tags box already full of tags) would
 * still yield an unreadable menu, so the width is floored at MIN_WIDTH and then
 * pulled back inside the viewport if that floor pushes it off the right edge.
 */
const MIN_WIDTH = 240;
const VIEWPORT_MARGIN = 8;

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
                    input?.closest(".o_field_tags") ||
                    input?.closest(".o_input_dropdown") ||
                    input?.closest(".o_field_widget") ||
                    input;
                if (anchor && popper) {
                    const rect = anchor.getBoundingClientRect();
                    const available = window.innerWidth - 2 * VIEWPORT_MARGIN;
                    const width = Math.min(Math.max(rect.width, MIN_WIDTH), available);
                    const maxLeft = window.innerWidth - VIEWPORT_MARGIN - width;
                    popper.style.width = `${width}px`;
                    popper.style.minWidth = "0";
                    popper.style.left = `${Math.max(VIEWPORT_MARGIN, Math.min(rect.left, maxLeft))}px`;
                }
            },
        };
    },
});
