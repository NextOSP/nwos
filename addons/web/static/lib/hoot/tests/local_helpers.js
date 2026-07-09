/** @nwos-module */

import { after, destroy, getFixture } from "@nwos/hoot";
import { App, Component, xml } from "@nwos/owl";

//-----------------------------------------------------------------------------
// Exports
//-----------------------------------------------------------------------------

/**
 * @param {import("@nwos/owl").ComponentConstructor} ComponentClass
 * @param {ConstructorParameters<typeof App>[1]} [config]
 */
export async function mountForTest(ComponentClass, config) {
    if (typeof ComponentClass === "string") {
        ComponentClass = class extends Component {
            static name = "anonymous component";
            static props = {};
            static template = xml`${ComponentClass}`;
        };
    }

    const app = new App(ComponentClass, {
        name: "TEST",
        test: true,
        warnIfNoStaticProps: true,
        ...config,
    });
    const fixture = getFixture();

    after(() => destroy(app));

    fixture.style.backgroundColor = "#fff";
    await app.mount(fixture);
    if (fixture.hasIframes) {
        await fixture.waitForIframes();
    }
}

/**
 * @param {string} url
 */
export function parseUrl(url) {
    return url.replace(/^.*hoot\/tests/, "@hoot").replace(/(\.test)?\.js$/, "");
}
