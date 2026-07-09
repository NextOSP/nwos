# account — Merge Conflict Resolution Plan (Flectra → Odoo 19)

Method: for each conflicted CODE file (excluding .po/.pot), diffed OURS (Flectra, Odoo-18-based)
against BASE (renamed Odoo 18.0 fork base) with Flectra branding neutralized
(`s/\bflectra\b/odoo/g; s/Flectra/Odoo/g`). Decision hinges on remaining OURS-vs-BASE differences.

## Summary counts

| Classification   | Count |
|------------------|-------|
| take-19          | 122   |
| careful-merge    | 9     |
| flectra-feature  | 0     |
| **Total**        | **131** |

Dominant pattern: Flectra is an *older* Odoo-18-based fork, so almost every OURS-only (`<`) block is
stale old-Odoo code that BASE (Odoo 18.0) later rewrote — paired replacements, not Flectra additions.
Those are all take-19. The 9 careful-merge files are the exceptions with genuine OURS-only content
(new field/method/logic or a Flectra regression test) that has no BASE counterpart and would be
silently dropped by adopting Odoo 19 wholesale. No distinct branded product features were found.

## careful-merge (9) — sorted most-substantive first

1. **models/account_move.py** — Central 3810-line engine. Before adopting Odoo 19, hand-verify no Flectra tweak survives in OURS-only blocks: inalterability hash chain (`secure_sequence_number`/`inalterable_hash`/`_get_new_hash`/`_compute_string_to_hash`), sequence-hole gap index (`account_move_sequence_index3`), tax-line auto-balance/unlink, payment/statement journal fallback, `send_and_print_values`.
2. **models/account_move_line.py** — Preserve/verify OURS-only `blocked` ("No Follow-up") field and on-line tax computation (`_compute_all_tax`/`_compute_tax_key`, `compute_all_tax_dirty`, `_convert_to_tax_base_line_dict`) against Odoo 19's reworked tax engine.
3. **wizard/account_payment_register.py** — Preserve OURS-only `_get_batches` partner-bank + branch/sibling-company batching logic (the "different branches without access to parent company" guard) against Odoo 19's installments/batching rewrite.
4. **models/onboarding_onboarding_step.py** — Preserve OURS-only `action_open_step_default_taxes` (Taxes setup-bar button opening `view_onboarding_tax_tree`) and `create_op_move_if_non_existant` opening-move logic; no BASE counterpart.
5. **wizard/accrued_orders.py** — Preserve OURS-only sale-order analytic distribution: `if not is_purchase and order.analytic_account_id: distribution[str(order.analytic_account_id.id)] += 100.0` (3 spots, no BASE counterpart); rest is version drift.
6. **models/__init__.py** — Preserve OURS-only `from . import ir_http` (Flectra `ir.http.session_info` quick_edit_mode override, absent from BASE); re-check the `onboarding_onboarding` import against Odoo 19's list.
7. **tests/test_account_move_out_invoice.py** — Bulk is version drift; preserve OURS-only `test_invoice_with_no_lines` (regression: portal preview of an invoice with no lines must not crash).
8. **tests/test_company_branch.py** — Preserve Flectra-added regression tests `test_branch_user_can_assign_outstanding_credit_with_parent_access` and `test_branch_user_bank_statement_foreign_currency` (branch-user access fix; modern syntax, 2025 dates).
9. **tests/test_portal_attachment.py** — Bulk is Odoo 18 route rename (`/portal/attachment` → `/mail/attachment`); preserve OURS-only `test_preview_early_discount_draft_invoice` (early-discount default-date fix).

## flectra-feature (0)

None — no distinct branded/product capability among the conflicts.

## take-19 (122) — adopt Odoo 19 wholesale

All OURS-vs-BASE differences are branding, whitespace/formatting, paired old-Odoo→Odoo-18 version
evolution (e.g. `tree`→`list`, `company_id`→`company_ids`, `to_check`→`checked`, `price_include`→
`price_include_override`, raw-SQL→`_read_group`/`SQL()`, OWL static-property modernization, tax-engine
and payment-model refactors), or stale code marked for removal. Representative examples:

- Core models (pure version-gap refactors): `models/account_tax.py` (full new tax engine),
  `models/account_payment.py` (payment-model refactor), `models/account_account.py`,
  `models/company.py`, `models/chart_template.py`, `models/partner.py`,
  `models/account_journal.py`, `models/account_journal_dashboard.py`, `models/sequence_mixin.py`,
  `models/res_config_settings.py`, `models/account_report.py`.
- Views: `views/account_move_views.xml`, `views/account_account_views.xml`,
  `views/account_tax_views.xml`, `views/account_journal_dashboard_view.xml`,
  `views/res_config_settings_views.xml`, `views/report_invoice.xml`, plus all other conflicted views.
- Tests: `tests/common.py`, `tests/test_tax.py`, `tests/test_account_payment.py`,
  `tests/test_account_move_reconcile.py`, and the remaining conflicted test files.
- JS/SCSS/CSS: all conflicted `static/src/**` files (OWL/static-property refactors, styling).
  Several were byte-identical after neutralization: `static/src/services/account_notification_service.js`,
  `static/src/components/document_state/document_state_field.js`,
  `static/src/components/open_move_line_move_widget/open_move_line_move_widget.js`,
  `static/src/components/account_payment_term_form/payment_term_line_ids.js`,
  `static/src/components/auto_save_res_partner_bank/auto_save_res_partner_bank.js`,
  `views/account_analytic_account_views.xml`.
- Data/tools/controllers: `tools/structured_reference.py` (BASE adds SI reference — pure addition),
  `data/template/account.account-generic_coa.csv`, `data/account_data.xml`,
  `data/mail_template_data.xml`, `controllers/portal.py`, `controllers/download_docs.py`,
  `security/account_security.xml`, `__manifest__.py`.
</content>
</invoke>
