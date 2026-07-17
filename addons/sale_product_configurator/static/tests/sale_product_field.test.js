import { expect, test } from "@nwos/hoot";
import { press, runAllTimers } from "@nwos/hoot-dom";
import { saleModels } from "@sale/../tests/sale_test_helpers";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";

class SaleOrderLine extends saleModels.SaleOrderLine {
    product_template_attribute_value_ids = fields.Many2many({
        string: "Product template attributes values",
        relation: "product.template.attribute.value",
    });
}

class ProductTemplateAttributeValue extends models.Model {
    _name = "product.template.attribute.value";

    name = fields.Char();
}

defineModels({ ...saleModels, SaleOrderLine, ProductTemplateAttributeValue });

test.tags("desktop");
test("selecting a product template makes one variant RPC with a valid id", async () => {
    const variantCallArgs = [];
    onRpc("product.template", "get_single_product_variant", ({ args, parent }) => {
        variantCallArgs.push(args);
        return parent();
    });

    await mountView({
        type: "form",
        resModel: "sale.order",
        arch: /* xml */ `
            <form>
                <sheet>
                    <field name="order_line">
                        <list editable="bottom">
                            <field name="product_template_id" widget="sol_product_many2one"/>
                            <field name="product_id" optional="hide"/>
                            <field name="name" optional="show"/>
                        </list>
                    </field>
                </sheet>
            </form>`,
    });

    await contains(".o_field_x2many_list .o_field_x2many_list_row_add a").click();
    await contains("[name='product_template_id'] input").edit("new product");
    await press("tab");
    await runAllTimers();

    expect(variantCallArgs).toHaveLength(1);
    expect(variantCallArgs[0]).toHaveLength(1);
    expect(Number.isInteger(variantCallArgs[0][0]) && variantCallArgs[0][0] > 0).toBe(true);
});
