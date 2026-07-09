import { registry } from "@web/core/registry";
import { booleanField } from "@web/views/fields/boolean/boolean_field";

/**
 *  The upgrade boolean field is intended to be used in config settings.
 *  Keep the widget name for compatibility with existing settings views, but
 *  handle it as a regular boolean field.
 */
export const upgradeBooleanField = {
    ...booleanField,
    additionalClasses: [...(booleanField.additionalClasses || []), "o_field_boolean"],
};

registry.category("fields").add("upgrade_boolean", upgradeBooleanField);
