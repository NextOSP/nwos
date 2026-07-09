import { Component, onMounted, useState } from "@nwos/owl";

export class LoadingOverlay extends Component {
    static template = "pos_self_order.LoadingOverlay";
    static props = {};

    setup() {
        this.state = useState({
            loading: false,
        });

        onMounted(() => {
            setTimeout(() => {
                this.state.loading = true;
            }, 200);
        });
    }
}
