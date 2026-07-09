# Flectra Core vs. Renamed Odoo-19 Core — Structural Diff Report

Comparison base paths (by relative path):

- Current Flectra core: `/Users/dean/code_env/flectra/flectra/`
- Staged renamed Odoo-19 core: `/Users/dean/code_env/flectra/migration/staging/flectra/`

Rename tool: `/Users/dean/code_env/flectra/migration/odoo_to_flectra_rename.py` (1202 files copied, 442 modified; idempotent).

## Headline counts

- Files ONLY in current Flectra core: **138**
- Files ONLY in staged Odoo-19 core: **227**
- Files in BOTH but differing: **521**
- Files identical in both: (of 975 common files, 454 identical)

## 1. Files ONLY in current Flectra core (carry-forward customizations)

Total: 138. By top-level path:
- `addons`: 117
- `tools`: 6
- `cli`: 3
- `modules`: 2
- `tests`: 2
- `__init__.py`: 1
- `api.py`: 1
- `conf`: 1
- `fields.py`: 1
- `models.py`: 1
- `osv`: 1
- `service`: 1
- `upgrade`: 1

Full list (cap 200):

- `__init__.py`
- `addons/__init__.py`
- `addons/base/controllers/__init__.py`
- `addons/base/controllers/rpc.py`
- `addons/base/i18n/hy.po`
- `addons/base/i18n/sr.po`
- `addons/base/models/ir_property.py`
- `addons/base/populate/__init__.py`
- `addons/base/populate/ir_filters.py`
- `addons/base/populate/res_company.py`
- `addons/base/populate/res_currency.py`
- `addons/base/populate/res_partner.py`
- `addons/base/populate/res_user.py`
- `addons/base/report/corporate_defaults.xml`
- `addons/base/report/corporate_odt_header.xml`
- `addons/base/report/corporate_sxw_header.xml`
- `addons/base/report/custom_report.xml`
- `addons/base/report/custom_view.xml`
- `addons/base/rng/tree_view.rng`
- `addons/base/static/img/bg_background_template.jpg`
- `addons/base/static/img/icons/website_twitter_wall.png`
- `addons/base/static/img/onboarding_bank-account.png`
- `addons/base/static/xls/res_partner.xlsx`
- `addons/base/tests/flectra.jpg`
- `addons/base/tests/test_mail_examples.py`
- `addons/base/tests/test_osv.py`
- `addons/base/tests/test_xmlrpc.py`
- `addons/base/views/ir_property_views.xml`
- `addons/test_apikeys/__init__.py`
- `addons/test_apikeys/__manifest__.py`
- `addons/test_apikeys/static/tests/apikey_flow.js`
- `addons/test_apikeys/tests/__init__.py`
- `addons/test_apikeys/tests/test_flow.py`
- `addons/test_assetsbundle/static/tests/lazyloading_test.js`
- `addons/test_converter/tests/test_gbf.py`
- `addons/test_exceptions/__init__.py`
- `addons/test_exceptions/__manifest__.py`
- `addons/test_exceptions/ir.model.access.csv`
- `addons/test_exceptions/models.py`
- `addons/test_exceptions/static/description/icon.png`
- `addons/test_exceptions/static/description/icon.svg`
- `addons/test_exceptions/view.xml`
- `addons/test_impex/__init__.py`
- `addons/test_impex/__manifest__.py`
- `addons/test_impex/ir.model.access.csv`
- `addons/test_impex/models.py`
- `addons/test_impex/tests/__init__.py`
- `addons/test_impex/tests/contacts.json`
- `addons/test_impex/tests/contacts_big.json`
- `addons/test_impex/tests/test_export.py`
- `addons/test_impex/tests/test_load.py`
- `addons/test_inherit/models.py`
- `addons/test_limits/__init__.py`
- `addons/test_limits/__manifest__.py`
- `addons/test_limits/ir.model.access.csv`
- `addons/test_limits/models.py`
- `addons/test_lint/tests/_flectra_checker_gettext.py`
- `addons/test_lint/tests/_flectra_checker_sql_injection.py`
- `addons/test_lint/tests/_flectra_checker_unlink_override.py`
- `addons/test_new_api/__init__.py`
- `addons/test_new_api/__manifest__.py`
- `addons/test_new_api/data/test_new_api_data.xml`
- `addons/test_new_api/i18n/fr.po`
- `addons/test_new_api/i18n/test_new_api.pot`
- `addons/test_new_api/models/__init__.py`
- `addons/test_new_api/models/test_new_api.py`
- `addons/test_new_api/models/test_unity_read.py`
- `addons/test_new_api/security/ir.model.access.csv`
- `addons/test_new_api/security/test_new_api_security.xml`
- `addons/test_new_api/static/tests/tours/constraint.js`
- `addons/test_new_api/static/tests/tours/x2many.js`
- `addons/test_new_api/tests/__init__.py`
- `addons/test_new_api/tests/test_attributes.py`
- `addons/test_new_api/tests/test_autovacuum.py`
- `addons/test_new_api/tests/test_company_checks.py`
- `addons/test_new_api/tests/test_domain.py`
- `addons/test_new_api/tests/test_indexed_translation.py`
- `addons/test_new_api/tests/test_json_field.py`
- `addons/test_new_api/tests/test_many2many.py`
- `addons/test_new_api/tests/test_new_fields.py`
- `addons/test_new_api/tests/test_onchange.py`
- `addons/test_new_api/tests/test_one2many.py`
- `addons/test_new_api/tests/test_properties.py`
- `addons/test_new_api/tests/test_qweb_float.py`
- `addons/test_new_api/tests/test_related_translation.py`
- `addons/test_new_api/tests/test_schema.py`
- `addons/test_new_api/tests/test_ui.py`
- `addons/test_new_api/tests/test_unity_read.py`
- `addons/test_new_api/tests/test_views.py`
- `addons/test_new_api/tests/test_web_read_group.py`
- `addons/test_new_api/tests/test_web_save.py`
- `addons/test_new_api/views/test_new_api_views.xml`
- `addons/test_performance/__init__.py`
- `addons/test_performance/__manifest__.py`
- `addons/test_performance/models/__init__.py`
- `addons/test_performance/models/models.py`
- `addons/test_performance/security/ir.model.access.csv`
- `addons/test_performance/tests/__init__.py`
- `addons/test_performance/tests/test_performance.py`
- `addons/test_populate/__init__.py`
- `addons/test_populate/__manifest__.py`
- `addons/test_populate/ir.model.access.csv`
- `addons/test_populate/models.py`
- `addons/test_populate/tests/__init__.py`
- `addons/test_populate/tests/test_populate.py`
- `addons/test_read_group/tests/test_auto_join.py`
- `addons/test_read_group/tests/test_date_range.py`
- `addons/test_read_group/tests/test_empty.py`
- `addons/test_read_group/tests/test_exceptions.py`
- `addons/test_read_group/tests/test_fill_temporal.py`
- `addons/test_read_group/tests/test_group_expand.py`
- `addons/test_read_group/tests/test_group_operator.py`
- `addons/test_read_group/tests/test_groupby_week.py`
- `addons/test_read_group/tests/test_m2m_grouping.py`
- `addons/test_testing_utilities/ir.model.access.csv`
- `addons/test_testing_utilities/menu.xml`
- `addons/test_testing_utilities/models.py`
- `addons/test_testing_utilities/nested_o2m.py`
- `api.py`
- `cli/genproxytoken.py`
- `cli/templates/l10n_payroll/models/hr_contract.py.template`
- `cli/tsconfig.py`
- `conf/__init__.py`
- `fields.py`
- `models.py`
- `modules/graph.py`
- `modules/registry.py`
- `osv/osv.py`
- `service/wsgi_server.py`
- `tests/_flectra_checker_markup.py`
- `tests/test_security.py`
- `tools/_monkeypatches.py`
- `tools/_monkeypatches_lxml.py`
- `tools/_monkeypatches_pytz.py`
- `tools/_monkeypatches_urls.py`
- `tools/num2words_patch.py`
- `tools/win32.py`
- `upgrade/__init__.py`

## 2. Files ONLY in staged Odoo-19 core (new in Odoo 19)

Total: 227. By top-level dir/file:
- `addons`: 147
- `_monkeypatches`: 23
- `orm`: 23
- `tools`: 11
- `upgrade_code`: 9
- `cli`: 5
- `modules`: 2
- `api`: 1
- `fields`: 1
- `init.py`: 1
- `logging.py`: 1
- `models`: 1
- `tests`: 1
- `upgrade`: 1

Notable new top-level modules / files:
- `_monkeypatches/__init__.py`
- `_monkeypatches/_cpython.py`
- `_monkeypatches/ast.py`
- `_monkeypatches/bs4.py`
- `_monkeypatches/csv.py`
- `_monkeypatches/docutils.py`
- `_monkeypatches/email.py`
- `_monkeypatches/locale.py`
- `_monkeypatches/lxml.py`
- `_monkeypatches/markupsafe.py`
- `_monkeypatches/mimetypes.py`
- `_monkeypatches/num2words.py`
- `_monkeypatches/pytz.py`
- `_monkeypatches/re.py`
- `_monkeypatches/requests.py`
- `_monkeypatches/site.py`
- `_monkeypatches/stdnum.py`
- `_monkeypatches/urllib3.py`
- `_monkeypatches/werkzeug.py`
- `_monkeypatches/xlrd.py`
- `_monkeypatches/xlsxwriter.py`
- `_monkeypatches/xlwt.py`
- `_monkeypatches/zeep.py`
- `api/__init__.py`
- `cli/help.py`
- `cli/i18n.py`
- `cli/module.py`
- `cli/upgrade_code.py`
- `fields/__init__.py`
- `init.py`
- `logging.py`
- `models/__init__.py`
- `modules/module_graph.py`
- `orm/__init__.py`
- `orm/commands.py`
- `orm/decorators.py`
- `orm/domains.py`
- `orm/environments.py`
- `orm/fields.py`
- `orm/fields_binary.py`
- `orm/fields_misc.py`
- `orm/fields_numeric.py`
- `orm/fields_properties.py`
- `orm/fields_reference.py`
- `orm/fields_relational.py`
- `orm/fields_selection.py`
- `orm/fields_temporal.py`
- `orm/fields_textual.py`
- `orm/identifiers.py`
- `orm/model_classes.py`
- `orm/models.py`
- `orm/models_transient.py`
- `orm/registry.py`
- `orm/table_objects.py`
- `orm/types.py`
- `orm/utils.py`
- `tests/test_cursor.py`
- `tools/gc.py`
- `tools/i18n.py`
- `tools/intervals.py`

## 3. Common files that differ — highest-effort reconciliation targets

Total differing: 521.

### Top 40 by raw diff line-count (NOTE: dominated by auto-generated i18n `.po` translation catalogs — low reconciliation effort, regenerated not hand-merged):

| # | diff lines | file |
|---|-----------|------|
| 1 | 68483 | `addons/base/i18n/fr.po` |
| 2 | 68068 | `addons/base/i18n/de.po` |
| 3 | 67959 | `addons/base/i18n/tr.po` |
| 4 | 67883 | `addons/base/i18n/nl.po` |
| 5 | 65877 | `addons/base/i18n/ar.po` |
| 6 | 65609 | `addons/base/i18n/es.po` |
| 7 | 64846 | `addons/base/i18n/ru.po` |
| 8 | 64490 | `addons/base/i18n/ko.po` |
| 9 | 64456 | `addons/base/i18n/sv.po` |
| 10 | 64061 | `addons/base/i18n/zh_CN.po` |
| 11 | 63792 | `addons/base/i18n/pt_BR.po` |
| 12 | 63686 | `addons/base/i18n/id.po` |
| 13 | 63285 | `addons/base/i18n/fi.po` |
| 14 | 63132 | `addons/base/i18n/it.po` |
| 15 | 62405 | `addons/base/i18n/da.po` |
| 16 | 62283 | `addons/base/i18n/uk.po` |
| 17 | 61159 | `addons/base/i18n/cs.po` |
| 18 | 60978 | `addons/base/i18n/ja.po` |
| 19 | 60762 | `addons/base/i18n/ro.po` |
| 20 | 59567 | `addons/base/i18n/pl.po` |
| 21 | 53893 | `addons/base/i18n/et.po` |
| 22 | 53744 | `addons/base/i18n/zh_TW.po` |
| 23 | 53581 | `addons/base/i18n/th.po` |
| 24 | 51915 | `addons/base/i18n/ca.po` |
| 25 | 50326 | `addons/base/i18n/he.po` |
| 26 | 50250 | `addons/base/i18n/sk.po` |
| 27 | 49812 | `addons/base/i18n/pt.po` |
| 28 | 49264 | `addons/base/i18n/az.po` |
| 29 | 48487 | `addons/base/i18n/lv.po` |
| 30 | 47626 | `addons/base/i18n/hr.po` |
| 31 | 46658 | `addons/base/i18n/bg.po` |
| 32 | 46065 | `addons/base/i18n/hu.po` |
| 33 | 44949 | `addons/base/i18n/fa.po` |
| 34 | 44437 | `addons/base/i18n/lt.po` |
| 35 | 42764 | `addons/base/i18n/el.po` |
| 36 | 36137 | `addons/base/i18n/vi.po` |
| 37 | 31195 | `addons/base/i18n/sq.po` |
| 38 | 24460 | `addons/base/i18n/mn.po` |
| 39 | 23096 | `addons/base/i18n/sr@latin.po` |
| 40 | 23035 | `addons/base/i18n/es_419.po` |

### Top 40 differing CODE/non-translation files (real reconciliation targets):

| # | diff lines | file |
|---|-----------|------|
| 1 | 2745 | `addons/base/tests/test_views.py` |
| 2 | 2045 | `addons/base/models/res_users.py` |
| 3 | 2033 | `addons/base/tests/test_qweb.py` |
| 4 | 1803 | `tests/common.py` |
| 5 | 1752 | `addons/base/tests/test_expression.py` |
| 6 | 1750 | `addons/base/models/ir_ui_view.py` |
| 7 | 1451 | `addons/test_main_flows/static/tests/tours/main_flow.js` |
| 8 | 1404 | `addons/base/models/ir_qweb.py` |
| 9 | 1243 | `osv/expression.py` |
| 10 | 1199 | `tools/config.py` |
| 11 | 1145 | `http.py` |
| 12 | 1123 | `addons/base/models/ir_model.py` |
| 13 | 1041 | `tools/misc.py` |
| 14 | 982 | `addons/base/models/ir_cron.py` |
| 15 | 914 | `tools/translate.py` |
| 16 | 892 | `addons/base/tests/test_res_partner.py` |
| 17 | 864 | `addons/test_read_group/tests/test_private_read_group.py` |
| 18 | 864 | `addons/base/models/ir_actions.py` |
| 19 | 737 | `addons/base/models/res_partner.py` |
| 20 | 730 | `addons/base/tests/test_res_users.py` |
| 21 | 698 | `service/server.py` |
| 22 | 697 | `modules/module.py` |
| 23 | 697 | `addons/base/models/ir_attachment.py` |
| 24 | 663 | `addons/base/tests/test_ir_cron.py` |
| 25 | 593 | `addons/base/models/ir_actions_report.py` |
| 26 | 581 | `addons/base/views/res_partner_views.xml` |
| 27 | 564 | `sql_db.py` |
| 28 | 554 | `tools/populate.py` |
| 29 | 536 | `addons/base/views/res_users_views.xml` |
| 30 | 521 | `modules/loading.py` |
| 31 | 476 | `addons/base/data/res.country.state.csv` |
| 32 | 434 | `addons/base/views/ir_actions_views.xml` |
| 33 | 427 | `addons/base/tests/test_misc.py` |
| 34 | 416 | `addons/base/models/ir_mail_server.py` |
| 35 | 405 | `addons/base/tests/test_translate.py` |
| 36 | 401 | `tools/cache.py` |
| 37 | 377 | `tools/date_utils.py` |
| 38 | 371 | `addons/base/tests/test_date_utils.py` |
| 39 | 367 | `addons/base/tests/test_ir_filters.py` |
| 40 | 367 | `addons/base/models/ir_module.py` |

## 4. Summary

The Odoo-19 core package renames cleanly: of ~1202 files, 442 required namespace rewrites and the tool is idempotent. Structurally, 138 files exist only in today's Flectra core and 227 only in Odoo-19, reflecting a large architectural shift: Odoo-19 split former single-module files into packages — `orm/`, `api/`, `fields/`, `models/` are now directories, plus wholly new subsystems (`_monkeypatches/`, `upgrade_code/`, `logging.py`). Flectra's current core still uses the older flat layout (`api.py`, `fields.py`, `models.py`), so much of the only-in-Flectra set is the old flat modules that Odoo-19 has restructured. Of 975 shared files, 454 are already identical (post-rename) and 521 differ. The bulk of the differing line-count is auto-generated `.po`/`.pot` translation catalogs in `addons/base/i18n/` (regenerated, not hand-merged). The genuine engineering effort concentrates in the restructured ORM/fields/models/api layer, `http.py`, the `modules/`, `tools/`, `service/` and `cli/` subsystems, and reconciling Flectra's flat-file customizations against Odoo-19's package-based layout — a substantial but tractable port centered on the core framework internals.
