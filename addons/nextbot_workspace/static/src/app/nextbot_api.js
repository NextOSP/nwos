/** @odoo-module **/

import {
    asArray,
    normalizeConversation,
    normalizeEvent,
    normalizeMessage,
    unwrapResult,
} from "./nextbot_utils";
import { browser } from "@web/core/browser/browser";

export const NEXTBOT_ROUTES = Object.freeze({
    bootstrap: "/nextbot/bootstrap",
    conversations: "/nextbot/conversations",
    startRun: "/nextbot/runs",
    uploadAttachment: "/mail/attachment/upload",
    tools: "/nextbot/tools",
});

/**
 * Thin transport adapter. Keeping route and envelope normalization here lets
 * the workspace remain stable while server-side providers evolve.
 */
export class NextBotApi {
    constructor(rpc) {
        this.rpc = rpc;
    }

    async bootstrap() {
        const result = unwrapResult(await this.rpc(NEXTBOT_ROUTES.bootstrap, {}));
        return {
            ...result,
            conversations: asArray(result.conversations).map(normalizeConversation),
            tools: asArray(result.tools),
        };
    }

    async listConversations(query = "") {
        const result = unwrapResult(
            await this.rpc(NEXTBOT_ROUTES.conversations, { search: query, limit: 80 })
        );
        return asArray(result.conversations ?? result.items ?? result).map(normalizeConversation);
    }

    async createConversation() {
        const result = unwrapResult(await this.rpc(NEXTBOT_ROUTES.conversations, { create: true }));
        return normalizeConversation(result.conversation || result);
    }

    async updateConversation(conversationId, values) {
        const result = unwrapResult(
            await this.rpc(`/nextbot/conversations/${encodeURIComponent(conversationId)}`, {
                name: values.name ?? values.title,
                archived: values.archived,
            })
        );
        return normalizeConversation(result.conversation || result);
    }

    async deleteConversation(conversationId) {
        return this.rpc(`/nextbot/conversations/${encodeURIComponent(conversationId)}`, {
            delete: true,
        });
    }

    async loadMessages(conversationId, { before = null, limit = 60 } = {}) {
        const result = unwrapResult(
            await this.rpc(`/nextbot/conversations/${encodeURIComponent(conversationId)}/messages`, {
                before,
                limit,
            })
        );
        return {
            messages: asArray(result.messages ?? result.items ?? result).map(normalizeMessage),
            events: asArray(result.events).map(normalizeEvent),
            hasMore: Boolean(result.has_more || result.hasMore),
            cursor: result.cursor || result.next_cursor || null,
        };
    }

    uploadAttachment(file, channelId, onProgress = () => {}) {
        const request = new browser.XMLHttpRequest();
        const formData = new FormData();
        formData.append("csrf_token", globalThis.nwos?.csrf_token || "");
        formData.append("ufile", file);
        formData.append("thread_id", channelId);
        formData.append("thread_model", "discuss.channel");
        formData.append("is_pending", "false");
        formData.append("temporary_id", String(-Date.now()));
        formData.append("tmp_url", "");
        const promise = new Promise((resolve, reject) => {
            request.open("POST", NEXTBOT_ROUTES.uploadAttachment);
            request.upload.addEventListener("progress", (event) => {
                if (event.lengthComputable) {
                    onProgress(Math.round((event.loaded / event.total) * 100));
                }
            });
            request.addEventListener("load", () => {
                let response;
                try {
                    response = JSON.parse(request.responseText || request.response || "{}");
                } catch {
                    reject(new Error("The attachment server returned an invalid response."));
                    return;
                }
                if (request.status < 200 || request.status >= 300 || response.error) {
                    reject(new Error(response.error?.message || response.error || "Attachment upload failed."));
                    return;
                }
                const data = unwrapResult(response);
                const attachment = data.attachment || data;
                resolve({
                    ...attachment,
                    id: attachment.id || attachment.attachment_id,
                    name: attachment.name || file.name,
                    mimetype: attachment.mimetype || file.type,
                });
            });
            request.addEventListener("error", () => reject(new Error("Attachment upload failed.")));
            request.send(formData);
        });
        promise.abort = () => request.abort();
        return promise;
    }

    async startRun(payload) {
        return unwrapResult(await this.rpc(NEXTBOT_ROUTES.startRun, payload));
    }

    async getRun(runId) {
        return unwrapResult(await this.rpc(`/nextbot/runs/${encodeURIComponent(runId)}`, {}));
    }

    async steerRun(runId, payload) {
        return unwrapResult(
            await this.rpc(`/nextbot/runs/${encodeURIComponent(runId)}/input`, {
                message: payload.prompt ?? payload.message ?? payload.content,
                attachment_ids: payload.attachment_ids || [],
            })
        );
    }

    async continueRun(runId) {
        return unwrapResult(
            await this.rpc(`/nextbot/runs/${encodeURIComponent(runId)}/continue`, {})
        );
    }

    async regenerateRun(runId) {
        return unwrapResult(await this.rpc(`/nextbot/runs/${encodeURIComponent(runId)}/regenerate`, {}));
    }

    async cancelRun(runId) {
        return this.rpc(`/nextbot/runs/${encodeURIComponent(runId)}/cancel`, {});
    }

    async pollEvents(runId, after = 0) {
        const result = unwrapResult(
            await this.rpc(
                `/nextbot/runs/${encodeURIComponent(runId)}/events`,
                { after, limit: 100 },
                { silent: true }
            )
        );
        return {
            events: asArray(result.events ?? result.items ?? result).map(normalizeEvent),
            status: result.status || result.run_status,
            cursor: Number(result.cursor ?? result.next_after ?? result.last_sequence ?? after),
            retryAfter: Number(result.retry_after_ms || 650),
            hasMore: Boolean(result.has_more),
        };
    }

    async resolveApproval(approvalId, decision) {
        return unwrapResult(
            await this.rpc(
                `/nextbot/approvals/${encodeURIComponent(approvalId)}/${
                    decision === "approve" ? "approve" : "reject"
                }`,
                {}
            )
        );
    }

    async listTools() {
        const result = unwrapResult(await this.rpc(NEXTBOT_ROUTES.tools, {}));
        return asArray(result.tools ?? result.items ?? result);
    }

    eventStreamUrl(runId, after = 0) {
        return `/nextbot/runs/${encodeURIComponent(runId)}/events?after=${encodeURIComponent(after || 0)}`;
    }
}
