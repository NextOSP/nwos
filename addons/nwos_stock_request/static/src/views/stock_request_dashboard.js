import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUpdateProps } from "@nwos/owl";

export class StockRequestDashboard extends Component {
    static template = "nwos_stock_request.Dashboard";
    static props = { list: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        onWillStart(async () => {
            await this.updateDashboard();
        });
        onWillUpdateProps(async () => {
            await this.updateDashboard();
        });
    }

    async updateDashboard() {
        this.data = await this.orm.call("stock.request", "retrieve_dashboard");
        this.multiuser =
            JSON.stringify(this.data.global) !== JSON.stringify(this.data.my);
    }

    /** Clear the current search and activate the filters named on the card. */
    setSearchContext(ev) {
        const filterNames = ev.currentTarget.getAttribute("filter_name").split(",");
        const items = this.env.searchModel.getSearchItems((item) =>
            filterNames.includes(item.name)
        );
        this.env.searchModel.query = [];
        for (const item of items) {
            this.env.searchModel.toggleSearchItem(item.id);
        }
    }
}
