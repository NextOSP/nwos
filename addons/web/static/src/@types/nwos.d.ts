interface NWOSModuleErrors {
    cycle?: string | null;
    failed?: Set<string>;
    missing?: Set<string>;
    unloaded?: Set<string>;
}

interface NWOSModuleFactory {
    deps: string[];
    fn: NWOSModuleFactoryFn;
    ignoreMissingDeps: boolean;
}

class NWOSModuleLoader {
    bus: EventTarget;
    checkErrorProm: Promise<void> | null;
    debug: boolean;
    /**
     * Mapping [name => factory]
     */
    factories: Map<string, NWOSModuleFactory>;
    /**
     * Names of failed modules
     */
    failed: Set<string>;
    /**
     * Names of modules waiting to be started
     */
    jobs: Set<string>;
    /**
     * Mapping [name => module]
     */
    modules: Map<string, NWOSModule>;

    constructor(root?: HTMLElement);

    addJob: (name: string) => void;

    define: (
        name: string,
        deps: string[],
        factory: NWOSModuleFactoryFn,
        lazy?: boolean
    ) => NWOSModule;

    findErrors: (jobs?: Iterable<string>) => NWOSModuleErrors;

    findJob: () => string | null;

    reportErrors: (errors: NWOSModuleErrors) => Promise<void>;

    sortFactories: () => void;

    startModule: (name: string) => NWOSModule;

    startModules: () => void;
}

type NWOSModule = Record<string, any>;

type NWOSModuleFactoryFn = (require: (dependency: string) => NWOSModule) => NWOSModule;

declare const nwos: {
    csrf_token: string;
    debug: string;
    define: NWOSModuleLoader["define"];
    loader: NWOSModuleLoader;
};
