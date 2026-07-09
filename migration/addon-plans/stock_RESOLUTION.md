# stock — Odoo 19 Merge Conflict Resolution Plan

Module: `stock` (Flectra 3.0 → Odoo 19 port)

Trees compared (by relative path):
- OURS   = `/Users/dean/code_env/flectra/addons/stock` (branding neutralized `flectra→odoo`, `Flectra→Odoo` before diffing)
- BASE   = `/Users/dean/code_env/flectra/migration/staging/addons18-base/stock`
- THEIRS = `/Users/dean/code_env/flectra/migration/staging/addons19/stock`

## Counts

| Category | Count |
|---|---|
| Conflicted code files (non-`.po`/`.pot`) | 112 |
| **take-19** | 112 |
| **careful-merge** | 0 |
| **flectra-feature** | 0 |

Every conflicted code file in `stock` can adopt Odoo 19 wholesale. After neutralizing branding, OURS differs from BASE only by branding, whitespace, or version staleness — Flectra's `stock` is an OLDER copy of Odoo with no substantive Flectra-specific content. No file carries a custom field/method/view/behavior that is absent from both Odoo 18 and Odoo 19.

## take-19 (112 files) — adopt Odoo 19

Representative version-drift patterns observed (all "older Odoo, upstream refactored"):
- Python: `type=='product'`/`detailed_type` → `is_storable`; `user_has_groups` → `has_group`; `copy` → `copy_data`; `create_returns` → `action_create_returns`; `ir.property` → `ir.default`; missing new warehouse fields (qc/store/xdock_type_id) and exchange/return-all features.
- JS/OWL: static class fields (`static template`/`static props`); `warehouse` → `warehouse_id`; `props.type` → `props.mode`; router → URL params; `@flectra-module` → `@odoo-module`; old jQuery tour API.
- XML views/reports: `tree` → `list`; `kanban-box` → `card`; `oe_chatter` → `<chatter/>`; `group_stock_storage_categories` → `group_stock_multi_locations`; `priority` → `is_favorite`; `table-sm` → `table-borderless`; `/web#action=` → `/odoo/action-`.
- Manifest: Flectra references old removed wizards (`stock_assign_serial_views.xml`, `stock_scheduler_compute_views.xml`); asset globs older than 19.

Two of the 112 (`wizard/product_label_layout.py`, `controllers/main.py`) are byte-identical to BASE after branding neutralization (pure branding).

Full list (all take-19):

### models/
- models/__init__.py
- models/product.py
- models/product_strategy.py
- models/res_company.py
- models/res_config_settings.py
- models/res_partner.py
- models/stock_location.py
- models/stock_lot.py
- models/stock_move.py
- models/stock_move_line.py
- models/stock_orderpoint.py
- models/stock_package_type.py
- models/stock_picking.py
- models/stock_quant.py
- models/stock_rule.py
- models/stock_scrap.py
- models/stock_storage_category.py
- models/stock_warehouse.py

### wizard/
- wizard/product_label_layout.py
- wizard/product_label_layout_views.xml
- wizard/product_replenish.py
- wizard/stock_package_destination.py
- wizard/stock_picking_return.py
- wizard/stock_picking_return_views.xml
- wizard/stock_quant_relocate.py
- wizard/stock_quantity_history.py
- wizard/stock_replenishment_info.py
- wizard/stock_request_count.py

### views/
- views/product_views.xml
- views/res_config_settings_views.xml
- views/res_partner_views.xml
- views/stock_location_views.xml
- views/stock_lot_views.xml
- views/stock_move_line_views.xml
- views/stock_move_views.xml
- views/stock_orderpoint_views.xml
- views/stock_package_type_view.xml
- views/stock_picking_views.xml
- views/stock_quant_views.xml
- views/stock_rule_views.xml
- views/stock_scrap_views.xml
- views/stock_storage_category_views.xml

### report/
- report/report_deliveryslip.xml
- report/report_package_barcode.xml
- report/report_stock_quantity.py
- report/report_stockinventory.xml
- report/report_stockpicking_operations.xml
- report/stock_forecasted.py
- report/stock_report_views.xml

### data/
- data/stock_data.xml  (note: Odoo renamed record id `stock_location_inter_wh`→`stock_location_inter_company`; verify no Flectra code references the old id)
- data/stock_demo_pre.xml

### security/
- security/ir.model.access.csv

### controllers/
- controllers/main.py

### static/src/
- static/src/client_actions/multi_print.js
- static/src/client_actions/stock_traceability_report_backend.js
- static/src/client_actions/stock_traceability_report_backend.xml
- static/src/components/reception_report_line/stock_reception_report_line.js
- static/src/components/reception_report_main/stock_reception_report_main.js
- static/src/components/reception_report_table/stock_reception_report_table.js
- static/src/fields/stock_move_line_x2_many_field.js
- static/src/stock_forecasted/forecasted_buttons.js
- static/src/stock_forecasted/forecasted_details.js
- static/src/stock_forecasted/forecasted_details.xml
- static/src/stock_forecasted/forecasted_graph.js
- static/src/stock_forecasted/forecasted_header.js
- static/src/stock_forecasted/forecasted_warehouse_filter.js
- static/src/stock_forecasted/stock_forecasted.js
- static/src/stock_forecasted/stock_forecasted.xml
- static/src/stock_warehouse_service.js
- static/src/views/list/inventory_report_list_model.js
- static/src/views/list/inventory_report_list_view.js
- static/src/views/list/stock_report_list_view.js
- static/src/views/picking_form/stock_move_one2many.js
- static/src/views/search/stock_report_search_model.js
- static/src/views/search/stock_report_search_panel.js
- static/src/views/stock_orderpoint_list_controller.js
- static/src/views/stock_orderpoint_list_view.js
- static/src/widgets/counted_quantity_widget.js
- static/src/widgets/forecast_widget.js
- static/src/widgets/forecast_widget.xml
- static/src/widgets/generate_serial.js
- static/src/widgets/json_widget.js
- static/src/widgets/json_widget.xml
- static/src/widgets/lots_dialog.xml
- static/src/widgets/popover_widget.js
- static/src/widgets/stock_pick_from.js
- static/src/widgets/stock_rescheduling_popover.js

### static/tests/
- static/tests/tours/stock_picking_tour.js
- static/tests/tours/stock_report_tests.js

### tests/
- tests/common.py
- tests/test_generate_serial_numbers.py
- tests/test_immediate.py
- tests/test_inventory.py
- tests/test_move.py
- tests/test_move2.py
- tests/test_move_lines.py
- tests/test_packing.py
- tests/test_packing_neg.py
- tests/test_picking_tours.py
- tests/test_proc_rule.py
- tests/test_product.py
- tests/test_quant.py
- tests/test_quant_inventory_mode.py
- tests/test_report.py
- tests/test_report_stock_quantity.py
- tests/test_report_tours.py
- tests/test_robustness.py
- tests/test_stock_flow.py
- tests/test_stock_lot.py
- tests/test_stock_return_picking.py
- tests/test_warehouse.py

### top-level
- __manifest__.py

## careful-merge (0 files)

None.

## flectra-feature (0 files)

None.
