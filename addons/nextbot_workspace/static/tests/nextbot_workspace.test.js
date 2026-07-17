import { describe, expect, test } from "@nwos/hoot";

import { NextBotApi } from "@nextbot_workspace/app/nextbot_api";
import {
    approvalOperationsForCard,
    isUserFacingCard,
} from "@nextbot_workspace/components/nextbot_components";
import {
    eventKind,
    eventLabel,
    foldApprovalEvents,
    needsBackfill,
    normalizeMarkdownTables,
    normalizeConversation,
    normalizeEvent,
    normalizeMessage,
    normalizeTask,
    projectTaskEvent,
    redactValue,
    safeMarkdown,
    safeUrl,
} from "@nextbot_workspace/app/nextbot_utils";

describe.current.tags("headless");

test("normalizes the backend conversation and preserves its Discuss channel", () => {
    const conversation = normalizeConversation({
        id: 4,
        channel_id: 19,
        name: "Quarter close",
        active: true,
        last_activity_at: "2026-07-11 10:15:00",
    });

    expect(conversation).toMatchObject({
        id: 4,
        channelId: 19,
        title: "Quarter close",
        archived: false,
        updatedAt: "2026-07-11 10:15:00",
    });
});

test("prefers a message plaintext projection over its Discuss HTML body", () => {
    const message = normalizeMessage({
        id: 8,
        role: "assistant",
        body: "<p>Hello <strong>world</strong></p>",
        text: "Hello world",
    });

    expect(message.content).toBe("Hello world");
    expect(safeMarkdown(message.content).toString()).toBe("Hello world");
});

test("repairs short model-generated Markdown table separators", () => {
    const malformed = [
        "| Code | Product | Price |",
        "|--|---|--|",
        "| A-1 | Example | 100 |",
    ].join("\n");

    expect(normalizeMarkdownTables(malformed).includes("| --- | --- | --- |")).toBe(true);
    expect(safeMarkdown(malformed).toString().includes("<table")).toBe(true);
});

test("joins completed approval results to products so rows can open ERP records", () => {
    const [operation] = approvalOperationsForCard({
        id: 9,
        state: "approved",
        preview: {
            type: "batch",
            operations: [{
                id: 30,
                tool: "prepare_create_records",
                summary: "Create 1 Product record(s).",
                preview: {
                    type: "bulk_change",
                    action: "create",
                    model: "product.template",
                    model_label: "Product",
                    count: 1,
                    sample: [{ name: "Example", default_code: "SKU-1" }],
                },
            }],
        },
        operations: [{
            id: 30,
            tool: "prepare_create_records",
            state: "completed",
            result: {
                model: "product.template",
                created_count: 1,
                record_ids: [77],
                records: [{ id: 77, name: "Example", default_code: "SKU-1" }],
            },
        }],
    });

    expect(operation.action).toBe("create");
    expect(operation.count).toBe(1);
    expect(operation.model).toBe("product.template");
    expect(operation.sample[0].id).toBe(77);
});

test("redacts sensitive nested tool arguments", () => {
    expect(
        redactValue({
            model: "sale.order",
            token: "top-secret",
            nested: { api_key: "also-secret", limit: 5 },
        })
    ).toEqual({
        model: "sale.order",
        token: "[redacted]",
        nested: { api_key: "[redacted]", limit: 5 },
    });
});

test("normalizes durable events and labels backend tool payloads", () => {
    const event = normalizeEvent({
        id: 11,
        sequence: 3,
        type: "tool.completed",
        payload: { tool: "search_records" },
    });

    expect(eventKind(event.type)).toBe("tool");
    expect(eventLabel(event)).toBe("Finished search_records");
});

test("projects durable plan and step events into task progress", () => {
    let task = projectTaskEvent(null, normalizeEvent({
        id: 1,
        sequence: 1,
        type: "task.plan.created",
        payload: {
            task: {
                goal: "Review overdue invoices",
                plan_revision: 1,
                steps: [
                    { id: 10, key: "find", title: "Find invoices", status: "queued" },
                    { id: 11, key: "summarize", title: "Summarize", status: "pending" },
                ],
            },
        },
    }));
    task = projectTaskEvent(task, normalizeEvent({
        id: 2,
        sequence: 2,
        type: "task.step.status",
        payload: { step: { id: 10, key: "find", title: "Find invoices", status: "completed" } },
    }));

    expect(eventKind("task.step.status")).toBe("task");
    expect(task.goal).toBe("Review overdue invoices");
    expect(task.steps[0].status).toBe("completed");
    expect(task.progress).toEqual({ completed: 1, total: 2, percent: 50 });
    expect(normalizeTask(task).plan_revision).toBe(1);
});

test("folds approval lifecycle and tool outcomes into the required card", () => {
    const events = [
        normalizeEvent({
            id: 1,
            sequence: 1,
            type: "approval.required",
            payload: { approval: { id: 41, state: "pending", summary: "Update record" } },
        }),
        normalizeEvent({
            id: 2,
            sequence: 2,
            type: "approval.resolved",
            payload: { approval_id: 41, decision: "approved" },
        }),
        normalizeEvent({
            id: 3,
            sequence: 3,
            type: "tool.failed",
            payload: { approval_id: 41, message: "Write rejected by ACL" },
        }),
        normalizeEvent({
            id: 4,
            sequence: 4,
            type: "approval.required",
            payload: { approval: { id: 42, state: "pending", summary: "Create quote" } },
        }),
        normalizeEvent({
            id: 5,
            sequence: 5,
            type: "tool.completed",
            payload: { approval_id: 42, result: { id: 9 } },
        }),
        normalizeEvent({
            id: 6,
            sequence: 6,
            type: "approval.required",
            payload: { approval: { id: 43, state: "pending", summary: "Old proposal" } },
        }),
        normalizeEvent({
            id: 7,
            sequence: 7,
            type: "approval.superseded",
            payload: { approval_id: 43 },
        }),
    ];

    const folded = foldApprovalEvents(events);
    expect(folded[0].payload.approval.state).toBe("failed");
    expect(folded[3].payload.approval.state).toBe("approved");
    expect(folded[5].payload.approval.state).toBe("superseded");
});

test("folds completed execution records into approvals after a reload", () => {
    const events = [
        normalizeEvent({
            id: 1,
            sequence: 1,
            type: "approval.required",
            payload: {
                approval: {
                    id: 9,
                    state: "pending",
                    operations: [{ id: 30, state: "proposed", result: false }],
                },
            },
        }),
        normalizeEvent({
            id: 2,
            sequence: 2,
            type: "tool.completed",
            payload: {
                approval_id: 9,
                execution_id: 30,
                result: {
                    model: "product.template",
                    records: [{ id: 77, display_name: "Example" }],
                },
            },
        }),
    ];

    const [approvalEvent] = foldApprovalEvents(events);
    expect(approvalEvent.payload.approval.state).toBe("approved");
    expect(approvalEvent.payload.approval.operations[0].result.records[0].id).toBe(77);
});

test("keeps generic tool cards and artifact downloads in normalized events", () => {
    const event = normalizeEvent({
        id: 20,
        sequence: 8,
        type: "tool.completed",
        payload: {
            card: {
                type: "artifact",
                name: "Sales export",
                download_url: "/web/content/90?download=true",
            },
        },
    });

    expect(event.card.name).toBe("Sales export");
    expect(safeUrl(event.card.download_url)).toBe("/web/content/90?download=true");
});

test("keeps internal ERP evidence out of chat while preserving user-facing cards", () => {
    expect(isUserFacingCard({
        type: "report",
        rows: [{ id: 1, name: "Units" }],
        res_model: "uom.uom",
    })).toBe(false);
    expect(isUserFacingCard({ type: "approval", id: 5 })).toBe(true);
    expect(isUserFacingCard({
        type: "artifact",
        name: "Product import report",
        download_url: "/web/content/42?download=true",
    })).toBe(true);
});

test("applies contiguous bus events and polls to backfill gaps", () => {
    // Duplicate or in-order pushes are applied (the dedupe set absorbs replays).
    expect(needsBackfill(4, 5)).toBe(false);
    expect(needsBackfill(4, 4)).toBe(false);
    expect(needsBackfill(0, 1)).toBe(false);
    // A skipped sequence or an oversized placeholder must not advance the
    // cursor past unfetched events.
    expect(needsBackfill(4, 6)).toBe(true);
    expect(needsBackfill(0, 3)).toBe(true);
    expect(needsBackfill(4, 5, true)).toBe(true);
});

test("normalizes a bus-pushed serialized event like a polled one", () => {
    const event = normalizeEvent({
        id: 33,
        run_id: 7,
        sequence: 2,
        type: "assistant.text.delta",
        timestamp: "2026-07-12T08:00:00+00:00",
        payload: { delta: "Hel" },
    });

    expect(event.sequence).toBe(2);
    expect(event.type).toBe("assistant.text.delta");
    expect(event.delta).toBe("Hel");
    expect(event.createdAt).toBe("2026-07-12T08:00:00+00:00");
});

test("rejects executable URLs while allowing authenticated relative links", () => {
    expect(safeUrl("javascript:alert(1)")).toBe("");
    expect(safeUrl("/web/content/42?download=true")).toBe("/web/content/42?download=true");
});

test("poll adapter uses the canonical cursor endpoint and preserves pagination", async () => {
    const calls = [];
    const api = new NextBotApi(async (route, params, settings) => {
        calls.push({ route, params, settings });
        return {
            status: "completed",
            events: [{ id: 1, sequence: 100, type: "assistant.text.delta", payload: { delta: "x" } }],
            next_after: 100,
            has_more: true,
        };
    });

    const result = await api.pollEvents(7, 0);
    expect(calls[0].route).toBe("/nextbot/runs/7/events");
    expect(calls[0].params).toEqual({ after: 0, limit: 100 });
    expect(calls[0].settings).toEqual({ silent: true });
    expect(result.cursor).toBe(100);
    expect(result.hasMore).toBe(true);
});

test("run adapter steers and continues the same durable task", async () => {
    const calls = [];
    const api = new NextBotApi(async (route, params) => {
        calls.push({ route, params });
        return { id: 7, status: "queued" };
    });

    await api.steerRun(7, { prompt: "Use only posted invoices", attachment_ids: [3] });
    await api.continueRun(7);
    expect(calls[0]).toEqual({
        route: "/nextbot/runs/7/input",
        params: { message: "Use only posted invoices", attachment_ids: [3] },
    });
    expect(calls[1]).toEqual({ route: "/nextbot/runs/7/continue", params: {} });
});
