import { Component } from "@nwos/owl";

export class NWOSLogo extends Component {
    static template = "point_of_sale.NWOSLogo";
    static props = {
        class: { type: String, optional: true },
        style: { type: String, optional: true },
        monochrome: { type: Boolean, optional: true },
    };
    static defaultProps = {
        class: "",
        style: "",
        monochrome: false,
    };
}
