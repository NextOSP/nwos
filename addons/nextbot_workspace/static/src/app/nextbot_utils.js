/** @odoo-module **/

import { markup } from "@nwos/owl";
import { nwosmark } from "@web/core/utils/html";

const SECRET_KEY = /(?:pass(?:word)?|secret|token|api[_-]?key|authorization|cookie|credential)/i;
const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

export function asArray(value) {
    if (Array.isArray(value)) {
        return value;
    }
    return value ? [value] : [];
}

export function unwrapResult(value) {
    if (value && typeof value === "object" && value.data && typeof value.data === "object") {
        return value.data;
    }
    return value || {};
}

export function normalizeConversation(raw = {}) {
    const id = raw.id ?? raw.channel_id ?? raw.conversation_id;
    return {
        ...raw,
        id,
        channelId: raw.channel_id ?? raw.channelId,
        title: raw.title || raw.name || "New conversation",
        updatedAt:
            raw.updated_at ||
            raw.last_activity_at ||
            raw.last_activity ||
            raw.write_date ||
            raw.create_date,
        preview: raw.preview || raw.last_message || "",
        archived: Boolean(raw.archived || raw.is_archived || raw.active === false),
        unread: Number(raw.unread || raw.unread_count || 0),
    };
}

export function normalizeMessage(raw = {}) {
    const role = raw.role || (raw.is_bot || raw.author_type === "bot" ? "assistant" : "user");
    return {
        ...raw,
        id: raw.id ?? raw.message_id ?? `message-${Math.random().toString(36).slice(2)}`,
        role,
        // The workspace renders safe plaintext/limited markdown. Prefer the
        // server's explicit text projection over its Discuss HTML body.
        content: raw.content ?? raw.text ?? raw.body ?? "",
        createdAt: raw.created_at || raw.date || raw.create_date,
        cards: asArray(raw.cards || raw.result_cards || raw.card),
        attachments: asArray(raw.attachments || raw.attachment_ids),
        sources: asArray(raw.sources),
        status: raw.status || "complete",
    };
}

export function normalizeEvent(raw = {}, fallbackSequence = 0) {
    const payload = raw.payload && typeof raw.payload === "object" ? raw.payload : {};
    return {
        ...payload,
        ...raw,
        id: raw.id ?? raw.event_id ?? `${raw.run_id || "run"}-${raw.sequence ?? fallbackSequence}`,
        sequence: Number(raw.sequence ?? raw.seq ?? fallbackSequence),
        type: String(raw.type || raw.event || payload.type || "activity").toLowerCase(),
        createdAt: raw.created_at || raw.timestamp || payload.created_at || new Date().toISOString(),
        status: raw.status || payload.status,
        payload,
    };
}

export function normalizeTask(raw = {}) {
    const steps = asArray(raw.steps).map((step, index) => ({
        ...step,
        key: step.key || `step-${step.id || index}`,
        status: step.status || "pending",
        type: step.type || step.step_type || "read",
    }));
    const completed = steps.filter((step) =>
        ["completed", "skipped", "cancelled"].includes(step.status)
    ).length;
    return {
        ...raw,
        goal: raw.goal || "Current task",
        status: raw.status || "queued",
        steps,
        progress: {
            completed: Number(raw.progress?.completed ?? completed),
            total: Number(raw.progress?.total ?? steps.length),
            percent: Number(
                raw.progress?.percent ?? (steps.length ? Math.round((completed * 100) / steps.length) : 0)
            ),
        },
    };
}

/** Project durable task events without mutating the prior snapshot. */
export function projectTaskEvent(current, event = {}) {
    const type = String(event.type || "").toLowerCase();
    const payload = event.payload && typeof event.payload === "object" ? event.payload : event;
    if ((type === "task.plan.created" || type === "task.plan.revised") && payload.task) {
        return normalizeTask(payload.task);
    }
    const task = normalizeTask(current || {});
    if (type === "task.step.status" && payload.step) {
        const step = {
            ...payload.step,
            key: payload.step.key || `step-${payload.step.id}`,
            status: payload.step.status || "pending",
            type: payload.step.type || payload.step.step_type || "read",
        };
        const index = task.steps.findIndex(
            (item) => item.id === step.id || (step.key && item.key === step.key)
        );
        const steps = [...task.steps];
        if (index < 0) steps.push(step);
        else steps[index] = { ...steps[index], ...step };
        return normalizeTask({ ...task, steps, progress: null });
    }
    if (type === "task.verification") {
        return normalizeTask({
            ...task,
            verification: {
                passed: Boolean(payload.passed),
                criteria: asArray(payload.criteria),
                completed_steps: Number(payload.completed_steps || 0),
            },
        });
    }
    if (type === "task.input.required") {
        return normalizeTask({ ...task, pendingQuestion: payload.question || event.question || "" });
    }
    if (type === "run.status" && (payload.status || event.status)) {
        return normalizeTask({ ...task, status: payload.status || event.status });
    }
    return task;
}

export function needsBackfill(cursor, sequence, fetchRequired = false) {
    // A pushed event may only be applied when it directly follows the cursor;
    // anything else (gap, oversized placeholder) must go through the ordered
    // cursor poll, which only reads events strictly after the cursor.
    return Boolean(fetchRequired) || Number(sequence || 0) > Number(cursor || 0) + 1;
}

export function eventKind(type = "") {
    const value = String(type).toLowerCase().replaceAll("_", ".").replaceAll(":", ".");
    if (value.includes("approval")) {
        return "approval";
    }
    if (value.includes("artifact")) {
        return "artifact";
    }
    if (value.includes("source") || value.includes("citation")) {
        return "source";
    }
    if (value.includes("tool")) {
        return "tool";
    }
    if (value.startsWith("task.")) {
        return "task";
    }
    if (value.includes("error") || value.includes("failed")) {
        return "error";
    }
    if (value.includes("complete") || value.includes("done")) {
        return "complete";
    }
    if (value.includes("delta")) {
        return "delta";
    }
    return "activity";
}

export function redactValue(value, depth = 0, seen = new WeakSet()) {
    if (depth > 5) {
        return "[truncated]";
    }
    if (value === null || value === undefined || typeof value === "boolean" || typeof value === "number") {
        return value;
    }
    if (typeof value === "string") {
        return value.length > 4000 ? `${value.slice(0, 4000)}…` : value;
    }
    if (typeof value !== "object") {
        return String(value);
    }
    if (seen.has(value)) {
        return "[circular]";
    }
    seen.add(value);
    if (Array.isArray(value)) {
        return value.slice(0, 50).map((item) => redactValue(item, depth + 1, seen));
    }
    const output = {};
    for (const [key, item] of Object.entries(value).slice(0, 80)) {
        output[key] = SECRET_KEY.test(key) ? "[redacted]" : redactValue(item, depth + 1, seen);
    }
    return output;
}

export function safeJson(value) {
    if (value === undefined || value === null || value === "") {
        return "";
    }
    if (typeof value === "string") {
        return value;
    }
    try {
        return JSON.stringify(redactValue(value), null, 2);
    } catch {
        return "[unavailable]";
    }
}

export function normalizeMarkdownTables(value) {
    const lines = String(value || "").split("\n");
    for (let index = 1; index < lines.length; index++) {
        const header = lines[index - 1].trim();
        const separator = lines[index].trim();
        if (!header.includes("|") || !separator.includes("|")) continue;
        const cells = (line) => line
            .replace(/^\s*\|/, "")
            .replace(/\|\s*$/, "")
            .split("|")
            .map((cell) => cell.trim());
        const headerCells = cells(header);
        const separatorCells = cells(separator);
        if (
            headerCells.length < 2 ||
            headerCells.length !== separatorCells.length ||
            !separatorCells.every((cell) => /^:?-+:?$/.test(cell))
        ) {
            continue;
        }
        lines[index] = `| ${separatorCells.map((cell) => {
            const left = cell.startsWith(":");
            const right = cell.endsWith(":");
            return `${left ? ":" : ""}---${right ? ":" : ""}`;
        }).join(" | ")} |`;
    }
    return lines.join("\n");
}

export function safeMarkdown(value) {
    const lines = normalizeMarkdownTables(value).split("\n");
    const output = [];
    let textLines = [];
    const flushText = () => {
        if (!textLines.length) return;
        output.push(nwosmark(textLines.join("\n")).toString());
        textLines = [];
    };
    const cells = (line) => line
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((cell) => cell.trim());
    for (let index = 0; index < lines.length; index++) {
        const header = cells(lines[index]);
        const separator = index + 1 < lines.length ? cells(lines[index + 1]) : [];
        const isTable =
            lines[index].includes("|") &&
            header.length >= 2 &&
            header.length === separator.length &&
            separator.every((cell) => /^:?-{3,}:?$/.test(cell));
        if (!isTable) {
            textLines.push(lines[index]);
            continue;
        }
        flushText();
        const rows = [];
        index += 2;
        while (index < lines.length && lines[index].includes("|")) {
            const row = cells(lines[index]);
            if (row.length !== header.length) break;
            rows.push(row);
            index += 1;
        }
        index -= 1;
        const renderCell = (cell, tag) => `<${tag}>${nwosmark(cell).toString()}</${tag}>`;
        output.push(
            '<div class="o_nextbot_markdown_table"><table><thead><tr>' +
            header.map((cell) => renderCell(cell, "th")).join("") +
            "</tr></thead><tbody>" +
            rows.map((row) => `<tr>${row.map((cell) => renderCell(cell, "td")).join("")}</tr>`).join("") +
            "</tbody></table></div>"
        );
    }
    flushText();
    return markup(output.join(""));
}

export function safeUrl(value, { allowRelative = true } = {}) {
    const url = String(value || "").trim();
    if (!url) {
        return "";
    }
    if (allowRelative && url.startsWith("/") && !url.startsWith("//")) {
        return url;
    }
    try {
        const parsed = new URL(url, window.location.origin);
        return SAFE_PROTOCOLS.has(parsed.protocol) ? parsed.href : "";
    } catch {
        return "";
    }
}

export function formatClock(value) {
    if (!value) {
        return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(date);
}

export function formatRelative(value, now = Date.now()) {
    if (!value) {
        return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    const delta = Math.max(0, now - date.getTime());
    if (delta < 60_000) {
        return "Now";
    }
    if (delta < 3_600_000) {
        return `${Math.floor(delta / 60_000)}m`;
    }
    if (delta < 86_400_000) {
        return `${Math.floor(delta / 3_600_000)}h`;
    }
    if (delta < 7 * 86_400_000) {
        return `${Math.floor(delta / 86_400_000)}d`;
    }
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

export function formatBytes(value) {
    const bytes = Number(value || 0);
    if (!bytes) {
        return "0 B";
    }
    const units = ["B", "KB", "MB", "GB"];
    const power = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const amount = bytes / 1024 ** power;
    return `${amount >= 10 || power === 0 ? amount.toFixed(0) : amount.toFixed(1)} ${units[power]}`;
}

export function eventLabel(event) {
    const type = String(event?.type || "").toLowerCase();
    if (event?.summary || event?.label || event?.message) {
        return event.summary || event.label || event.message;
    }
    if (type.includes("tool") && (event.tool_name || event.tool || event.name)) {
        const verb = type.includes("complete") ? "Finished" : type.includes("fail") ? "Could not run" : "Using";
        return `${verb} ${event.tool_name || event.tool || event.name}`;
    }
    if (type.includes("approval")) {
        const decision = event.decision || event.payload?.decision;
        if (type.includes("resolved") && decision) {
            return `Approval ${decision}`;
        }
        return "Approval required";
    }
    if (type === "task.plan.created") return "Created a task plan";
    if (type === "task.plan.revised") return "Revised the task plan";
    if (type === "task.step.status") {
        const step = event.step || event.payload?.step;
        return step?.title ? `${step.title}: ${step.status || "updated"}` : "Updated a plan step";
    }
    if (type === "task.verification") return "Verified the completed task";
    if (type === "task.input.required") return "Waiting for your input";
    if (type.includes("artifact")) {
        return "Created an artifact";
    }
    if (type.includes("source")) {
        return "Found a source";
    }
    if (type.includes("complete")) {
        return "Response completed";
    }
    if (type.includes("error") || type.includes("fail")) {
        return "Something went wrong";
    }
    return "Working on your request";
}

/**
 * Reconcile immutable approval.required events with later lifecycle events.
 * The event log intentionally does not mutate old payloads, so clients need
 * this projection to avoid presenting a stale approval button after reload.
 */
export function foldApprovalEvents(events = []) {
    const approvalStates = new Map();
    const approvalResults = new Map();
    const ordered = events
        .map((event, index) => ({ event, index }))
        .sort(
            (left, right) =>
                Number(left.event?.sequence || 0) - Number(right.event?.sequence || 0) ||
                left.index - right.index
        );
    for (const { event } of ordered) {
        const type = String(event?.type || "").toLowerCase();
        const approval = event?.approval || event?.payload?.approval;
        if (approval?.id) {
            approvalStates.set(approval.id, approval.state || approval.status || "pending");
        }
        const approvalId = event?.approval_id || event?.payload?.approval_id;
        if (!approvalId) continue;
        if (type === "approval.resolved") {
            approvalStates.set(
                approvalId,
                event?.decision || event?.payload?.decision || "resolved"
            );
        } else if (type === "approval.superseded") {
            approvalStates.set(approvalId, "superseded");
        } else if (type === "tool.started") {
            approvalStates.set(approvalId, "executing");
        } else if (type === "tool.completed") {
            approvalStates.set(approvalId, "approved");
            const executionId = event?.execution_id || event?.payload?.execution_id;
            const result = event?.result || event?.payload?.result;
            if (executionId && result && typeof result === "object") {
                const results = approvalResults.get(approvalId) || new Map();
                results.set(executionId, result);
                approvalResults.set(approvalId, results);
            }
        } else if (type === "tool.failed") {
            approvalStates.set(approvalId, "failed");
        }
    }
    if (!approvalStates.size) return events;
    return events.map((event) => {
        const approval = event?.approval || event?.payload?.approval;
        const state = approval?.id && approvalStates.get(approval.id);
        if (!approval || !state) return event;
        const results = approvalResults.get(approval.id);
        const operations = Array.isArray(approval.operations)
            ? approval.operations.map((operation) => {
                const result = results?.get(operation.id);
                return result ? { ...operation, state: "completed", result } : operation;
            })
            : approval.operations;
        const updated = { ...approval, operations, state, status: state };
        return {
            ...event,
            approval: updated,
            payload: { ...event.payload, approval: updated },
        };
    });
}
