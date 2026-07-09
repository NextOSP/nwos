import { Component } from "@nwos/owl";

export class BackButton extends Component {
    static template = "point_of_sale.BackButton";
    static props = {
        onClick: { type: Function },
        class: { type: Object, optional: true },
    };
}
