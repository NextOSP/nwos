// @nwos-module ignore
// ! WARNING: this module must be loaded after `module_loader` but cannot have dependencies !

(function (nwos) {
    "use strict";

    if (nwos.define.name.endsWith("(hoot)")) {
        return;
    }

    const name = `${nwos.define.name} (hoot)`;
    nwos.define = {
        [name](name, dependencies, factory) {
            return nwos.loader.define(name, dependencies, factory, !name.endsWith(".hoot"));
        },
    }[name];
})(globalThis.nwos);
