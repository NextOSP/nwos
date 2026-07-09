import { expect, test } from "@nwos/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { Component, useState, xml } from "@nwos/owl";
import { NWOSLogo } from "@point_of_sale/app/components/nwos_logo/nwos_logo";
import { CenteredIcon } from "@point_of_sale/app/components/centered_icon/centered_icon";
import { Input } from "@point_of_sale/app/components/inputs/input/input";
import { NumericInput } from "@point_of_sale/app/components/inputs/numeric_input/numeric_input";
import { registry } from "@web/core/registry";
import { waitFor } from "@nwos/hoot-dom";

test("test that generic components can be mounted; the goal is to ensure that they don't have any unmet dependencies", async () => {
    class TestComponent extends Component {
        static props = [];
        static components = {
            NWOSLogo,
            CenteredIcon,
            Input,
            NumericInput,
        };
        static template = xml`
            <div class="test-container">
                <NWOSLogo />
                <CenteredIcon icon="'fa-smile'"/>
                <Input tModel="[state, 'number']"/>
                <NumericInput tModel="[state, 'number']" />
            </div>
        `;
        setup() {
            this.state = useState({ number: 1 });
        }
    }

    registry.category("services").content = {};

    await mountWithCleanup(TestComponent, {
        noMainContainer: true,
    });
    await waitFor("div.test-container");
    expect(true).toBe(true);
});
