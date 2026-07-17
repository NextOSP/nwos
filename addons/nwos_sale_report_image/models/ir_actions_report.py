# Part of NextOSP. See LICENSE file for full copyright and licensing details.
import logging

from nwos import api, models

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _nwos_consolidate_sale_reports(self):
        """Collapse the redundant sale-order quotation reports.

        Several modules each add a quotation report on ``sale.order`` and they
        all pile into the Print menu *and* the report-preview "Template"
        selector (which lists every qweb-pdf report for the model, regardless of
        binding). The intended set is only three: the clean "Quotation" (this
        module's layout), "Quotation with Image", and "PRO-FORMA Invoice".

        This method:

        - renames the standard sale report (labelled "PDF Quote" by
          ``sale_pdf_quote_builder``) to "Quotation" - it already renders our
          clean template, repointed in ``sale_report_image_actions.xml``;
        - deletes the "Quotation / Order" (raw) *action* added by
          ``sale_pdf_quote_builder``. Only the action is removed; its template
          ``sale.report_saleorder_raw`` stays, so that module keeps rendering.

        The duplicate "Quotation (Clean)" action this module used to define is
        dropped from the data file, so Flectra's orphan cleanup unlinks it.

        Called from a ``<function>`` in a non-noupdate data file, so it runs on
        install and on every module update. Every step is guarded, making it a
        no-op when a target is already gone or the owning module is absent.
        """
        default = self.env.ref("sale.action_report_saleorder", raise_if_not_found=False)
        if default and default.name != "Quotation":
            default.name = "Quotation"
            _logger.info("nwos_sale_report_image: renamed default sale report to 'Quotation'")

        raw = self.env.ref(
            "sale_pdf_quote_builder.action_report_saleorder_raw",
            raise_if_not_found=False,
        )
        if raw:
            raw.unlink()
            _logger.info("nwos_sale_report_image: removed redundant 'Quotation / Order' report action")

        self._nwos_repoint_clean_reports()

    @api.model
    def _nwos_repoint_clean_reports(self):
        """Point the standard purchase / delivery / invoice reports at this
        module's clean self-contained templates, so every business document
        shares the same IBM-Carbon layout as the quotation.

        Done in Python (not XML) because purchase/stock are NOT dependencies of
        this module: `env.ref(..., raise_if_not_found=False)` makes each repoint
        a no-op when the owning module is absent. Runs on install and every
        update (via the <function> that also calls the sale consolidation).
        Only report_name/report_file/paperformat change, so it is reversible.
        """
        euro = self.env.ref("base.paperformat_euro", raise_if_not_found=False)
        # action xmlid -> clean report template
        mapping = {
            "sale.action_report_pro_forma_invoice": "nwos_sale_report_image.report_saleorder_proforma_clean",
            "purchase.action_report_purchase_order": "nwos_sale_report_image.report_purchaseorder_clean",
            "purchase.report_purchase_quotation": "nwos_sale_report_image.report_purchaseorder_clean",
            "stock.action_report_delivery": "nwos_sale_report_image.report_delivery_clean",
            "account.account_invoices": "nwos_sale_report_image.report_invoice_clean",
            "account.account_invoices_without_payment": "nwos_sale_report_image.report_invoice_clean",
            "account.action_report_payment_receipt": "nwos_sale_report_image.report_payment_receipt_clean",
        }
        for action_xmlid, report_name in mapping.items():
            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            if not action:
                continue
            vals = {"report_name": report_name, "report_file": report_name}
            if euro:
                vals["paperformat_id"] = euro.id
            action.write(vals)
            _logger.info("nwos_sale_report_image: repointed %s -> %s", action_xmlid, report_name)
