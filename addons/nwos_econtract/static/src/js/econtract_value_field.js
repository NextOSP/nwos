import { registry } from "@web/core/registry";
import { Component, xml } from "@nwos/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const { DateTime } = luxon;

/**
 * One "Value" cell that adapts to the line's field_type:
 * text input, number input, date picker, datetime picker, checkbox,
 * or a read-only signature status.
 */
export class EContractValueField extends Component {
    static template = xml`
        <t t-if="props.readonly or type === 'signature'">
            <span t-att-class="type === 'signature' and value ? 'text-success' : ''"
                  t-esc="displayValue"/>
        </t>
        <t t-elif="type === 'boolean'">
            <input type="checkbox" class="form-check-input"
                   t-att-checked="record.data.value_boolean"
                   t-on-change="(ev) => this.update('value_boolean', ev.target.checked)"/>
        </t>
        <t t-elif="type === 'date'">
            <input type="date" class="o_input"
                   t-att-value="isoDate"
                   t-on-change="(ev) => this.updateDate('value_date', ev.target.value)"/>
        </t>
        <t t-elif="type === 'datetime'">
            <input type="datetime-local" class="o_input"
                   t-att-value="isoDatetime"
                   t-on-change="(ev) => this.updateDate('value_datetime', ev.target.value)"/>
        </t>
        <t t-elif="type === 'number' or type === 'monetary'">
            <input type="number" step="any" class="o_input text-end"
                   t-att-value="record.data.value_number or ''"
                   t-att-placeholder="placeholder"
                   t-on-change="(ev) => this.update('value_number', parseFloat(ev.target.value) || 0)"/>
        </t>
        <t t-else="">
            <input type="text" class="o_input"
                   t-att-value="record.data.value_char or ''"
                   t-att-placeholder="placeholder"
                   t-on-change="(ev) => this.update('value_char', ev.target.value)"/>
        </t>
    `;
    static props = { ...standardFieldProps, placeholder: { type: String, optional: true } };

    get record() {
        return this.props.record;
    }

    get type() {
        return this.record.data.field_type;
    }

    get value() {
        return this.record.data[this.props.name];
    }

    get displayValue() {
        return this.record.data.display_value || "";
    }

    get placeholder() {
        return this.props.placeholder || "";
    }

    get isoDate() {
        const d = this.record.data.value_date;
        return d ? d.toISODate() : "";
    }

    get isoDatetime() {
        const d = this.record.data.value_datetime;
        return d ? d.toFormat("yyyy-MM-dd'T'HH:mm") : "";
    }

    update(field, value) {
        this.record.update({ [field]: value });
    }

    updateDate(field, iso) {
        this.record.update({ [field]: iso ? DateTime.fromISO(iso) : false });
    }
}

registry.category("fields").add("econtract_value", {
    component: EContractValueField,
    displayName: "eContract Value",
    supportedTypes: ["char"],
});
