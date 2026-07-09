import { expect, test } from "@nwos/hoot";
import { queryAll, queryAllTexts } from "@nwos/hoot-dom";
import { animationFrame } from "@nwos/hoot-mock";
import { Component, xml } from "@nwos/owl";

import {
    contains,
    defineMenus,
    makeMockEnv,
    mountWithCleanup,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { WebClient } from "@web/webclient/webclient";

test("can be rendered", async () => {
    await mountWithCleanup(WebClient);

    expect(`header > nav.o_main_navbar`).toHaveCount(1);
});

test.tags("desktop");
test("empty webclient route opens the app launcher", async () => {
    defineMenus([
        { id: 1, name: "Discuss", actionID: 124 },
        { id: 2, name: "Sales", actionID: 55 },
    ]);

    await mountWithCleanup(WebClient);
    await animationFrame();

    expect(".o_app_launcher").toHaveCount(1);
    expect(queryAllTexts(".o_app_launcher_app")).toEqual(["Discuss", "Sales"]);
    expect(".o_menu_brand").toHaveCount(0);
});

test.tags("desktop");
test("app launcher groups apps into sections", async () => {
    defineMenus([
        {
            id: 1,
            name: "Dashboards",
            actionID: 124,
            xmlid: "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
        },
        { id: 2, name: "CRM", actionID: 55, xmlid: "crm.crm_menu_root" },
        {
            id: 3,
            name: "Attendances",
            actionID: 56,
            xmlid: "hr_attendance.menu_hr_attendance_root",
        },
        {
            id: 4,
            name: "Stock Requests",
            actionID: 57,
            xmlid: "nwos_stock_request.menu_stock_request_root",
        },
        { id: 5, name: "Custom App", actionID: 58, xmlid: "custom.menu_root" },
    ]);

    await mountWithCleanup(WebClient);
    await animationFrame();

    expect(queryAllTexts(".o_app_launcher_section_title")).toEqual([
        "Overview",
        "Sales",
        "Human Resources",
        "Operations",
        "Other",
    ]);
    expect(
        queryAll(".o_app_launcher_section").map((section) => ({
            title: section.querySelector(".o_app_launcher_section_title").innerText,
            apps: [...section.querySelectorAll(".o_app_launcher_app")].map((app) => app.innerText),
        }))
    ).toEqual([
        { title: "Overview", apps: ["Dashboards"] },
        { title: "Sales", apps: ["CRM"] },
        { title: "Human Resources", apps: ["Attendances"] },
        { title: "Operations", apps: ["Stock Requests"] },
        { title: "Other", apps: ["Custom App"] },
    ]);
});

test.tags("desktop");
test("app launcher search keeps matching section only", async () => {
    defineMenus([
        {
            id: 1,
            name: "Dashboards",
            actionID: 124,
            xmlid: "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
        },
        { id: 2, name: "CRM", actionID: 55, xmlid: "crm.crm_menu_root" },
    ]);

    await mountWithCleanup(WebClient);
    await animationFrame();
    await contains(".o_app_launcher_search input").edit("crm");

    expect(queryAllTexts(".o_app_launcher_section_title")).toEqual(["Sales"]);
    expect(queryAllTexts(".o_app_launcher_app")).toEqual(["CRM"]);
});

test("can render a main component", async () => {
    class MyComponent extends Component {
        static props = {};
        static template = xml`<span class="chocolate">MyComponent</span>`;
    }

    const env = await makeMockEnv();
    registry.category("main_components").add("mycomponent", { Component: MyComponent });

    await mountWithCleanup(WebClient, { env });

    expect(`.chocolate`).toHaveCount(1);
});

test.tags("desktop");
test("control-click <a href/> in a standalone component", async () => {
    class MyComponent extends Component {
        static props = {};
        static template = xml`<a href="#" class="MyComponent" t-on-click="onclick">Some link</a>`;

        /** @param {MouseEvent} ev */
        onclick(ev) {
            expect.step(ev.ctrlKey ? "ctrl-click" : "click");
            // Necessary in order to prevent the test browser to open in new tab on ctrl-click
            ev.preventDefault();
        }
    }

    await mountWithCleanup(MyComponent);

    expect.verifySteps([]);

    await contains(".MyComponent").click();
    await contains(".MyComponent").click({ ctrlKey: true });

    expect.verifySteps(["click", "ctrl-click"]);
});

test.tags("desktop");
test("control-click propagation stopped on <a href/>", async () => {
    expect.assertions(3);

    patchWithCleanup(WebClient.prototype, {
        /** @param {MouseEvent} ev */
        onGlobalClick(ev) {
            super.onGlobalClick(ev);
            if (ev.ctrlKey) {
                expect(ev.defaultPrevented).toBe(false, {
                    message:
                        "the global click should not prevent the default behavior on ctrl-click an <a href/>",
                });
                // Necessary in order to prevent the test browser to open in new tab on ctrl-click
                ev.preventDefault();
            }
        },
    });

    class MyComponent extends Component {
        static props = {};
        static template = xml`<a href="#" class="MyComponent" t-on-click="onclick">Some link</a>`;

        /** @param {MouseEvent} ev */
        onclick(ev) {
            expect.step(ev.ctrlKey ? "ctrl-click" : "click");
            // Necessary in order to prevent the test browser to open in new tab on ctrl-click
            ev.preventDefault();
        }
    }

    await mountWithCleanup(WebClient);

    registry.category("main_components").add("mycomponent", { Component: MyComponent });
    await animationFrame();

    expect.verifySteps([]);

    await contains(".MyComponent").click();
    await contains(".MyComponent").click({ ctrlKey: true });

    expect.verifySteps(["click"]);
});
