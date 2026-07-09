import { expect, test } from "@nwos/hoot";
import { animationFrame } from "@nwos/hoot-mock";
import { click } from "@nwos/hoot-dom";
import { defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers";

class ResConfigSettings extends models.Model {
    _name = "res.config.settings";
    bar = fields.Boolean({ string: "Bar" });
}
defineModels([ResConfigSettings]);

test("widget upgrade_boolean in a form view toggles without upgrade dialog", async () => {
    await mountView({
        type: "form",
        arch: /* xml */ `
            <form js_class="base_settings">
                <app string="CRM" name="crm">
                    <field name="bar" widget="upgrade_boolean"/>
                </app>
            </form>`,
        resModel: "res.config.settings",
    });

    await click(".o-checkbox .form-check-input");
    await animationFrame();
    expect(".o_dialog .modal").toHaveCount(0, {
        message: "no upgrade dialog should be opened",
    });
    expect(".o-checkbox .form-check-input").toBeChecked({
        message: "the field should be handled as a regular boolean",
    });
});

test("widget upgrade_boolean in a form view - label has no upgrade badge", async () => {
    await mountView({
        type: "form",
        arch: /* xml */ `
            <form js_class="base_settings">
                <app string="CRM" name="crm">
                    <setting string="Coucou">
                        <field name="bar" widget="upgrade_boolean"/>
                    </setting>
                </app>
            </form>`,
        resModel: "res.config.settings",
    });

    expect(".o_field .badge").toHaveCount(0, {
        message: "the upgrade badge shouldn't be inside the field section",
    });
    expect(".o_form_label .badge").toHaveCount(0, {
        message: "the upgrade badge shouldn't be inside the label section",
    });
    expect(".o_form_label").toHaveText("Coucou", {
        message: "the label shouldn't contains the upgrade label",
    });
});
