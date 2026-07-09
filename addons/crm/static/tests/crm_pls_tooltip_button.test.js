import { expect, test } from "@nwos/hoot";
import { animationFrame } from "@nwos/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";

import "@crm/views/crm_form/crm_pls_tooltip_button";

class Lead extends models.Model {
    _name = "crm.lead";

    name = fields.Char();
    probability = fields.Float();

    _records = [
        {
            id: 1,
            name: "Lead without tooltip entries",
            probability: 72,
        },
    ];
}

defineModels([Lead]);

test("PLS tooltip handles missing scoring entries", async () => {
    onRpc("crm.lead", "prepare_pls_tooltip_data", () => {
        expect.step("prepare_pls_tooltip_data");
        return {
            probability: 72,
            team_name: "Direct Sales",
        };
    });

    await mountView({
        type: "form",
        resModel: "crm.lead",
        resId: 1,
        arch: /* xml */ `
            <form>
                <widget name="pls_tooltip_button"/>
                <field name="probability"/>
            </form>`,
    });

    await contains(".o_crm_pls_tooltip_button").click();
    await animationFrame();
    expect.verifySteps(["prepare_pls_tooltip_data"]);
    expect(".o_crm_pls_tooltip").toHaveCount(1);
    expect(".o_crm_pls_tooltip h5").toHaveText("Top Positives");
    expect(".o_crm_pls_tooltip").toHaveText(/Historic win rate/);
});
