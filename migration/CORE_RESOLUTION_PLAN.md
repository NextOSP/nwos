# CORE Package Merge-Conflict Resolution Plan (Flectra -> Odoo 19)

Scope: the ~196 conflicted CODE files (excluding .po/.pot) from the 3-way merge in
`migration/staging/flectra-merged/`. Each was classified by diffing OURS (current Flectra core)
against BASE (Odoo 18.0 fork base) with branding neutralized (flectra/Flectra -> odoo/Odoo) and
whitespace ignored, then judging the remaining differences. THEIRS (Odoo 19.0) is the merge target.

## Summary counts
- take-19 (bulk-resolvable): 190
- careful-merge: 5
- flectra-feature: 1
- TOTAL: 196

Key finding: Flectra core sits on a PRE-18 Odoo snapshot, so for the overwhelming majority of files
OURS is simply an OLDER copy of the same Odoo code (list/tree tag rename, check_access_rights vs
check_access, _check_recursion vs _has_cycle, name_search/_search old signatures, %/.format vs f-strings/SQL(),
ustr/pycompat/from __future__, missing newer Odoo-18 fields) plus pure branding tokens (flectrahq.com,
<flectra> XML roots, @flectra-module). None of that carries functional value -> take Odoo 19 wholesale
(re-applying branding afterward). Genuine Flectra divergence is confined to 6 files below.

## CAREFUL-MERGE (preserve Flectra logic; sorted biggest/most-substantive first)

- `addons/base/models/res_config.py` — Flectra RETAINS the legacy `res.config.installer` TransientModel (full class: modules_to_install / already_installed / execute hook logic) that Odoo 18/19 deleted; dropping it breaks any addon subclassing it. (Also minor str2bool->bool cast.)
- `addons/base/security/ir.model.access.csv` — adds ACL rows for the legacy models Flectra keeps: `model_ir_property` (group_user + group_system) and `model_res_config_installer`; must stay in sync with the retained models.
- `tools/config.py` — Flectra default ports (http `7073`, gevent/longpolling `7072` vs Odoo 8069/8072), retained deprecated `longpolling-port` alias + `_warn_deprecated_options` handling, and `set_admin_password` crypt_context backward-compat.
- `addons/base/__manifest__.py` — data list still loads `views/ir_property_views.xml` for the retained legacy `ir.property` model (Odoo 18/19 dropped it); remainder of the data-file divergence is version staleness.
- `tools/pdf/__init__.py` — loops page `/Annots` to force filled PDF form text fields to read-only (sets `/Ff` readonly bit); behavior absent from both Odoo 18 and 19. (Verify vs Odoo-19 PDF handling; may be old-Odoo behavior since removed.)

## FLECTRA-FEATURE

- `release.py` — Flectra product identity constants that must NOT be overwritten by Odoo 19: `version_info=(3,0,0,...)`, `url=https://flectrahq.com`, author string, `nt_service_name="flectra-server-"`, series/description. Preserve Flectra identity on top of any Odoo-19 structural changes.

## TAKE-19 (bulk-resolvable — adopt Odoo 19, re-apply branding) — 190 files

- `addons/base/data/res.country.state.csv`
- `addons/base/data/res.lang.csv`
- `addons/base/data/res_partner_demo.xml`
- `addons/base/data/res_users_data.xml`
- `addons/base/models/assetsbundle.py`
- `addons/base/models/decimal_precision.py`
- `addons/base/models/ir_actions.py`
- `addons/base/models/ir_actions_report.py`
- `addons/base/models/ir_attachment.py`
- `addons/base/models/ir_autovacuum.py`
- `addons/base/models/ir_binary.py`
- `addons/base/models/ir_config_parameter.py`
- `addons/base/models/ir_cron.py`
- `addons/base/models/ir_default.py`
- `addons/base/models/ir_demo.py`
- `addons/base/models/ir_fields.py`
- `addons/base/models/ir_filters.py`
- `addons/base/models/ir_http.py`
- `addons/base/models/ir_mail_server.py`
- `addons/base/models/ir_model.py`
- `addons/base/models/ir_module.py`
- `addons/base/models/ir_profile.py`
- `addons/base/models/ir_qweb.py`
- `addons/base/models/ir_qweb_fields.py`
- `addons/base/models/ir_rule.py`
- `addons/base/models/ir_sequence.py`
- `addons/base/models/ir_ui_menu.py`
- `addons/base/models/ir_ui_view.py`
- `addons/base/models/report_paperformat.py`
- `addons/base/models/res_bank.py`
- `addons/base/models/res_company.py`
- `addons/base/models/res_country.py`
- `addons/base/models/res_currency.py`
- `addons/base/models/res_lang.py`
- `addons/base/models/res_partner.py`
- `addons/base/models/res_users.py`
- `addons/base/models/res_users_deletion.py`
- `addons/base/models/res_users_settings.py`
- `addons/base/rng/calendar_view.rng`
- `addons/base/security/base_groups.xml`
- `addons/base/security/base_security.xml`
- `addons/base/static/tests/test_ir_model_fields_translation.js`
- `addons/base/tests/common.py`
- `addons/base/tests/test_acl.py`
- `addons/base/tests/test_api.py`
- `addons/base/tests/test_date_utils.py`
- `addons/base/tests/test_db_cursor.py`
- `addons/base/tests/test_expression.py`
- `addons/base/tests/test_form_create.py`
- `addons/base/tests/test_http_case.py`
- `addons/base/tests/test_ir_actions.py`
- `addons/base/tests/test_ir_attachment.py`
- `addons/base/tests/test_ir_cron.py`
- `addons/base/tests/test_ir_filters.py`
- `addons/base/tests/test_ir_mail_server_smtpd.py`
- `addons/base/tests/test_ir_model.py`
- `addons/base/tests/test_ir_sequence.py`
- `addons/base/tests/test_mail.py`
- `addons/base/tests/test_misc.py`
- `addons/base/tests/test_module.py`
- `addons/base/tests/test_orm.py`
- `addons/base/tests/test_ormcache.py`
- `addons/base/tests/test_qweb.py`
- `addons/base/tests/test_res_company.py`
- `addons/base/tests/test_res_partner.py`
- `addons/base/tests/test_res_users.py`
- `addons/base/tests/test_search.py`
- `addons/base/tests/test_sql.py`
- `addons/base/tests/test_test_retry.py`
- `addons/base/tests/test_test_suite.py`
- `addons/base/tests/test_tests_tags.py`
- `addons/base/tests/test_translate.py`
- `addons/base/tests/test_uninstall.py`
- `addons/base/tests/test_user_has_group.py`
- `addons/base/tests/test_views.py`
- `addons/base/views/ir_actions_views.xml`
- `addons/base/views/ir_config_parameter_views.xml`
- `addons/base/views/ir_cron_views.xml`
- `addons/base/views/ir_model_views.xml`
- `addons/base/views/ir_module_views.xml`
- `addons/base/views/ir_profile_views.xml`
- `addons/base/views/res_bank_views.xml`
- `addons/base/views/res_country_views.xml`
- `addons/base/views/res_currency_views.xml`
- `addons/base/views/res_partner_views.xml`
- `addons/base/views/res_users_identitycheck_views.xml`
- `addons/base/views/res_users_views.xml`
- `addons/base/wizard/base_export_language.py`
- `addons/base/wizard/base_export_language_views.xml`
- `addons/base/wizard/base_import_language.py`
- `addons/base/wizard/base_language_install.py`
- `addons/base/wizard/base_module_upgrade.py`
- `addons/base/wizard/base_partner_merge.py`
- `addons/test_access_rights/tests/test_feedback.py`
- `addons/test_access_rights/tests/test_ir_rules.py`
- `addons/test_assetsbundle/__manifest__.py`
- `addons/test_assetsbundle/static/tests/lazy_test_component/lazy_test_component.js`
- `addons/test_assetsbundle/static/tests/test_css_error.js`
- `addons/test_assetsbundle/tests/test_assetsbundle.py`
- `addons/test_assetsbundle/tests/test_js_transpiler.py`
- `addons/test_assetsbundle/tests/test_js_transpiler_regex.py`
- `addons/test_converter/models.py`
- `addons/test_http/__manifest__.py`
- `addons/test_http/controllers.py`
- `addons/test_http/tests/__init__.py`
- `addons/test_http/tests/test_greeting.py`
- `addons/test_http/tests/test_models.py`
- `addons/test_http/tests/test_session.py`
- `addons/test_http/tests/test_static.py`
- `addons/test_http/utils.py`
- `addons/test_lint/__init__.py`
- `addons/test_lint/tests/__init__.py`
- `addons/test_lint/tests/eslintrc`
- `addons/test_lint/tests/lint_case.py`
- `addons/test_lint/tests/test_checkers.py`
- `addons/test_lint/tests/test_dunderinit.py`
- `addons/test_lint/tests/test_manifests.py`
- `addons/test_lint/tests/test_markers.py`
- `addons/test_lint/tests/test_override_signatures.py`
- `addons/test_lint/tests/test_pylint.py`
- `addons/test_main_flows/static/tests/tours/main_flow.js`
- `addons/test_main_flows/static/tests/tours/switch_company_access_error_tour.js`
- `addons/test_main_flows/tests/test_flow.py`
- `addons/test_mimetypes/tests/test_guess_mimetypes.py`
- `addons/test_read_group/ir.model.access.csv`
- `addons/test_read_group/models.py`
- `addons/test_read_group/tests/__init__.py`
- `addons/test_read_group/tests/test_private_read_group.py`
- `addons/test_rpc/models.py`
- `addons/test_rpc/tests/test_error.py`
- `addons/test_translation_import/tests/test_term_count.py`
- `cli/__init__.py`
- `cli/cloc.py`
- `cli/command.py`
- `cli/db.py`
- `cli/deploy.py`
- `cli/neutralize.py`
- `cli/obfuscate.py`
- `cli/populate.py`
- `cli/scaffold.py`
- `cli/server.py`
- `cli/shell.py`
- `cli/start.py`
- `cli/templates/default/controllers/controllers.py.template`
- `cli/templates/default/models/models.py.template`
- `exceptions.py`
- `http.py`
- `modules/__init__.py`
- `modules/db.py`
- `modules/loading.py`
- `modules/migration.py`
- `modules/module.py`
- `modules/neutralize.py`
- `netsvc.py`
- `osv/__init__.py`
- `osv/expression.py`
- `service/common.py`
- `service/db.py`
- `service/model.py`
- `service/security.py`
- `service/server.py`
- `sql_db.py`
- `tests/common.py`
- `tests/form.py`
- `tests/loader.py`
- `tests/test_module_operations.py`
- `tools/__init__.py`
- `tools/barcode.py`
- `tools/cache.py`
- `tools/cloc.py`
- `tools/constants.py`
- `tools/convert.py`
- `tools/date_utils.py`
- `tools/float_utils.py`
- `tools/func.py`
- `tools/js_transpiler.py`
- `tools/json.py`
- `tools/lru.py`
- `tools/mail.py`
- `tools/mimetypes.py`
- `tools/misc.py`
- `tools/osutil.py`
- `tools/populate.py`
- `tools/profiler.py`
- `tools/pycompat.py`
- `tools/query.py`
- `tools/safe_eval.py`
- `tools/sql.py`
- `tools/translate.py`
- `tools/xml_utils.py`
