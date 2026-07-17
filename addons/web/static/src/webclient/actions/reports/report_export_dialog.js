import { Dialog } from "@web/core/dialog/dialog";
import { _t, loadLanguages } from "@web/core/l10n/translation";
import { downloadReport, getReportUrl } from "@web/webclient/actions/reports/utils";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

import { Component, onWillStart, useState } from "@nwos/owl";

const SKIP_REPORT_EXPORT_DIALOG = "__skip_report_export_dialog__";

export class ReportExportDialog extends Component {
    static template = "web.ReportExportDialog";
    static components = { Dialog };
    static props = {
        action: Object,
        close: Function,
        export: Function,
        cancel: Function,
    };

    setup() {
        this.orm = this.env.services.orm;
        this.notification = this.env.services.notification;
        this.env.dialogData.dismiss = () => this.props.cancel();
        this.state = useState({
            reports: [],
            languages: [],
            paperformats: [],
            selectedReportId: String(this.props.action.id || "current"),
            selectedLang: this.props.action.context?.lang || user.context.lang,
            selectedPaperformatId: "",
            previewUrl: "",
            isPreviewLoading: false,
            isExporting: false,
        });

        onWillStart(async () => {
            const [reports, languages, paperformats] = await Promise.all([
                this.loadReports(),
                loadLanguages(this.orm),
                this.loadPaperformats(),
            ]);
            this.state.reports = reports;
            this.state.languages = languages;
            this.state.paperformats = paperformats;
            this.state.selectedPaperformatId = this.getDefaultPaperformatId();
            this.refreshPreview();
        });
    }

    async loadReports() {
        const action = this.props.action;
        const currentReport = this.normalizeReport(action, _t("Current report"));
        const activeModel = action.context?.active_model || action.res_model || action.model;
        if (!activeModel) {
            return [currentReport];
        }

        const domain = [
            ["model", "=", activeModel],
            ["report_type", "in", ["qweb-pdf", "qweb-text"]],
        ];
        const reports = await this.orm.searchRead(
            "ir.actions.report",
            domain,
            ["name", "report_name", "report_file", "report_type", "paperformat_id"],
            { order: "name" }
        );
        const normalizedReports = reports.map((report) => this.normalizeReport(report));
        if (!normalizedReports.some((report) => report.id === currentReport.id)) {
            normalizedReports.unshift(currentReport);
        }
        return normalizedReports;
    }

    normalizeReport(report, fallbackName) {
        return {
            id: String(report.id || "current"),
            name: report.name || report.display_name || fallbackName,
            report_name: report.report_name,
            report_file: report.report_file,
            report_type: report.report_type,
            paperformat_id: Array.isArray(report.paperformat_id) ? report.paperformat_id[0] : false,
        };
    }

    async loadPaperformats() {
        return this.orm.searchRead("report.paperformat", [], ["name"], { order: "name" });
    }

    getDefaultPaperformatId() {
        return this.selectedReport?.paperformat_id ? String(this.selectedReport.paperformat_id) : "";
    }

    get selectedReport() {
        return (
            this.state.reports.find((report) => report.id === this.state.selectedReportId) ||
            this.state.reports[0]
        );
    }

    get selectedLanguageName() {
        const selectedLanguage = this.state.languages.find(
            ([code]) => code === this.state.selectedLang
        );
        return selectedLanguage?.[1] || this.state.selectedLang;
    }

    getSelectedAction(reportType = this.selectedReport.report_type) {
        const selectedReport = this.selectedReport;
        return {
            ...this.props.action,
            report_name: selectedReport.report_name,
            report_file: selectedReport.report_file,
            report_type: reportType,
            name: selectedReport.name,
            display_name: selectedReport.name,
            context: {
                ...(this.props.action.context || {}),
                lang: this.state.selectedLang,
                // Reports (e.g. sale quotations) force the customer's language;
                // `report_lang` lets the template honor the language picked here.
                report_lang: this.state.selectedLang,
                ...(this.state.selectedPaperformatId
                    ? { report_paperformat_id: Number(this.state.selectedPaperformatId) }
                    : {}),
                [SKIP_REPORT_EXPORT_DIALOG]: true,
            },
        };
    }

    refreshPreview() {
        if (!this.selectedReport?.report_name) {
            this.state.previewUrl = "";
            this.state.isPreviewLoading = false;
            return;
        }
        // Render the preview as PDF (not HTML) so the selected paper format and
        // language are actually reflected: paper format only affects PDF output,
        // and the PDF is rendered inline by the browser's viewer.
        const previewAction = this.getSelectedAction("qweb-pdf");
        let previewUrl = getReportUrl(previewAction, "pdf", {
            ...user.context,
            ...(previewAction.context || {}),
        });
        // Cache-buster: the report URL is otherwise identical across renders, so
        // the browser would serve a stale cached PDF after a template change.
        previewUrl += (previewUrl.includes("?") ? "&" : "?") + "_ts=" + Date.now();
        this.state.isPreviewLoading = previewUrl !== this.state.previewUrl;
        this.state.previewUrl = previewUrl;
    }

    onPreviewLoaded() {
        this.state.isPreviewLoading = false;
    }

    onReportChange(ev) {
        this.state.selectedReportId = ev.target.value;
        this.state.selectedPaperformatId = this.getDefaultPaperformatId();
        this.refreshPreview();
    }

    onLanguageChange(ev) {
        this.state.selectedLang = ev.target.value;
        this.refreshPreview();
    }

    onPaperformatChange(ev) {
        this.state.selectedPaperformatId = ev.target.value;
        this.refreshPreview();
    }

    async export() {
        this.state.isExporting = true;
        try {
            const action = this.getSelectedAction();
            const type = action.report_type.slice(5);
            const result = await downloadReport(rpc, action, type, {
                ...user.context,
                ...(action.context || {}),
            });
            if (result.message) {
                this.notification.add(result.message, {
                    sticky: true,
                    title: _t("Report"),
                });
            }
            if (!result.success) {
                return false;
            }
            await this.props.export();
            this.props.close();
        } finally {
            this.state.isExporting = false;
        }
    }

    cancel() {
        this.props.cancel();
        this.props.close();
    }
}

registry.category("ir.actions.report handlers").add("report_export_dialog", async (action, options, env) => {
    if (
        action.context?.[SKIP_REPORT_EXPORT_DIALOG] ||
        !["qweb-pdf", "qweb-text"].includes(action.report_type)
    ) {
        return false;
    }

    return new Promise((resolve) => {
        env.services.dialog.add(ReportExportDialog, {
            action,
            export: () => resolve(true),
            cancel: () => resolve(true),
        });
    });
});
