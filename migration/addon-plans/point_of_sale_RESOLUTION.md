# point_of_sale — Merge Conflict Resolution Plan

Port target: Odoo 19. Decision method: diff OURS (branding-neutralized `flectra`→`odoo`) vs BASE (Odoo 18); judge remaining substantive differences.

## Counts
- Conflicted code files (excl. .po/.pot): **103**
- **take-19: 101**
- **careful-merge: 2**
- **flectra-feature: 0**

## Overall finding
OURS is an older Odoo POS fork. Almost every conflict is pure version drift: Odoo renamed/rearchitected APIs between OURS' base and Odoo 18/19 (e.g. `create_from_ui`→`sync_from_ui`, `load_pos_data`→`load_data`, `uid`→`uuid`, `pos.combo`/`pos.combo.line`→`product.combo`/`product.combo.item`, `type:'product'`→`is_storable`, `price_include`→`price_include_override`, popup service→dialog, `tree`→`list` views, `<oe_chatter>`→`<chatter/>`, `pos.load.mixin`/`pos.data` data layer, QR payment methods). None of that is Flectra business logic — adopt Odoo 19 wholesale.

## take-19 (101 files) — adopt Odoo 19
All files below. OURS differs only by whitespace/legacy staleness or is an older copy of the same Odoo code (vendored lib `static/src/app/utils/html-to-image.js` always take-19).

Examples: `models/pos_order.py`, `models/pos_session.py` (drop OURS' Odoo-17-era "capture unprocessed order" `PoSOrderData`/`_capture_order_data` system, removed in 19), `models/pos_payment_method.py`, `report/pos_order_report.py`, all 15 `views/*.xml`, all 20 static JS/TS files, all 28 static xml/scss/css files, all 21 tests + root files (`__manifest__.py`, `controllers/main.py`, `data/point_of_sale_data.xml`, `security/*`).

Full list by area:
- models (16): `__init__.py`, `account_fiscal_position.py`, `account_journal.py`, `account_move.py`, `account_tax.py`, `digest.py`, `pos_bill.py`, `pos_category.py`, `pos_order.py`, `pos_payment.py`, `pos_payment_method.py`, `pos_printer.py`, `pos_session.py`, `report_sale_details.py`, `res_company.py`, `res_partner.py`, `stock_picking.py`
- root/tests (21): `__manifest__.py`, `controllers/main.py`, `data/point_of_sale_data.xml`, `report/pos_order_report.py`, `security/ir.model.access.csv`, `security/point_of_sale_security.xml`, `tests/__init__.py`, `tests/common.py`, `tests/common_setup_methods.py`, `tests/test_anglo_saxon.py`, `tests/test_frontend.py`, `tests/test_point_of_sale.py`, `tests/test_point_of_sale_flow.py`, `tests/test_pos_basic_config.py`, `tests/test_pos_controller.py`, `tests/test_pos_other_currency_config.py`, `tests/test_pos_products_with_tax.py`, `tests/test_pos_setup.py`, `tests/test_pos_stock_account.py`, `tests/test_report_session.py`, `tests/test_res_config_settings.py`
- views (15): `point_of_sale_dashboard.xml`, `pos_assets_index.xml`, `pos_bill_view.xml`, `pos_config_view.xml`, `pos_order_report_view.xml`, `pos_order_view.xml`, `pos_payment_method_views.xml`, `pos_payment_views.xml`, `pos_printer_view.xml`, `pos_session_view.xml`, `product_view.xml`, `report_invoice.xml`, `report_saledetails.xml`, `res_config_settings_views.xml`, `res_partner_view.xml`
- static JS/TS (20): `@types/services.d.ts`, `app/main.js`, `app/pos_app.js`, `app/screens/partner_list/partner_line/partner_line.js`, `app/screens/partner_list/partner_list.js`, `app/screens/payment_screen/payment_lines/payment_lines.js`, `app/screens/payment_screen/payment_screen.js`, `app/screens/payment_screen/payment_status/payment_status.js`, `app/screens/product_screen/action_pad/action_pad.js`, `app/screens/product_screen/product_screen.js`, `app/screens/receipt_screen/receipt_screen.js`, `app/screens/receipt_screen/receipt/order_receipt.js`, `app/screens/receipt_screen/receipt/receipt_header/receipt_header.js`, `app/screens/scale_screen/scale_screen.js`, `app/screens/ticket_screen/invoice_button/invoice_button.js`, `app/screens/ticket_screen/search_bar/search_bar.js`, `app/screens/ticket_screen/ticket_screen.js`, `app/utils/html-to-image.js` (vendored lib), `backend/tours/point_of_sale.js`, `utils.js`
- static xml/scss/css (28): `app/pos_app.scss`, `app/pos_app.xml`, `app/screens/partner_list/partner_line/partner_line.scss`, `app/screens/partner_list/partner_line/partner_line.xml`, `app/screens/partner_list/partner_list.scss`, `app/screens/partner_list/partner_list.xml`, `app/screens/payment_screen/payment_lines/payment_lines.xml`, `app/screens/payment_screen/payment_screen.scss`, `app/screens/payment_screen/payment_screen.xml`, `app/screens/payment_screen/payment_status/payment_status.xml`, `app/screens/product_screen/action_pad/action_pad.xml`, `app/screens/product_screen/control_buttons/control_buttons.scss`, `app/screens/product_screen/product_screen.scss`, `app/screens/product_screen/product_screen.xml`, `app/screens/receipt_screen/receipt_screen.scss`, `app/screens/receipt_screen/receipt_screen.xml`, `app/screens/receipt_screen/receipt/order_receipt.xml`, `app/screens/receipt_screen/receipt/receipt_header/receipt_header.xml`, `app/screens/scale_screen/scale_screen.xml`, `app/screens/ticket_screen/invoice_button/invoice_button.xml`, `app/screens/ticket_screen/search_bar/search_bar.xml`, `app/screens/ticket_screen/ticket_screen.scss`, `app/screens/ticket_screen/ticket_screen.xml`, `app/store/order_change_receipt_template.xml`, `css/pos_receipts.css`, `scss/pos.scss`, `scss/pos_dashboard.scss`, `scss/pos_variables_extra.scss`

## careful-merge (2 files)
- `models/pos_config.py` — Preserve the `start_category` Boolean field (+ related `iface_start_categ_id` "Initial Category" logic and `_check_start_categ` constraint): a Flectra toggle that gates the auto-selected opening product category. Absent from BASE and Odoo 19; wired into `static/src/app/store/pos_store.js` (`selectedCategoryId`). Everything else in the file is Odoo version drift → take Odoo 19 and re-apply only this field.
- `models/res_config_settings.py` — Preserve the mirror `pos_start_category` (related to `pos_config_id.start_category`) field and its `@api.depends('pos_start_category', ...)` onchange that clears the initial category when the toggle is off. Rest is version drift → take Odoo 19 and re-apply this field only.

## flectra-feature (0 files)
None. No standalone Flectra product feature files among the conflicts.
