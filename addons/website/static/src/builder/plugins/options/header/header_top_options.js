import { Component } from "@nwos/owl";

export class HeaderTopOptions extends Component {
    static template = "website.HeaderTopOptions";
    static props = {
        openEditMenu: Function,
    };
}
