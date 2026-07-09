# mail — Merge Conflict Resolution Plan

Port target: Odoo 19. Decision hinges on OURS (Flectra) vs BASE (Odoo 18), branding neutralized
(`perl -pe 's/\bflectra\b/odoo/g; s/Flectra/Odoo/g'` on OURS, then `diff -w` vs BASE).

Key finding: OURS is Flectra built on an **older Odoo than BASE-18**. Every conflicted file differs even
after neutralizing branding, but in virtually all cases the remaining delta is pure **version drift**
(older Odoo APIs/method renames, the Odoo 18 `Store`/`_to_store` refactor, `check_access_rule`→`_check_access`,
`shortcode`→`canned.response`, `web_push`→`push`, `tree`→`list`, jQuery→vanilla DOM, missing newer Odoo
features), not Flectra customizations.

## Counts
- Conflicted code files (excl. .po/.pot): **286**
- **take-19: 285**
- **careful-merge: 1**
- **flectra-feature: 0**

## take-19 (285) — adopt Odoo 19
Spans the entire module: all `models/**` (incl. mail_message.py, mail_thread.py, discuss/*), all
`controllers/**`, all `static/src/**` JS/SCSS/XML/d.ts (core, discuss, call, gif, voice, typing, views),
all `tests/**`, all `views/**`, all `wizard/**`, `tools/discuss.py`, `security/mail_security.xml`,
`__manifest__.py`, and `data/**`.
Examples: `models/mail_message.py`, `models/mail_thread.py`, `models/discuss/discuss_channel.py`,
`static/src/core/common/thread_model.js`, `controllers/discuss/channel.py`, `views/mail_message_views.xml`,
`wizard/mail_compose_message.py`.
Notable branding-only bits still classed take-19: `models/res_company.py` (default brand color
`#009efb` vs Odoo `#875A7B`); various `flectrabot`/`flectra_sfu` tokens = OdooBot/SFU branding.

## careful-merge (1)
- `security/ir.model.access.csv` — OURS adds a portal-group create ACL on `mail.compose.message`
  (`access_mail_compose_message_portal`) that is absent from vanilla Odoo. Preserve this row when
  adopting the Odoo 19 CSV; everything else in the file is drift (shortcode→canned.response, web_push→push renames).

## flectra-feature (0)
None found.
