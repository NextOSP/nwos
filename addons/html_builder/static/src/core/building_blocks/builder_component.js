import { Component, xml } from "@nwos/owl";
import { useDomState } from "../utils";

export class BuilderComponent extends Component {
    static template = xml`<t t-if="this.state.isVisible"><t t-slot="default"/></t>`;
    static props = {
        slots: { type: Object },
    };

    setup() {
        this.state = useDomState(
            (editingElement) => ({
                isVisible: !!editingElement,
            }),
            { checkEditingElement: false }
        );
    }
}
