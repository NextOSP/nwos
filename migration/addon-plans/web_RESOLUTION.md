# `web` addon — Odoo 19 merge conflict resolution plan

Method: for each conflicted code file, OURS was piped through
`sed 's/\bflectra\b/odoo/g; s/Flectra/Odoo/g'` and diffed (`-w`) against BASE
(addons18-base). Decision hinges on OURS vs BASE.

Key finding: Flectra's `web` is an **older copy of upstream Odoo**. The large
OURS-vs-BASE diffs are Odoo version drift (e.g. `@api.readonly` decorators,
`name_search`→`_name_search`, `authenticate(login,pwd)`→`authenticate(credential)`,
`readonly=True` route kwargs, `LazyTranslate`, `_filter_access_rules`→`_filtered_access`),
**not** Flectra logic. Genuine Flectra content is limited to branding: logo assets
and a handful of `flectrahq.com` / `flectra-icon` / `flectra_*` strings that the
`\bflectra\b` neutralization does not catch. → almost everything is take-19.

## Counts
- Total conflicted code files (excl. .po/.pot): **322**
- **take-19: 315** — of which **8 are vendored libs** (`static/lib/**`; always take-19)
- **careful-merge: 6**
- **flectra-feature: 1**

## take-19 (315)
Adopt Odoo 19 wholesale. Comprises:
- 8 vendored/minified libs: `static/lib/ace/ace.js`, `static/lib/ace/mode-{xml,python,scss}.js`,
  `static/lib/ace/theme-monokai.js`, `static/lib/Chart/Chart.js`,
  `static/lib/luxon/luxon.js`, `static/lib/zxing-library/zxing-library.js`
- ~4 files identical to BASE after branding neutralization
  (`models/res_partner.py`, `tests/test_ir_model.py`, `tests/test_partner.py`, `controllers/domain.py`)
- ~303 hand-written framework files (Python models/controllers/tests + `static/src/**`
  JS/XML/SCSS) whose only OURS-vs-BASE differences are Odoo version drift plus the
  pervasive `@flectra-module` / `flectra.*` / `FlectraEnv` framework-namespace branding
  (systematic rename, not per-file logic). Examples: `models/models.py`,
  `models/res_users.py`, `controllers/home.py`, `controllers/database.py`,
  `static/src/webclient/actions/action_service.js`, `static/src/views/list/list_renderer.js`,
  `static/src/core/dropdown/dropdown.js`, `static/src/env.js`.

## careful-merge (6)
Adopt the Odoo 19 file structure, but re-apply the Flectra branding string/asset
noted (each is drift + a small branding delta absent from BASE):
- `__manifest__.py` — preserve Flectra lib asset-bundle paths: `web/static/lib/flectra_ui_icons/*` and `web/static/lib/owl/flectra_module.js`.
- `models/ir_http.py` — preserve Flectra `support_url` in session_info (`https://www.flectrahq.com/buy`).
- `controllers/session.py` — preserve Flectra OAuth accounts URL (`https://accounts.flectrahq.com/oauth2/auth`).
- `controllers/webmanifest.py` — preserve Flectra app icon assets (`flectra-icon-<size>.png`, `_icon_path`, `flectra_icon` template var).
- `static/src/webclient/user_menu/user_menu_items.js` — preserve Flectra docs URL, the "My Flectra.com account" item (`flectraAccountItem`, `flectra_account`) and `accounts.flectrahq.com/account`.
- `static/src/webclient/settings_form_view/fields/upgrade_dialog.xml` — preserve Flectra upgrade/editions link (`flectrahq.com/editions`).

## flectra-feature (1)
- `views/webclient_templates.xml` — Flectra logo/branding on the login and database-manager pages (`/web/static/img/flectra_logo_tiny.png`, "Powered by Flectra", `flectra_icon`). Layer Odoo 19 template changes beneath the Flectra logo markup.
