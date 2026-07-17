/** @odoo-module **/

import { Component, useRef, useState } from "@nwos/owl";

import {
    eventKind,
    eventLabel,
    formatBytes,
    formatClock,
    formatRelative,
    safeJson,
    safeMarkdown,
    safeUrl,
} from "../app/nextbot_utils";

export function isUserFacingCard(card = {}) {
    const type = String(card.type || card.kind || card.card_type || "").toLowerCase();
    if (type.includes("approval") || type.includes("quotation") || type.includes("quote")) {
        return true;
    }
    if (type.includes("record") && Boolean(card.res_model && (card.res_id || card.record_id))) {
        return true;
    }
    // Generated files are deliverables. Search/read tables are internal evidence
    // and remain available in the Details inspector instead of flooding chat.
    return Boolean(
        (type.includes("artifact") || type.includes("file")) &&
            (card.download_url || card.url || card.href)
    );
}

export function approvalOperationsForCard(card = {}) {
    const preview = card.preview && typeof card.preview === "object" ? card.preview : null;
    if (!preview) return [];
    const proposed = preview.type === "batch"
        ? (Array.isArray(preview.operations) ? preview.operations : [])
        : [{ id: card.id, tool: card.tool, summary: preview.title || card.summary, preview }];
    const executions = new Map(
        (Array.isArray(card.operations) ? card.operations : []).map((operation) => [
            String(operation.id),
            operation,
        ])
    );
    const state = String(card.status || card.state || "pending").toLowerCase();
    return proposed.map((operation, index) => {
        const operationPreview = operation?.preview || {};
        const execution = executions.get(String(operation.id)) || {};
        const result = execution.result && typeof execution.result === "object" ? execution.result : {};
        const resultRecords = Array.isArray(result.records) ? result.records : [];
        const model = result.model || operationPreview.model || "";
        const previewSample = (Array.isArray(operationPreview.sample) ? operationPreview.sample : [])
            .slice(0, 10);
        const sample = state === "approved" && resultRecords.length
            ? resultRecords.slice(0, 10).map((record, recordIndex) => {
                const item = previewSample.find((candidate) => candidate && typeof candidate === "object" && (
                    (record.id && Number(candidate.res_id || candidate.id) === Number(record.id)) ||
                    (record.default_code && candidate.default_code === record.default_code) ||
                    (record.barcode && candidate.barcode === record.barcode) ||
                    (record.name && candidate.name === record.name)
                )) || previewSample[recordIndex] || {};
                return typeof item === "object"
                    ? { ...item, ...record, res_model: model }
                    : { display_name: item, ...record, res_model: model };
            })
            : previewSample;
        const proposalCount = Number(operationPreview.count ?? sample.length ?? 1);
        const runtimeCount = result.created_count ?? result.updated_count;
        const count = state === "approved" && runtimeCount !== undefined
            ? Number(runtimeCount)
            : proposalCount;
        const runtimeSkipped = Array.isArray(result.skipped_records) ? result.skipped_records : null;
        const skippedSample = (runtimeSkipped || operationPreview.skipped_sample || []).slice(0, 10);
        const skippedCount = state === "approved" && result.skipped_count !== undefined
            ? Number(result.skipped_count)
            : Number(operationPreview.skipped_count || 0);
        const tool = String(operation.tool || execution.tool || card.tool || "");
        const action = operationPreview.action || (
            tool.includes("create") ? "create" : tool.includes("update") ? "update" : "change"
        );
        return {
            id: operation.id || index,
            summary: operation.summary || operationPreview.title ||
                (proposalCount === 1
                    ? "Review 1 proposed ERP change"
                    : `Review ${proposalCount} proposed ERP changes`),
            action,
            count,
            proposalCount,
            sample,
            model,
            modelLabel: operationPreview.model_label || model || "ERP",
            skippedCount,
            skippedSample,
        };
    });
}

export class CarbonIcon extends Component {
    static template = "nextbot_workspace.CarbonIcon";
    static props = ["name", "size?", "class?"];

    get iconClass() {
        return `o_nextbot_icon ${this.props.class || ""}`;
    }
}

export class ConversationList extends Component {
    static template = "nextbot_workspace.ConversationList";
    static components = { CarbonIcon };
    static props = [
        "conversations",
        "activeId?",
        "search",
        "loading",
        "menuId?",
        "renamingId?",
        "renameDraft?",
        "protectedId?",
        "onSearch",
        "onNew",
        "onSelect",
        "onToggleMenu",
        "onStartRename",
        "onRenameInput",
        "onCommitRename",
        "onRenameKeydown",
        "onArchive",
        "onDelete",
        "onClose?",
    ];

    relative(value) {
        return formatRelative(value);
    }

    isProtected(conversation) {
        return Boolean(this.props.protectedId && conversation.id === this.props.protectedId);
    }
}

export class ResultCard extends Component {
    static template = "nextbot_workspace.ResultCard";
    static components = { CarbonIcon };
    static props = ["card", "onApproval", "onOpenRecord"];

    setup() {
        this.state = useState({ approvalDetailsOpen: false });
    }

    get kind() {
        const value = String(
            this.props.card?.type ||
                this.props.card?.kind ||
                this.props.card?.card_type ||
                "result"
        ).toLowerCase();
        if (value.includes("approval")) return "approval";
        if (value.includes("quotation") || value.includes("quote")) return "quotation";
        if (value.includes("report") || value.includes("table")) return "report";
        if (value.includes("artifact") || value.includes("file")) return "artifact";
        if (value.includes("record")) return "record";
        if (value.includes("error")) return "error";
        return "result";
    }

    get title() {
        const card = this.props.card || {};
        if (this.kind === "approval" && this.approvalOperations.length === 1) {
            return this.approvalOperationTitle(this.approvalOperations[0]);
        }
        return card.title || card.name || card.display_name || this.preview?.title || {
            approval: "Approval required",
            quotation: "Quotation",
            report: "Report",
            artifact: "Artifact",
            record: "ERP record",
            error: "Unable to complete",
            result: "Result",
        }[this.kind];
    }

    get subtitle() {
        const card = this.props.card || {};
        if (this.kind === "approval" && this.preview) {
            // The structured preview shows the details; the flattened legacy
            // summary would just repeat them as one noisy line.
            return "";
        }
        const value = card.subtitle || card.summary || card.description || card.text || "";
        return typeof value === "string" && value.length > 400 ? `${value.slice(0, 400)}…` : value;
    }

    get fields() {
        const card = this.props.card || {};
        const raw =
            card.fields ||
            card.values ||
            (!Array.isArray(card.data) && card.data) ||
            (!Array.isArray(card.result) && card.result) ||
            {};
        if (Array.isArray(raw)) {
            return raw.slice(0, 12).map((entry, index) => ({
                key: entry.key || entry.label || index,
                label: entry.label || entry.key || "Value",
                value: entry.value ?? "",
            }));
        }
        if (!raw || typeof raw !== "object") return [];
        return Object.entries(raw)
            .filter(([, value]) => !Array.isArray(value))
            .slice(0, 12)
            .map(([key, value]) => ({
                key,
                label: key.replaceAll("_", " "),
                value: typeof value === "object" ? safeJson(value) : value,
            }));
    }

    get rows() {
        const card = this.props.card || {};
        const candidates = [
            card.rows,
            card.data,
            card.result,
            card.data?.records,
            card.result?.records,
            card.data?.products,
            card.result?.products,
            card.data?.quotations,
            card.result?.quotations,
            card.data?.orders,
            card.result?.orders,
        ];
        const rows = candidates.find(Array.isArray) || [];
        return rows.slice(0, 50);
    }

    get columns() {
        const columns = this.props.card?.columns;
        if (Array.isArray(columns) && columns.length) {
            return columns.slice(0, 12).map((column) =>
                typeof column === "string"
                    ? { key: column, label: column.replaceAll("_", " ") }
                    : { key: column.key || column.name, label: column.label || column.name || column.key }
            );
        }
        const [first] = this.rows;
        if (first && typeof first === "object") {
            // Technical keys don't help humans; ids still power the row click.
            const keys = Object.keys(first).filter((key) => !["id", "display_name"].includes(key));
            return (keys.length ? keys : Object.keys(first))
                .slice(0, 12)
                .map((key) => ({ key, label: key.replaceAll("_", " ") }));
        }
        return this.rows.length ? [{ key: "__value__", label: "Value" }] : [];
    }

    get approvalState() {
        return String(this.props.card?.status || this.props.card?.state || "pending").toLowerCase();
    }

    get canResolve() {
        return ["pending", "requested", "waiting"].includes(this.approvalState);
    }

    get href() {
        return safeUrl(
            this.props.card?.download_url || this.props.card?.url || this.props.card?.href || ""
        );
    }

    get total() {
        const card = this.props.card || {};
        return card.formatted_total || card.total || card.amount_total || "";
    }

    get quoteLines() {
        const lines = this.props.card?.lines;
        return Array.isArray(lines) ? lines.slice(0, 10) : [];
    }

    get preview() {
        const preview = this.props.card?.preview;
        return preview && typeof preview === "object" ? preview : null;
    }

    get previewLines() {
        const lines = this.preview?.lines;
        return Array.isArray(lines) ? lines.slice(0, 10) : [];
    }

    get previewSample() {
        const sample = this.preview?.sample;
        return Array.isArray(sample) ? sample.slice(0, 10) : [];
    }

    get previewValues() {
        const values = this.preview?.values;
        if (!values || typeof values !== "object") return [];
        return Object.entries(values).map(([key, value]) => ({
            key,
            label: key.replaceAll("_", " "),
            value: typeof value === "object" ? safeJson(value) : String(value),
        }));
    }

    get approvalOperations() {
        return approvalOperationsForCard(this.props.card);
    }

    get showApprovalDetails() {
        return this.canResolve || this.approvalState === "executing" || this.state.approvalDetailsOpen;
    }

    toggleApprovalDetails() {
        this.state.approvalDetailsOpen = !this.state.approvalDetailsOpen;
    }

    approvalOperationTitle(operation) {
        if (this.canResolve) return operation.summary;
        if (this.approvalState === "approved") {
            const verb = operation.action === "create"
                ? "Created"
                : operation.action === "update" ? "Updated" : "Completed";
            return `${verb} ${operation.count} ${operation.modelLabel} record${operation.count === 1 ? "" : "s"}`;
        }
        if (this.approvalState === "executing") return `Applying ${operation.proposalCount} ERP change${operation.proposalCount === 1 ? "" : "s"}…`;
        if (this.approvalState === "rejected") return "Change request rejected";
        if (this.approvalState === "failed") return "Approved change failed";
        if (this.approvalState === "expired") return "Approval expired";
        if (this.approvalState === "superseded") return "Replaced by a newer proposal";
        return operation.summary;
    }

    approvalOperationStatus(operation) {
        const skipped = operation.skippedCount ? ` · ${operation.skippedCount} duplicate${operation.skippedCount === 1 ? "" : "s"} skipped` : "";
        if (this.approvalState === "approved") {
            const verb = operation.action === "update" ? "updated" : operation.action === "create" ? "created" : "completed";
            return `${operation.count} ${verb}${skipped}`;
        }
        if (this.approvalState === "rejected") return "Not applied";
        if (this.approvalState === "failed") return "Failed";
        if (this.approvalState === "expired") return "Expired";
        if (this.approvalState === "superseded") return "Not applied";
        const verb = operation.action === "update" ? "update" : operation.action === "create" ? "create" : "apply";
        return `${operation.proposalCount} to ${verb}${skipped}`;
    }

    approvalDetailsLabel(operation) {
        if (this.state.approvalDetailsOpen) return "Hide product details";
        const noun = operation.modelLabel === "Product" ? "products" : "records";
        return `View ${operation.count} ${operation.action === "create" ? "created " : ""}${noun}`;
    }

    approvalResolutionLabel() {
        return {
            approved: "Changes completed",
            rejected: "Request rejected — no changes made",
            failed: "The approved change failed",
            expired: "Approval expired — no changes made",
            superseded: "Replaced by a newer proposal",
        }[this.approvalState] || this.approvalState;
    }

    approvalItemRecordId(item) {
        return Number(item?.id || item?.res_id || item?.record_id || 0);
    }

    canOpenApprovalItem(operation, item) {
        return Boolean(operation.model && this.approvalItemRecordId(item));
    }

    openApprovalItem(operation, item) {
        if (!this.canOpenApprovalItem(operation, item)) return;
        this.props.onOpenRecord({
            res_model: operation.model,
            res_id: this.approvalItemRecordId(item),
            title: this.approvalItemName(item),
        });
    }

    approvalItemName(item) {
        if (!item || typeof item !== "object") return String(item || "Record");
        return item.name || item.display_name || item.default_code || "Record";
    }

    approvalItemMeta(item) {
        if (!item || typeof item !== "object") return "";
        const details = [];
        if (item.default_code && item.default_code !== item.name) {
            details.push(`Reference: ${item.default_code}`);
        }
        if (item.list_price !== undefined && item.list_price !== null) {
            const price = Number(item.list_price);
            details.push(`Sales price: ${Number.isFinite(price) ? price.toLocaleString() : item.list_price}`);
        }
        if (item.sale_ok === true) details.push("For sale");
        if (item.purchase_ok === true) details.push("Purchasable");
        if (item.description_sale) details.push(item.description_sale);
        return details.join(" · ");
    }

    approvalSkippedName(item) {
        return item?.name || item?.default_code || "Duplicate record";
    }

    approvalSkippedMeta(item) {
        const matched = item?.matched_name || "an existing ERP record";
        const reference = item?.default_code ? ` · Reference: ${item.default_code}` : "";
        return `Already exists as ${matched}${reference}`;
    }

    get textContent() {
        const card = this.props.card || {};
        const value = card.preview || card.content;
        return typeof value === "string" ? value : "";
    }

    fieldValue(row, column) {
        if (column.key === "__value__") return row ?? "";
        const value = row?.[column.key];
        if (Array.isArray(value) && value.length === 2 && typeof value[1] === "string") {
            return value[1]; // many2one [id, name] → show the name
        }
        return typeof value === "object" ? safeJson(value) : value ?? "";
    }

    get rowModel() {
        const card = this.props.card || {};
        return card.res_model || card.model || card.resource?.model || "";
    }

    canOpenRow(row) {
        return Boolean(this.rowModel && row && typeof row === "object" && Number(row.id));
    }

    openRow(row) {
        if (!this.canOpenRow(row)) return;
        this.props.onOpenRecord({
            res_model: this.rowModel,
            res_id: Number(row.id),
            title: row.name || row.display_name || "",
        });
    }

    safeJson(value) {
        return safeJson(value);
    }

    formatBytes(value) {
        return formatBytes(value);
    }

    get fileKind() {
        const mimetype = String(this.props.card?.mime_type || this.props.card?.mimetype || "").toLowerCase();
        if (mimetype.includes("pdf")) return "PDF document";
        if (mimetype.includes("csv")) return "CSV spreadsheet";
        if (mimetype.startsWith("image/")) return "Image";
        if (mimetype.includes("json")) return "JSON data";
        return mimetype || "Generated file";
    }
}

export class MessageBubble extends Component {
    static template = "nextbot_workspace.MessageBubble";
    static components = { CarbonIcon, ResultCard };
    static props = [
        "message",
        "isLastAssistant?",
        "onCopy",
        "onRegenerate",
        "onApproval",
        "onOpenRecord",
    ];

    isFeaturedCard(card) {
        return isUserFacingCard(card);
    }

    get actionCards() {
        return this.props.message.cards.filter((card) => this.isFeaturedCard(card));
    }

    get body() {
        return safeMarkdown(this.props.message?.content || "");
    }

    get time() {
        return formatClock(this.props.message?.createdAt);
    }

    get isAssistant() {
        return this.props.message?.role !== "user";
    }

    attachmentHref(attachment) {
        return safeUrl(attachment?.url || attachment?.download_url || "");
    }

    attachmentName(attachment) {
        return typeof attachment === "string"
            ? attachment
            : attachment?.name || attachment?.filename || "Attachment";
    }
}

export class TaskProgress extends Component {
    static template = "nextbot_workspace.TaskProgress";
    static components = { CarbonIcon };
    static props = ["task", "status", "pauseReason?", "onContinue", "onStop"];

    get steps() {
        return Array.isArray(this.props.task?.steps) ? this.props.task.steps : [];
    }

    get progress() {
        return this.props.task?.progress || { completed: 0, total: this.steps.length, percent: 0 };
    }

    get canContinue() {
        return this.props.status === "waiting_input" && this.props.pauseReason === "budget";
    }

    get isTerminal() {
        return ["completed", "partial", "failed", "cancelled", "interrupted"].includes(
            this.props.status
        );
    }

    get statusLabel() {
        return {
            queued: "Queued",
            planning: "Planning",
            running: "Working",
            waiting_input: "Waiting for input",
            waiting_approval: "Waiting for approval",
            verifying: "Verifying",
            completed: "Completed",
            partial: "Partially completed",
            failed: "Failed",
            cancelled: "Cancelled",
            interrupted: "Interrupted",
        }[this.props.status] || "Working";
    }

    stepLabel(step) {
        return {
            pending: "Pending",
            queued: "Queued",
            running: "Working",
            completed: "Done",
            failed: "Failed",
            skipped: "Skipped",
            cancelled: "Cancelled",
        }[step.status] || step.status || "Pending";
    }
}

export class ActivityInspector extends Component {
    static template = "nextbot_workspace.ActivityInspector";
    static components = { CarbonIcon, ResultCard };
    static props = [
        "tab",
        "events",
        "tools",
        "sources",
        "artifacts",
        "running",
        "onSelectTab",
        "onClose",
        "onApproval",
        "onOpenRecord",
    ];

    get items() {
        if (this.props.tab === "tools") return this.props.tools;
        if (this.props.tab === "sources") return this.props.sources;
        if (this.props.tab === "artifacts") return this.props.artifacts;
        return this.props.events;
    }

    kind(event) {
        return eventKind(event?.type);
    }

    label(event) {
        return eventLabel(event);
    }

    clock(value) {
        return formatClock(value);
    }

    details(event) {
        return safeJson(
            event?.safe_output ||
                event?.output ||
                event?.result ||
                event?.safe_input ||
                event?.input ||
                event?.arguments
        );
    }

    sourceHref(source) {
        return safeUrl(source?.url || source?.href || "");
    }

    artifactHref(artifact) {
        return safeUrl(artifact?.download_url || artifact?.url || artifact?.href || "");
    }

    approvalCard(event) {
        const approval = event?.payload?.approval || event?.approval;
        if (approval) {
            return {
                ...approval,
                type: "approval",
                status: approval.state || approval.status || "pending",
            };
        }
        return {
            type: "approval",
            id: event?.approval_id || event?.payload?.approval_id,
            status: event?.decision || event?.payload?.decision || "resolved",
            summary: event?.summary || event?.message || "Approval resolved",
        };
    }

    hasApprovalCard(event) {
        return Boolean(event?.payload?.approval || event?.approval);
    }
}

export class NextBotComposer extends Component {
    static template = "nextbot_workspace.NextBotComposer";
    static components = { CarbonIcon };
    static props = [
        "draft",
        "attachments",
        "running",
        "sending",
        "disabled?",
        "onInput",
        "onFiles",
        "onRemoveAttachment",
        "onSend",
        "onStop",
    ];

    setup() {
        this.state = useState({ dragging: false });
        this.inputRef = useRef("input");
        this.fileRef = useRef("files");
    }

    formatBytes(value) {
        return formatBytes(value);
    }

    onComposerInput(event) {
        this.props.onInput(event.target.value);
        this.resizeInput(event.target);
    }

    onKeydown(event) {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            this.submit();
        }
    }

    submit() {
        if (!this.props.sending && !this.props.disabled) {
            this.props.onSend();
        }
    }

    resizeInput(element = this.inputRef.el) {
        if (!element) return;
        element.style.height = "auto";
        element.style.height = `${Math.min(element.scrollHeight, 176)}px`;
    }

    openFilePicker() {
        this.fileRef.el?.click();
    }

    onFileInput(event) {
        this.props.onFiles(Array.from(event.target.files || []));
        event.target.value = "";
    }

    onPaste(event) {
        const files = Array.from(event.clipboardData?.files || []);
        if (files.length) {
            this.props.onFiles(files);
        }
    }

    onDragOver(event) {
        event.preventDefault();
        if (!this.props.sending) this.state.dragging = true;
    }

    onDragLeave(event) {
        if (!event.currentTarget.contains(event.relatedTarget)) {
            this.state.dragging = false;
        }
    }

    onDrop(event) {
        event.preventDefault();
        this.state.dragging = false;
        if (!this.props.sending) {
            this.props.onFiles(Array.from(event.dataTransfer?.files || []));
        }
    }
}
