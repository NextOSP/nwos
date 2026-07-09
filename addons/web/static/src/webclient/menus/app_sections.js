import { _t } from "@web/core/l10n/translation";

const APP_SECTIONS = [
    {
        id: "overview",
        name: _t("Overview"),
        appXmlids: [
            "nwos_bod_dashboard.menu_bod_root",
            "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
        ],
    },
    {
        id: "communication",
        name: _t("Communication"),
        appXmlids: [
            "mail.menu_root_discuss",
            "calendar.mail_menu_calendar",
            "contacts.menu_contacts",
        ],
    },
    {
        id: "sales",
        name: _t("Sales"),
        appXmlids: ["crm.crm_menu_root", "sale.sale_menu_root"],
    },
    {
        id: "finance",
        name: _t("Finance"),
        appXmlids: ["account.menu_finance", "hr_expense.menu_hr_expense_root"],
    },
    {
        id: "human_resources",
        name: _t("Human Resources"),
        appXmlids: [
            "hr.menu_hr_root",
            "hr_attendance.menu_hr_attendance_root",
            "hr_holidays.menu_hr_holidays_root",
            "hr_recruitment.menu_hr_recruitment_root",
        ],
    },
    {
        id: "operations",
        name: _t("Operations"),
        appXmlids: [
            "purchase.menu_purchase_root",
            "stock.menu_stock_root",
            "nwos_stock_request.menu_stock_request_root",
            "mrp.menu_mrp_root",
            "data_recycle.menu_data_cleaning_root",
            "utm.menu_link_tracker_root",
        ],
    },
    {
        id: "administration",
        name: _t("Administration"),
        appXmlids: ["base.menu_management", "base.menu_administration"],
    },
    {
        id: "other",
        name: _t("Other"),
        appXmlids: [],
    },
];

const APP_SECTION_BY_XMLID = new Map(
    APP_SECTIONS.flatMap((section) => section.appXmlids.map((xmlid) => [xmlid, section.id]))
);

export function getAppSections(apps) {
    const sections = APP_SECTIONS.map((section) => ({
        id: section.id,
        name: section.name,
        apps: [],
    }));
    const sectionById = new Map(sections.map((section) => [section.id, section]));

    for (const app of apps) {
        const sectionId = APP_SECTION_BY_XMLID.get(app.xmlid) || "other";
        sectionById.get(sectionId).apps.push(app);
    }

    return sections.filter((section) => section.apps.length);
}
