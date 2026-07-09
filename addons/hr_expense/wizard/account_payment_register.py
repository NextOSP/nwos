from nwos import models, api, _
from nwos.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _get_expenses_from_payment_process_vals(self, vals):
        return vals['batch']['lines'].move_id.expense_ids.filtered(lambda expense: expense.payment_mode == 'own_account')

    def _ensure_expense_payment_account(self, payments, to_process):
        for payment, vals in zip(payments, to_process):
            if not self._get_expenses_from_payment_process_vals(vals) or payment.outstanding_account_id:
                continue

            journal_account = payment.journal_id.default_account_id
            if (
                journal_account
                and journal_account.account_type in ('asset_cash', 'liability_credit_card')
                and (not journal_account.currency_id or journal_account.currency_id == payment.currency_id)
            ):
                payment.outstanding_account_id = journal_account
                if not payment.payment_method_line_id.payment_account_id:
                    payment.payment_method_line_id.payment_account_id = journal_account
                continue

            raise UserError(_(
                "The %(journal)s journal is missing a payment account, so NWOS cannot create "
                "a journal entry for this expense payment. Configure the payment account on "
                "the %(method)s payment method before paying the expense.",
                journal=payment.journal_id.display_name,
                method=payment.payment_method_line_id.display_name,
            ))

    def _write_expense_id_on_payment_moves(self, to_process):
        for vals in to_process:
            payment = vals['payment']
            expenses = self._get_expenses_from_payment_process_vals(vals)
            if not expenses:
                continue
            if not payment.move_id:
                raise UserError(_(
                    "The payment %(payment)s was created without a journal entry, so the expense "
                    "cannot be marked as paid. Configure a payment account on the %(journal)s journal.",
                    payment=payment.display_name,
                    journal=payment.journal_id.display_name,
                ))
            payment.move_id.line_ids.write({'expense_id': expenses[0].id})

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    @api.model
    def _get_line_batch_key(self, line):
        # OVERRIDE to set the bank account defined on the employee
        res = super()._get_line_batch_key(line)
        expense = line.move_id.expense_ids.filtered(lambda expense: expense.payment_mode == 'own_account')
        if expense and not line.move_id.partner_bank_id:
            res['partner_bank_id'] = (
                    expense.employee_id.sudo().primary_bank_account_id.id
                    or line.partner_id.bank_ids
                    and line.partner_id.bank_ids.ids[0]
            )
        return res

    def _init_payments(self, to_process, edit_mode=False):
        # OVERRIDE
        payments = super()._init_payments(to_process, edit_mode=edit_mode)
        self._ensure_expense_payment_account(payments, to_process)
        return payments

    def _post_payments(self, to_process, edit_mode=False):
        # OVERRIDE
        super()._post_payments(to_process, edit_mode=edit_mode)
        self._write_expense_id_on_payment_moves(to_process)
