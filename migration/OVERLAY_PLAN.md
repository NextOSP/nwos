# Flectra CORE Overlay Plan — Odoo-19 foundation (THEIRS)

Trees compared by relative path:
- OURS   = `/Users/dean/code_env/flectra/flectra/`                          (current Flectra, pre-18 based)
- BASE   = `/Users/dean/code_env/flectra/migration/staging/flectra18-base/` (renamed Odoo 18.0)
- THEIRS = `/Users/dean/code_env/flectra/migration/staging/flectra/`        (renamed Odoo 19.0 = foundation)

Strategy: THEIRS is the foundation; overlay OURS files only where Flectra genuinely diverges.

---

## Category E — in OURS, absent from BASE and THEIRS (42 files)

### KEEP (28) — genuine Flectra additions / legacy models Odoo dropped before 18
| File | Reason |
|------|--------|
| `addons/base/models/ir_property.py` | Legacy `ir.property` model Flectra retains; Odoo removed it in 17. Imports resolve (`osv/expression.py` present in THEIRS). |
| `addons/base/views/ir_property_views.xml` | UI for the retained `ir.property` model (referenced in Flectra `base/__manifest__.py`). |
| `addons/base/populate/__init__.py` | Flectra populate-factory package; Odoo 19 base ships no populate factories. |
| `addons/base/populate/ir_filters.py` | Flectra `_populate_factories` (additive `_inherit`). |
| `addons/base/populate/res_company.py` | idem |
| `addons/base/populate/res_currency.py` | idem |
| `addons/base/populate/res_partner.py` | idem |
| `addons/base/populate/res_user.py` | idem |
| `addons/base/i18n/hy.po` | Flectra-provided Armenian base translation, not shipped by Odoo 19. |
| `addons/base/i18n/sr.po` | Flectra-provided Serbian base translation (THEIRS only has `sr@latin.po`). |
| `addons/base/static/img/bg_background_template.jpg` | Flectra-only static asset. |
| `addons/base/static/img/icons/website_twitter_wall.png` | Flectra-only static asset. |
| `addons/base/tests/flectra.jpg` | Flectra test image fixture. |
| `addons/test_impex/` (9 files) | Flectra-retained import/export test addon (not in 18/19); tests live import/export API. |
| `addons/test_populate/` (6 files) | Flectra test addon for the populate framework, which still exists (`tools/populate.py`, `cli/populate.py`). |

`test_impex` files: `__init__.py`, `__manifest__.py`, `ir.model.access.csv`, `models.py`, `tests/__init__.py`, `tests/contacts.json`, `tests/contacts_big.json`, `tests/test_export.py`, `tests/test_load.py`.
`test_populate` files: `__init__.py`, `__manifest__.py`, `ir.model.access.csv`, `models.py`, `tests/__init__.py`, `tests/test_populate.py`.

### DROP (14) — stale copies of relocated/removed upstream code
| File | Reason |
|------|--------|
| `addons/base/rng/tree_view.rng` | Odoo 19 renamed tree→list; superseded by THEIRS `addons/base/rng/list_view.rng`. |
| `addons/test_lint/tests/_flectra_checker_gettext.py` | THEIRS ships `_odoo_checker_gettext.py` + `test_checkers.py` that imports it; Flectra rename is orphaned. |
| `addons/test_lint/tests/_flectra_checker_sql_injection.py` | idem (`_odoo_checker_sql_injection.py` in THEIRS). |
| `addons/test_lint/tests/_flectra_checker_unlink_override.py` | idem (`_odoo_checker_unlink_override.py` in THEIRS). |
| `addons/test_read_group/tests/test_exceptions.py` | `test_read_group` fully refactored in Odoo 19 (new test suite); stale test file. |
| `osv/osv.py` | Deprecation shim ("Since 17.0") for `osv/osv_memory` aliases; removed in Odoo 19 (`osv/` now only `__init__.py`+`expression.py`). |
| `service/wsgi_server.py` | Deprecation shim (moved to `flectra.http.root` in 15.3); removed in Odoo 19. |
| `tests/_flectra_checker_markup.py` | Stale pylint checker; lint checkers relocated to `addons/test_lint/tests/`. |
| `tests/test_security.py` | Standalone `__main__` security-scan script removed/relocated upstream. |
| `tools/_monkeypatches.py` | Superseded by THEIRS `_monkeypatches/` package (`patch_init()`). |
| `tools/_monkeypatches_lxml.py` | → `_monkeypatches/lxml.py`. |
| `tools/_monkeypatches_pytz.py` | → `_monkeypatches/pytz.py`. |
| `tools/_monkeypatches_urls.py` | → `_monkeypatches/urllib3.py` + `werkzeug.py`. |
| `tools/num2words_patch.py` | → `_monkeypatches/num2words.py`. |

---

## Category B — in OURS+BASE, absent from THEIRS (12 core files)

| File | Decision | Reason |
|------|----------|--------|
| `__init__.py` | DROP (restructured) | Odoo 19 split the monolith: heavy setup → `init.py` (imported by `cli/command.py`), monkeypatches → `_monkeypatches/`, shortcuts set in `init.py`. Do NOT overlay the old monolith. NOTE: THEIRS ships no top-level `__init__.py`; the package loads as a PEP-420 namespace — if `import flectra` breaks, PORT a *thin* namespace stub (only the `__path__` extend), never the old file. |
| `api.py` | DROP (restructured) | THEIRS `api/__init__.py` package supersedes the flat module. |
| `fields.py` | DROP (restructured) | THEIRS `fields/__init__.py` package supersedes the flat module. |
| `models.py` | DROP (restructured) | THEIRS `models/__init__.py` package supersedes the flat module. |
| `modules/graph.py` | DROP (renamed) | Renamed to THEIRS `modules/module_graph.py`. |
| `modules/registry.py` | DROP (restructured) | Now the THEIRS `modules/registry/` package. |
| `conf/__init__.py` | KEEP / PORT | THEIRS dropped the `conf/` package but code still references `flectra.conf.server_wide_modules` (e.g. `addons/test_http/tests/test_registry.py`). The module is still required → overlay it. |
| `upgrade/__init__.py` | DROP | THEIRS uses `upgrade/.gitkeep` (namespace dir for external upgrade scripts); no package `__init__.py` needed. |
| `cli/genproxytoken.py` | KEEP | Flectra-only CLI (proxy-token generation); not in Odoo 19. Imports (`from . import Command`, `flectra.tools.config`) still valid. |
| `cli/tsconfig.py` | KEEP | Flectra-retained dev CLI (tsconfig generation); dropped by Odoo 19. Import `flectra.modules.module.MANIFEST_NAMES` still valid. |
| `tools/win32.py` | DROP | Windows locale shim removed in Odoo 19; not imported anywhere in OURS → orphaned. |
| `cli/templates/l10n_payroll/models/hr_contract.py.template` | DROP | Odoo 19 scaffold replaced `hr.contract` with `hr.version`; THEIRS ships `hr_version.py.template`. Keeping the old template yields a broken scaffold. |

---

## Import-surface verification

THEIRS provides all four packages plus `init.py` and `orm/`:
- `api/__init__.py` ✓  `fields/__init__.py` ✓  `models/__init__.py` ✓  `init.py` ✓  `orm/__init__.py` ✓
- No top-level `__init__.py` in THEIRS (loads as PEP-420 namespace; `cli/command.py` does `import flectra.init`).

Re-exported public names:
- `flectra/api/__init__.py`: `NewId`, decorators (`autovacuum, constrains, depends, depends_context, deprecated, model, model_create_multi, onchange, ondelete, private, readonly`), `Environment`, `SUPERUSER_ID`, and types (`ContextType, DomainType, IdType, Self, ValuesType`).
- `flectra/fields/__init__.py`: `Field`, all field classes (`Id, Json, Boolean, Integer, Float, Monetary, Char, Text, Html, Selection, Date, Datetime, Many2one, Many2many, One2many, Many2oneReference, Reference, Properties, PropertiesDefinition, Binary, Image`), `Command`, `Domain`, `NO_ACCESS`, `parse_field_expr`.
- `flectra/models/__init__.py`: `BaseModel, Model, AbstractModel, TransientModel, MetaModel`, magic-column consts, `Constraint/Index/UniqueIndex`, helpers.
- `flectra/init.py`: sets top-level shortcuts `Command`, `SUPERUSER_ID`, `_`, `_lt` and imports `_monkeypatches`.

Result for `from flectra import api, fields, models, Command, SUPERUSER_ID, _`:
- `api`, `fields`, `models` → resolve as submodule packages. ✓
- `Command`, `SUPERUSER_ID`, `_` → wired in `init.py`, BUT `init.py` has a rename defect: it does `import flectra` yet assigns to `odoo.SUPERUSER_ID/_/_lt/Command` while no `odoo` name/shim is defined. As-is this raises `NameError` (or attaches to the wrong module), so the three top-level shortcuts do **not** resolve until `init.py` lines 40-43 are fixed (`odoo.` → `flectra.`, or add `import flectra as odoo`).

Action item: fix the `odoo.`→`flectra.` assignments in THEIRS `init.py` so the shortcut import surface resolves.
