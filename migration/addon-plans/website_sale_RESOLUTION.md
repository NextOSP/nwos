# website_sale — Merge Conflict Resolution Plan

Port target: Odoo 19. Decision hinges on OURS (Flectra) vs BASE (Odoo 18), branding neutralized
(`sed 's/\bflectra\b/odoo/g; s/Flectra/Odoo/g'` on OURS) before diffing. THEIRS (Odoo 19) used to
confirm whether OURS-only content is upstream refactor/drift vs a genuine Flectra addition.

## Counts
- Conflicted code files (excl. .po/.pot): **101**
- take-19: **97**
- careful-merge: **4**
- flectra-feature: **0**

## take-19 (97) — adopt Odoo 19 wholesale
After neutralizing branding, OURS is only whitespace/branding/legacy-stale OR an older copy of the
same Odoo code that upstream later refactored (confirmed against THEIRS). Examples:

- models/: ir_http.py, product_attribute.py, product_image.py, product_pricelist.py,
  product_product.py (ribbon_id→variant_ribbon_id upstream), product_public_category.py,
  product_ribbon.py (old html/html_class design → new name/bg_color/position), product_template.py,
  res_config_settings.py (group_product_pricelist / module_website_sale_picking removed upstream),
  res_partner.py, sale_order.py, sale_order_line.py (access_point → pickup_location_data upstream),
  website.py, website_snippet_filter.py
- controllers/: __init__.py, delivery.py, main.py, variant.py (all old monolithic → Odoo 19 split
  into cart/sale/website/payment/reorder/product_configurator; access_point is dropped-upstream drift)
- report/: sale_report.py (identical after neutralization), sale_report_views.xml
- data/: data.xml, demo.xml, mail_template_data.xml, product_snippet_template_data.xml
- views/: product_attribute_views.xml, product_views.xml, res_config_settings_views.xml,
  snippets/s_add_to_cart.xml, snippets/s_dynamic_snippet_products.xml, snippets/snippets.xml,
  templates.xml (large shop table→CSS-grid refactor OURS predates), variant_templates.xml,
  website_pages_views.xml, website_sale_menus.xml, website_sale_visitor_views.xml
  (tree→list renames, branding URLs/colors/labels only)
- static/src/js/: components/website_sale_image_viewer.js, notification/* (add_to_cart_notification
  .js/.xml, cart_notification.js, notification_service.js, warning_notification.js),
  systray_items/new_content.js, tours/tour_utils.js, tours/website_sale_shop.js,
  website_sale_form_editor.js, website_sale_video_field_preview.js
- static/src/scss/: product_configurator.scss (OURS-only = old advanced-configurator-modal removed
  upstream), website_sale.scss, website_sale_delivery.scss, website_sale_frontend.scss,
  snippets/s_dynamic_snippet_products/000.scss
- static/src/xml/website_sale_image_viewer.xml
- tests/ (18): __init__.py, test_customize.py, test_delivery_controller.py, test_delivery_ui.py,
  test_express_checkout_flows.py, test_sale_process.py, test_website_editor.py,
  test_website_sale_cart.py, test_website_sale_cart_abandoned.py, test_website_sale_cart_payment.py,
  test_website_sale_image.py, test_website_sale_mail.py, test_website_sale_pricelist.py,
  test_website_sale_product_attribute_value_config.py, test_website_sale_reorder_from_portal.py,
  test_website_sale_show_compare_list_price.py, test_website_sale_snippets.py,
  test_website_sale_visitor.py (all setUp→setUpClass / fixture-common refactors, no Flectra logic)
- static/tests/tours/ (27): website_free_delivery.js, website_sale_add_to_cart_snippet_tour.js,
  website_sale_buy.js, website_sale_cart_notification.js,
  website_sale_category_page_and_products_snippet.js, website_sale_complete_flow.js,
  website_sale_complete_flow_backend.js, website_sale_fiscal_position_tour.js,
  website_sale_google_analytics.js, website_sale_remove_product_image.js,
  website_sale_reorder_from_portal.js, website_sale_restricted_editor_ui.js,
  website_sale_shop_archived_variant_multi.js, website_sale_shop_cart_recovery.js,
  website_sale_shop_compare_list_price_pricelist.js, website_sale_shop_custom_attribute_value.js,
  website_sale_shop_deleted_archived_variants.js, website_sale_shop_dynamic_variants.js,
  website_sale_shop_editor_tour.js, website_sale_shop_mail.js, website_sale_shop_multi_checkbox.js,
  website_sale_shop_no_variant_attribute.js, website_sale_shop_pricelist_tour.js,
  website_sale_shop_zoom.js, website_sale_snippet_products.js, website_sale_update_address.js,
  website_sale_update_cart.js (all Odoo v17→v18/19 tour-API migration drift)

## careful-merge (4)
- **models/__init__.py** — Preserve `from . import res_country`: OURS ships a Flectra `models/res_country.py`
  (website-sale country/state-by-delivery-carrier filtering) absent from BASE and THEIRS; re-add Odoo 19's new module imports around it.
- **static/src/js/website_sale_utils.js** — Preserve Flectra `forceDialog = html.dataset.add2cartRedirect === '2'`
  (add-to-cart redirect option, absent from BASE/THEIRS) while adopting Odoo 19's `rpc` import change. NOTE: appears currently unused in JS — if confirmed dead everywhere, safe to downgrade to take-19.
- **views/sale_order_views.xml** — Preserve extra record `ir_actions_server_sale_cart_recovery_email`
  ("Send a Cart Recovery Email" action-menu binding on sale.order) absent from BASE/THEIRS; rest is tree→list drift. Decide whether to keep the binding (Odoo 19 exposes recovery only via form button).
- **__manifest__.py** — Coordination point only: content is version-drift (branding URL, Odoo's own
  security/asset/file-list reorg), but hand-reconcile so no Flectra-registered data/asset file (e.g. res_country) is silently dropped while adopting Odoo 19's new entries.

## flectra-feature (0)
None. No standalone Flectra product feature among conflicted files; the Flectra footprint is
branding (names/URLs/colors/labels) plus a few small customizations captured under careful-merge.
