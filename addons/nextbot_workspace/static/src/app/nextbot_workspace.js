/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    useRef,
    useState,
} from "@nwos/owl";

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

import { NextBotApi } from "./nextbot_api";
import {
    asArray,
    eventKind,
    foldApprovalEvents,
    needsBackfill,
    normalizeConversation,
    normalizeEvent,
    normalizeMessage,
    normalizeTask,
    projectTaskEvent,
} from "./nextbot_utils";
import {
    ActivityInspector,
    CarbonIcon,
    ConversationList,
    MessageBubble,
    NextBotComposer,
    TaskProgress,
} from "../components/nextbot_components";

const TERMINAL_RUN_STATES = new Set(["completed", "partial", "failed", "cancelled", "interrupted"]);
const ACTIVE_RUN_STATES = new Set([
    "queued",
    "planning",
    "running",
    "waiting_input",
    "waiting_approval",
    "verifying",
]);
const BUS_RUN_EVENT = "nextbot.run/event";
// With bus push the poll is only a lazy reconciliation/fallback loop.
const POLL_DELAY_BUS_MS = 5000;
const POLL_DELAY_FALLBACK_MS = 650;
const DEFAULT_ATTACHMENT_COUNT = 5;
const DEFAULT_ATTACHMENT_BYTES = 20 * 1024 * 1024;
const MAX_RENDERED_MESSAGES = 1000;

export class NextBotWorkspace extends Component {
    static template = "nextbot_workspace.NextBotWorkspace";
    static components = {
        ActivityInspector,
        CarbonIcon,
        ConversationList,
        MessageBubble,
        NextBotComposer,
        TaskProgress,
    };
    static props = { ...standardActionServiceProps };
    static displayName = _t("NextBot");
    static path = "nextbot";

    setup() {
        this.rpc = rpc;
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.busService = useService("bus_service");
        this.api = new NextBotApi(this.rpc);

        this.scrollRef = useRef("messageScroll");
        this.state = useState({
            conversations: [],
            activeConversationId: null,
            messages: [],
            events: [],
            availableTools: [],
            search: "",
            draft: "",
            attachments: [],
            loadingConversations: true,
            loadingMessages: false,
            loadingOlder: false,
            sending: false,
            hasMoreMessages: false,
            messageCursor: null,
            error: null,
            activeRun: null,
            activeTask: null,
            runConnection: "idle",
            inspectorOpen: false,
            inspectorTab: "activity",
            historyOpen: false,
            conversationMenuId: null,
            renamingConversationId: null,
            renameDraft: "",
            eventTransport: "cursor_polling",
            maxAttachments: DEFAULT_ATTACHMENT_COUNT,
            maxAttachmentBytes: DEFAULT_ATTACHMENT_BYTES,
        });

        this.messageCache = new Map();
        this.eventCache = new Map();
        this.historyMeta = new Map();
        this.taskCache = new Map();
        this.seenEventKeys = new Set();
        this.searchTimer = null;
        this.pollTimer = null;
        this.pollFailures = 0;
        this.pendingDelta = "";
        this.deltaFrame = null;
        this.scrollFrame = null;
        this.loadToken = 0;
        this.stickToBottom = true;
        this.busConnected = false;
        this._globalKeydown = (event) => this.onGlobalKeydown(event);
        this._onBusRunEvent = (payload) => this.onBusRunEvent(payload);
        this._onBusConnect = () => this.onBusConnectionChange(true);
        this._onBusDisconnect = () => this.onBusConnectionChange(false);

        onWillStart(() => this.bootstrap());
        onMounted(() => {
            browser.addEventListener("keydown", this._globalKeydown);
            this.busService.subscribe(BUS_RUN_EVENT, this._onBusRunEvent);
            this.busService.addEventListener("BUS:CONNECT", this._onBusConnect);
            this.busService.addEventListener("BUS:RECONNECT", this._onBusConnect);
            this.busService.addEventListener("BUS:DISCONNECT", this._onBusDisconnect);
            this.busService.start();
            this.scrollToBottom(false);
        });
        onWillUnmount(() => this.cleanup());
    }

    get currentConversation() {
        return this.state.conversations.find(
            (conversation) => conversation.id === this.state.activeConversationId
        );
    }

    get currentTitle() {
        return this.currentConversation?.title || "New conversation";
    }

    get filteredConversations() {
        const needle = this.state.search.trim().toLocaleLowerCase();
        if (!needle) return this.state.conversations;
        return this.state.conversations.filter((conversation) =>
            `${conversation.title} ${conversation.preview || ""}`.toLocaleLowerCase().includes(needle)
        );
    }

    get visibleMessages() {
        return this.state.messages.slice(-MAX_RENDERED_MESSAGES);
    }

    get hiddenMessageCount() {
        return Math.max(0, this.state.messages.length - this.visibleMessages.length);
    }

    get lastAssistantId() {
        return [...this.state.messages].reverse().find((message) => message.role !== "user")?.id;
    }

    get currentRun() {
        return this.state.activeRun?.conversationId === this.state.activeConversationId
            ? this.state.activeRun
            : null;
    }

    get isRunning() {
        return Boolean(this.currentRun && ACTIVE_RUN_STATES.has(this.currentRun.status));
    }

    get runStatusLabel() {
        return {
            queued: "Queued",
            planning: "Planning your task",
            running: "Working on your task",
            waiting_input: "Waiting for your input",
            waiting_approval: "Waiting for approval",
            verifying: "Verifying the result",
        }[this.state.activeRun?.status] || "Working on your task";
    }

    get activityEvents() {
        return this.state.events.filter((event) => {
            const type = String(event.type || "");
            return eventKind(type) !== "delta" && type !== "assistant.text.completed";
        });
    }

    get toolEvents() {
        return this.state.events.filter((event) => eventKind(event.type) === "tool");
    }

    get sources() {
        const sources = [];
        for (const event of this.state.events) {
            if (eventKind(event.type) !== "source") continue;
            sources.push(...asArray(event.source || event.sources || event.payload?.source || event.payload?.sources || event.payload));
        }
        for (const message of this.state.messages) {
            sources.push(...asArray(message.sources));
        }
        return this.uniqueItems(sources, (item) => item?.id || item?.url || item?.title || item?.name);
    }

    get artifacts() {
        const artifacts = [];
        for (const event of this.state.events) {
            if (eventKind(event.type) === "artifact") {
                artifacts.push(...asArray(event.artifact || event.payload?.artifact || event.payload));
            }
        }
        for (const message of this.state.messages) {
            artifacts.push(
                ...message.cards.filter((card) =>
                    String(card.type || card.kind || "").toLowerCase().includes("artifact")
                )
            );
        }
        return this.uniqueItems(artifacts, (item) => item?.id || item?.download_url || item?.name);
    }

    isRawDataArtifact(artifact) {
        return String(artifact?.mime_type || artifact?.mimetype || "").includes("json");
    }

    uniqueItems(items, keyFn) {
        const seen = new Set();
        return items.filter((item) => {
            if (!item || typeof item !== "object") return false;
            const key = keyFn(item) || JSON.stringify(item);
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }

    async bootstrap() {
        this.state.loadingConversations = true;
        this.state.error = null;
        try {
            const result = await this.api.bootstrap();
            this.state.conversations = result.conversations;
            this.state.availableTools = result.tools;
            this.state.eventTransport = result.features?.event_transport || "cursor_polling";
            this.state.maxAttachments = Number(result.limits?.attachment_count || DEFAULT_ATTACHMENT_COUNT);
            this.state.maxAttachmentBytes =
                Number(result.limits?.attachment_size_mb || 20) * 1024 * 1024;
            const requestedId =
                this.props.action?.params?.conversation_id ||
                this.props.action?.context?.active_conversation_id;
            const initial = result.conversations.find((item) => item.id === requestedId) || result.conversations[0];
            if (initial) {
                await this.selectConversation(initial.id, { closeHistory: false });
            }
        } catch (error) {
            this.state.error = this.errorMessage(error, "NextBot could not be loaded.");
        } finally {
            this.state.loadingConversations = false;
        }
    }

    async refreshConversations(query = this.state.search, { silent = false } = {}) {
        if (!silent) this.state.loadingConversations = true;
        try {
            const conversations = await this.api.listConversations(query);
            if (!query && this.currentConversation && !conversations.some((item) => item.id === this.currentConversation.id)) {
                conversations.unshift(this.currentConversation);
            }
            this.state.conversations = conversations;
        } catch (error) {
            if (!silent) this.state.error = this.errorMessage(error, "Conversation history could not be loaded.");
        } finally {
            if (!silent) this.state.loadingConversations = false;
        }
    }

    onSearch(value) {
        this.state.search = value;
        if (this.searchTimer) browser.clearTimeout(this.searchTimer);
        this.searchTimer = browser.setTimeout(() => this.refreshConversations(value, { silent: true }), 280);
    }

    async createConversation() {
        this.state.conversationMenuId = null;
        try {
            const conversation = await this.api.createConversation();
            this.state.conversations = [
                conversation,
                ...this.state.conversations.filter((item) => item.id !== conversation.id),
            ];
            this.messageCache.set(conversation.id, []);
            this.eventCache.set(conversation.id, []);
            await this.selectConversation(conversation.id);
        } catch (error) {
            this.notification.add(this.errorMessage(error, "Could not create a conversation."), {
                type: "danger",
            });
        }
    }

    async selectConversation(conversationId, { closeHistory = true } = {}) {
        if (!conversationId) return;
        const token = ++this.loadToken;
        this.state.activeConversationId = conversationId;
        this.state.conversationMenuId = null;
        if (closeHistory) this.state.historyOpen = false;
        this.state.error = null;
        this.state.messages = this.messageCache.get(conversationId) || [];
        this.state.events = this.eventCache.get(conversationId) || [];
        this.state.activeTask = this.taskCache.get(conversationId) || null;

        if (this.messageCache.has(conversationId)) {
            this.applyHistoryMeta(conversationId);
            this.scrollToBottom(false);
            return;
        }

        this.state.loadingMessages = true;
        try {
            const result = await this.api.loadMessages(conversationId);
            if (token !== this.loadToken) return;
            this.setMessages(conversationId, result.messages);
            this.setEvents(conversationId, result.events);
            this.historyMeta.set(conversationId, {
                hasMore: result.hasMore,
                cursor: result.cursor,
            });
            this.applyHistoryMeta(conversationId);
            await this.hydrateLatestRun(conversationId, result.messages);
            this.scrollToBottom(false);
        } catch (error) {
            if (token === this.loadToken) {
                this.state.error = this.errorMessage(error, "Messages could not be loaded.");
            }
        } finally {
            if (token === this.loadToken) this.state.loadingMessages = false;
        }
    }

    async hydrateLatestRun(conversationId, messages) {
        const runMessage = [...messages].reverse().find((message) => message.run_id);
        if (!runMessage) return;
        try {
            const run = await this.api.getRun(runMessage.run_id);
            const events = asArray(run.events).map(normalizeEvent);
            this.setEvents(conversationId, events);
            this.setTask(conversationId, run.task);
            this.decorateMessagesFromEvents(conversationId, events);
            if (ACTIVE_RUN_STATES.has(run.status) && !this.state.activeRun) {
                this.resumeRun(
                    runMessage.run_id,
                    conversationId,
                    run.status,
                    Number(run.event_sequence || events.at(-1)?.sequence || 0),
                    run.task,
                    run.pause_reason
                );
            }
        } catch {
            // Message history remains fully usable if old run details were pruned.
        }
    }

    decorateMessagesFromEvents(conversationId, events) {
        const cards = [];
        const sources = [];
        const approvals = new Map();
        for (const event of foldApprovalEvents(events)) {
            if (eventKind(event.type) === "approval") {
                const approval = event.approval || event.payload?.approval;
                if (approval) {
                    approvals.set(approval.id, {
                        ...approval,
                        type: "approval",
                        status: approval.state,
                    });
                }
            } else if (eventKind(event.type) === "artifact") {
                const artifact = event.artifact || event.payload?.artifact;
                // Raw JSON tool dumps stay in the inspector's Artifacts tab;
                // only user-facing files (reports, documents) belong in chat.
                if (artifact && !this.isRawDataArtifact(artifact)) {
                    cards.push({ ...artifact, type: "artifact" });
                }
            } else if (eventKind(event.type) === "source") {
                sources.push(...asArray(event.source || event.sources || event.payload?.source || event.payload?.sources));
            }
            const structuredCards = asArray(
                event.cards ||
                    event.card ||
                    event.result_card ||
                    event.payload?.cards ||
                    event.payload?.card
            );
            cards.push(...structuredCards);
        }
        cards.unshift(...approvals.values());
        if (!cards.length && !sources.length) return;
        const messages = [...(this.messageCache.get(conversationId) || [])];
        let index = -1;
        for (let cursor = messages.length - 1; cursor >= 0; cursor--) {
            if (messages[cursor].role !== "user") {
                index = cursor;
                break;
            }
        }
        if (index < 0) return;
        messages[index] = {
            ...messages[index],
            cards: this.uniqueItems([...messages[index].cards, ...cards], (item) => item.download_url || item.id || item.name),
            sources: this.uniqueItems([...messages[index].sources, ...sources], (item) => item.id || item.url),
        };
        this.setMessages(conversationId, messages);
    }

    resumeRun(runId, conversationId, status, cursor = 0, task = null, pauseReason = null) {
        const messages = this.messageCache.get(conversationId) || [];
        let assistant = [...messages].reverse().find(
            (message) => message.role !== "user" && message.run_id === runId
        );
        if (!assistant) {
            assistant = normalizeMessage({
                id: `run-${runId}-assistant`,
                role: "assistant",
                content: "",
                status: "streaming",
                run_id: runId,
                cards: [],
            });
            this.setMessages(conversationId, [...messages, assistant]);
        }
        this.state.activeRun = {
            id: runId,
            conversationId,
            assistantMessageId: assistant.id,
            cursor,
            status,
            pauseReason,
        };
        if (task) this.setTask(conversationId, task);
        this.seenEventKeys = new Set(
            (this.eventCache.get(conversationId) || []).map((event) => `${runId}:${event.sequence}:${event.id}`)
        );
        this.startRunTransport();
    }

    applyHistoryMeta(conversationId) {
        const meta = this.historyMeta.get(conversationId) || {};
        const loadedCount = (this.messageCache.get(conversationId) || []).length;
        this.state.hasMoreMessages = Boolean(meta.hasMore && loadedCount < MAX_RENDERED_MESSAGES);
        this.state.messageCursor = meta.cursor || null;
    }

    async loadOlderMessages() {
        if (
            !this.state.hasMoreMessages ||
            this.state.loadingOlder ||
            this.isRunning ||
            !this.currentConversation
        ) {
            return;
        }
        const conversationId = this.currentConversation.id;
        const loadedAtStart = this.messageCache.get(conversationId) || [];
        const remainingCapacity = MAX_RENDERED_MESSAGES - loadedAtStart.length;
        if (remainingCapacity <= 0) {
            this.state.hasMoreMessages = false;
            return;
        }
        const scroll = this.scrollRef.el;
        const previousHeight = scroll?.scrollHeight || 0;
        this.state.loadingOlder = true;
        try {
            const result = await this.api.loadMessages(conversationId, {
                before: this.state.messageCursor,
                limit: Math.min(60, remainingCapacity),
            });
            const current = this.messageCache.get(conversationId) || [];
            const ids = new Set(current.map((message) => message.id));
            const older = result.messages.filter((message) => !ids.has(message.id));
            const combined = [...older, ...current];
            this.setMessages(conversationId, combined);
            this.historyMeta.set(conversationId, {
                hasMore: result.hasMore && combined.length < MAX_RENDERED_MESSAGES,
                cursor: result.cursor,
            });
            this.applyHistoryMeta(conversationId);
            if (scroll) {
                requestAnimationFrame(() => {
                    scroll.scrollTop += scroll.scrollHeight - previousHeight;
                });
            }
        } catch (error) {
            this.notification.add(this.errorMessage(error, "Older messages could not be loaded."), {
                type: "warning",
            });
        } finally {
            this.state.loadingOlder = false;
        }
    }

    setMessages(conversationId, messages) {
        const normalized = messages.map((message) =>
            message?.content !== undefined && message?.cards ? message : normalizeMessage(message)
        );
        this.messageCache.set(conversationId, normalized);
        if (conversationId === this.state.activeConversationId) this.state.messages = normalized;
    }

    setEvents(conversationId, events) {
        const normalized = events.map((event, index) =>
            event?.createdAt && event?.type ? event : normalizeEvent(event, index)
        );
        this.eventCache.set(conversationId, foldApprovalEvents(normalized).slice(-600));
        if (conversationId === this.state.activeConversationId) {
            this.state.events = this.eventCache.get(conversationId);
        }
    }

    setTask(conversationId, task) {
        if (!conversationId || !task) return;
        const normalized = normalizeTask(task);
        this.taskCache.set(conversationId, normalized);
        if (conversationId === this.state.activeConversationId) {
            this.state.activeTask = normalized;
        }
    }

    async sendMessage() {
        const prompt = this.state.draft.trim();
        if ((!prompt && !this.state.attachments.length) || this.state.sending) return;
        this.state.sending = true;
        this.state.error = null;
        try {
            let conversation = this.currentConversation;
            if (!conversation) {
                conversation = await this.api.createConversation();
                this.state.conversations = [conversation, ...this.state.conversations];
                this.state.activeConversationId = conversation.id;
                this.messageCache.set(conversation.id, []);
                this.eventCache.set(conversation.id, []);
            }

            const uploaded = await Promise.all(
                this.state.attachments.map((attachment) => this.uploadAttachment(attachment, conversation))
            );
            const finalPrompt = prompt || "Please review the attached file(s).";
            const payload = {
                conversation_id: conversation.id,
                prompt: finalPrompt,
                attachment_ids: uploaded.map((attachment) => attachment.id),
            };
            const steering = Boolean(
                this.state.activeRun && this.state.activeRun.conversationId === conversation.id
            );
            const run = steering
                ? await this.api.steerRun(this.state.activeRun.id, payload)
                : await this.api.startRun(payload);

            const userMessage = normalizeMessage({
                id: steering ? `local-user-${Date.now()}` : run.input_message_id || `local-user-${Date.now()}`,
                role: "user",
                content: finalPrompt,
                created_at: new Date().toISOString(),
                attachments: uploaded,
                run_id: run.id,
            });
            this.setMessages(conversation.id, [
                ...(this.messageCache.get(conversation.id) || []),
                userMessage,
            ]);
            this.updateConversationPreview(conversation.id, finalPrompt);
            this.state.draft = "";
            this.clearAttachments();
            this.beginRun(run, conversation.id, { steering });
            this.scrollToBottom(true);
        } catch (error) {
            this.state.error = this.errorMessage(error, "Your message could not be sent.");
            for (const attachment of this.state.attachments) {
                if (attachment.status === "uploading") attachment.status = "error";
            }
        } finally {
            this.state.sending = false;
        }
    }

    beginRun(run, conversationId, { steering = false } = {}) {
        const runId = run.id || run.run_id;
        const status = run.status || "queued";
        if (steering && this.state.activeRun?.id === runId) {
            this.flushDelta();
            const priorAssistantId = this.state.activeRun.assistantMessageId;
            const priorMessages = [...(this.messageCache.get(conversationId) || [])];
            const priorIndex = priorMessages.findIndex((message) => message.id === priorAssistantId);
            if (priorIndex >= 0) {
                const prior = priorMessages[priorIndex];
                if (prior.content || prior.cards?.length) {
                    priorMessages[priorIndex] = { ...prior, status: "complete" };
                } else {
                    priorMessages.splice(priorIndex, 1);
                }
                this.setMessages(conversationId, priorMessages);
            }
        }
        const approvals = asArray(run.approvals).map((approval) => ({
            ...approval,
            type: "approval",
            status: approval.state,
        }));
        const artifacts = asArray(run.artifacts)
            .filter((artifact) => !this.isRawDataArtifact(artifact))
            .map((artifact) => ({ ...artifact, type: "artifact" }));
        const assistant = normalizeMessage({
            id: steering
                ? `run-${runId}-assistant-${Date.now()}`
                : run.response_message_id || `run-${runId}-assistant`,
            role: "assistant",
            content: steering ? "" : run.response || run.response_text || "",
            status: TERMINAL_RUN_STATES.has(status) ? (status === "failed" ? "error" : "complete") : "streaming",
            error: run.error,
            run_id: runId,
            cards: [...approvals, ...artifacts],
        });
        this.setMessages(conversationId, [
            ...(this.messageCache.get(conversationId) || []),
            assistant,
        ]);
        if (!steering) this.setEvents(conversationId, []);
        this.setTask(conversationId, run.task || { goal: run.goal || run.prompt, status });
        this.state.activeRun = {
            id: runId,
            conversationId,
            assistantMessageId: assistant.id,
            cursor: 0,
            status,
            pauseReason: run.pause_reason || null,
        };
        if (!steering) this.seenEventKeys = new Set();
        for (const event of asArray(run.events)) this.processEvent(normalizeEvent(event));

        if (TERMINAL_RUN_STATES.has(status)) {
            this.finishRun(status, { text: run.response || run.response_text, message: run.error });
        } else {
            this.startRunTransport();
        }
    }

    startRunTransport() {
        this.stopRunTransport();
        if (!this.state.activeRun) return;
        this.state.runConnection = this.busConnected ? "streaming" : "polling";
        this.schedulePoll(this.busConnected ? POLL_DELAY_BUS_MS : 0);
    }

    onBusRunEvent(payload) {
        if (!payload || !payload.run_id) return;
        const activeRun = this.state.activeRun;
        if (!activeRun) {
            // A run started (or progressed) in another tab on the conversation
            // currently on screen: attach to it, unless it is already over.
            const status = payload.event?.payload?.status;
            const isTerminal =
                payload.event?.type === "run.status" && TERMINAL_RUN_STATES.has(status);
            if (payload.conversation_id === this.state.activeConversationId && !isTerminal) {
                this.resumeRun(payload.run_id, payload.conversation_id, "running", 0);
            }
            return;
        }
        if (payload.run_id !== activeRun.id) return;
        const sequence = payload.event?.sequence || payload.sequence || 0;
        if (needsBackfill(activeRun.cursor, sequence, payload.fetch_required)) {
            this.schedulePoll(0);
            return;
        }
        this.processEvent(normalizeEvent(payload.event));
    }

    onBusConnectionChange(connected) {
        this.busConnected = connected;
        if (!this.state.activeRun) return;
        this.state.runConnection = connected ? "streaming" : "polling";
        // Reconnect: poll immediately for an authoritative catch-up, then the
        // lazy cadence resumes. Disconnect: fall back to tight polling.
        this.schedulePoll(connected ? 0 : 250);
    }

    schedulePoll(delay) {
        if (this.pollTimer) browser.clearTimeout(this.pollTimer);
        if (!this.state.activeRun) return;
        this.pollTimer = browser.setTimeout(() => this.pollRun(), Math.max(0, delay));
    }

    async pollRun() {
        const activeRun = this.state.activeRun;
        if (!activeRun) return;
        try {
            const result = await this.api.pollEvents(activeRun.id, activeRun.cursor);
            if (this.state.activeRun?.id !== activeRun.id) return;
            this.pollFailures = 0;
            this.state.runConnection = this.busConnected ? "streaming" : "polling";
            for (const event of result.events) this.processEvent(event, { deferTerminal: true });
            if (!this.state.activeRun || this.state.activeRun.id !== activeRun.id) return;
            this.state.activeRun.cursor = Math.max(this.state.activeRun.cursor, result.cursor || 0);
            this.state.activeRun.status = result.status || this.state.activeRun.status;
            if (result.hasMore) {
                this.schedulePoll(0);
            } else if (TERMINAL_RUN_STATES.has(result.status)) {
                this.finishRun(result.status);
            } else if (this.busConnected) {
                this.schedulePoll(POLL_DELAY_BUS_MS);
            } else {
                const delay = result.status === "waiting_approval" ? 1400 : result.retryAfter;
                this.schedulePoll(delay || POLL_DELAY_FALLBACK_MS);
            }
        } catch (error) {
            if (!this.state.activeRun || this.state.activeRun.id !== activeRun.id) return;
            this.pollFailures += 1;
            this.state.runConnection = "reconnecting";
            this.schedulePoll(Math.min(5000, 600 * 2 ** Math.min(this.pollFailures, 3)));
        }
    }

    processEvent(event, { deferTerminal = false } = {}) {
        const activeRun = this.state.activeRun;
        if (!activeRun) return;
        const key = `${activeRun.id}:${event.sequence}:${event.id}`;
        if (this.seenEventKeys.has(key)) return;
        this.seenEventKeys.add(key);
        activeRun.cursor = Math.max(activeRun.cursor || 0, event.sequence || 0);

        const existing = this.eventCache.get(activeRun.conversationId) || [];
        this.setEvents(activeRun.conversationId, [...existing, event]);
        const type = String(event.type || "").toLowerCase();

        if (type.startsWith("task.") || type === "run.status") {
            this.setTask(
                activeRun.conversationId,
                projectTaskEvent(this.taskCache.get(activeRun.conversationId), event)
            );
            if (type === "task.input.required") activeRun.pauseReason = "input";
            if (type === "task.continued") activeRun.pauseReason = null;
        }

        if (type.includes("assistant.text.delta") || type === "assistant.delta") {
            this.queueDelta(event.delta || event.text_delta || event.payload?.delta || "");
            return;
        }
        if (type === "assistant.text.completed") {
            this.flushDelta();
            const text = event.text || event.content || event.payload?.text;
            if (text) this.updateAssistant((message) => ({ ...message, content: text }));
            return;
        }
        if (eventKind(type) === "approval" && (event.approval || event.payload?.approval)) {
            const approval = event.approval || event.payload.approval;
            this.addAssistantCard({ ...approval, type: "approval", status: approval.state });
        }
        if (type === "approval.resolved" && (event.approval_id || event.payload?.approval_id)) {
            this.updateApprovalEverywhere(
                event.approval_id || event.payload.approval_id,
                event.decision || event.payload?.decision || "resolved"
            );
        }
        if (type === "approval.superseded" && (event.approval_id || event.payload?.approval_id)) {
            this.updateApprovalEverywhere(
                event.approval_id || event.payload.approval_id,
                "superseded"
            );
        }
        if (eventKind(type) === "artifact" && (event.artifact || event.payload?.artifact)) {
            const artifact = event.artifact || event.payload.artifact;
            if (!this.isRawDataArtifact(artifact)) {
                this.addAssistantCard({ ...artifact, type: "artifact" });
            }
        }
        const resultCards = asArray(
            event.cards ||
                event.card ||
                event.result_card ||
                event.payload?.cards ||
                event.payload?.card
        );
        for (const resultCard of resultCards) this.addAssistantCard(resultCard);
        const eventApprovalId = event.approval_id || event.payload?.approval_id;
        if (eventApprovalId && type === "tool.started") {
            this.updateApprovalEverywhere(eventApprovalId, "executing");
        } else if (eventApprovalId && type === "tool.completed") {
            this.updateApprovalEverywhere(eventApprovalId, "approved");
        } else if (eventApprovalId && type === "tool.failed") {
            this.updateApprovalEverywhere(eventApprovalId, "failed", {
                error: event.message || event.payload?.message,
            });
        }
        if (eventKind(type) === "source") {
            const sources = asArray(event.source || event.sources || event.payload?.source || event.payload?.sources);
            if (sources.length) {
                this.updateAssistant((message) => ({
                    ...message,
                    sources: this.uniqueItems([...message.sources, ...sources], (item) => item.id || item.url),
                }));
            }
        }
        if (type === "run.error") {
            const errorMessage = event.message || event.error || event.payload?.message;
            this.updateAssistant((message) => ({
                ...message,
                content: message.content || errorMessage || "",
                error: errorMessage || message.error,
            }));
        }
        if (type === "run.status") {
            const status = event.status || event.payload?.status;
            if (status) activeRun.status = status;
            activeRun.pauseReason = event.pause_reason || event.payload?.pause_reason || activeRun.pauseReason;
            if (TERMINAL_RUN_STATES.has(status) && !deferTerminal) this.finishRun(status, event);
        } else if (type === "error" || type === "run.failed") {
            if (!deferTerminal) this.finishRun("failed", event);
        }
        this.scrollToBottom(true);
    }

    queueDelta(delta) {
        if (!delta) return;
        this.pendingDelta += String(delta);
        if (!this.deltaFrame) {
            this.deltaFrame = browser.requestAnimationFrame(() => this.flushDelta());
        }
    }

    flushDelta() {
        if (this.deltaFrame) browser.cancelAnimationFrame(this.deltaFrame);
        this.deltaFrame = null;
        if (!this.pendingDelta || !this.state.activeRun) return;
        const delta = this.pendingDelta;
        this.pendingDelta = "";
        this.updateAssistant((message) => ({ ...message, content: `${message.content || ""}${delta}` }));
        this.scrollToBottom(true);
    }

    updateAssistant(updater) {
        const activeRun = this.state.activeRun;
        if (!activeRun) return;
        const messages = [...(this.messageCache.get(activeRun.conversationId) || [])];
        const index = messages.findIndex((message) => message.id === activeRun.assistantMessageId);
        if (index < 0) return;
        messages[index] = updater(messages[index]);
        this.setMessages(activeRun.conversationId, messages);
    }

    addAssistantCard(card) {
        this.updateAssistant((message) => ({
            ...message,
            cards: this.uniqueItems(
                [...message.cards, card],
                (item) => item.download_url || item.id || `${item.type}:${item.title || item.name}`
            ),
        }));
    }

    finishRun(status, event = {}) {
        if (!this.state.activeRun) return;
        const runId = this.state.activeRun.id;
        const conversationId = this.state.activeRun.conversationId;
        this.flushDelta();
        const finalText = event.text || event.content || event.response || event.payload?.text;
        this.updateAssistant((message) => ({
            ...message,
            content: finalText || message.content,
            status: status === "failed" ? "error" : status === "cancelled" ? "cancelled" : "complete",
            error:
                status === "failed"
                    ? message.error || event.message || event.error || event.payload?.message
                    : message.error,
        }));
        const task = this.taskCache.get(conversationId);
        if (task) this.setTask(conversationId, { ...task, status });
        this.stopRunTransport();
        this.state.activeRun = null;
        this.state.runConnection = "idle";
        this.refreshConversations("", { silent: true });
        this.notification.add(
            status === "failed"
                ? _t("NextBot could not complete the response.")
                : status === "cancelled"
                  ? _t("Response stopped.")
                  : _t("Response ready."),
            { type: status === "failed" ? "danger" : status === "completed" ? "success" : "info" }
        );
        this.seenEventKeys.delete(runId);
    }

    async continueRun() {
        if (!this.state.activeRun) return;
        const active = this.state.activeRun;
        try {
            const run = await this.api.continueRun(active.id);
            this.beginRun(run, active.conversationId, { steering: true });
            this.notification.add(_t("Task resumed."), { type: "info" });
        } catch (error) {
            this.notification.add(this.errorMessage(error, "The task could not be continued."), {
                type: "danger",
            });
        }
    }

    async stopRun() {
        if (!this.state.activeRun) return;
        const runId = this.state.activeRun.id;
        try {
            const result = await this.api.cancelRun(runId);
            for (const approval of asArray(result?.approvals)) {
                this.updateApprovalEverywhere(
                    approval.id,
                    approval.state || "rejected",
                    approval
                );
            }
            this.rejectPendingApprovals(this.state.activeRun?.conversationId);
            if (this.state.activeRun?.id === runId) this.finishRun("cancelled");
        } catch (error) {
            this.notification.add(this.errorMessage(error, "The run could not be stopped."), {
                type: "warning",
            });
        }
    }

    async regenerate(message) {
        if (this.isRunning || this.state.sending || !message?.run_id) return;
        this.state.sending = true;
        try {
            const run = await this.api.regenerateRun(message.run_id);
            // Regeneration reuses the original Discuss input message. Only a
            // new assistant turn is added, keeping UI and persisted history in
            // exact parity without duplicating the user's prompt.
            this.beginRun(run, this.state.activeConversationId);
            this.scrollToBottom(true);
        } catch (error) {
            this.notification.add(this.errorMessage(error, "The response could not be regenerated."), {
                type: "danger",
            });
        } finally {
            this.state.sending = false;
        }
    }

    async resolveApproval(card, decision) {
        const approvalId = card?.approval_id || card?.id;
        if (!approvalId) return;
        this.updateApprovalEverywhere(approvalId, "executing");
        try {
            const result = await this.api.resolveApproval(approvalId, decision);
            const approval = result.approval || result;
            this.updateApprovalEverywhere(approvalId, approval.state || (decision === "approve" ? "approved" : "rejected"), approval);
            if (!this.state.activeRun && approval.run_id) {
                this.resumeRun(approval.run_id, approval.conversation_id || this.state.activeConversationId, "running", 0);
            } else if (this.state.activeRun) {
                this.schedulePoll(0);
            }
        } catch (error) {
            this.updateApprovalEverywhere(approvalId, card.state || card.status || "pending");
            this.notification.add(this.errorMessage(error, "The approval decision could not be saved."), {
                type: "danger",
            });
        }
    }

    updateApprovalEverywhere(approvalId, state, values = {}) {
        const conversationId = this.state.activeRun?.conversationId || this.state.activeConversationId;
        const events = (this.eventCache.get(conversationId) || []).map((event) => {
            const approval = event.approval || event.payload?.approval;
            if (approval?.id !== approvalId) return event;
            const updated = { ...approval, ...values, state, status: state };
            return {
                ...event,
                approval: updated,
                payload: { ...event.payload, approval: updated },
            };
        });
        this.setEvents(conversationId, events);
        const messages = (this.messageCache.get(conversationId) || []).map((message) => ({
            ...message,
            cards: message.cards.map((card) =>
                (card.approval_id || card.id) === approvalId
                    ? { ...card, ...values, state, status: state }
                    : card
            ),
        }));
        this.setMessages(conversationId, messages);
    }

    rejectPendingApprovals(conversationId) {
        if (!conversationId) return;
        const messages = (this.messageCache.get(conversationId) || []).map((message) => ({
            ...message,
            cards: message.cards.map((card) => {
                const state = card.status || card.state;
                return String(card.type || "").includes("approval") &&
                    ["pending", "requested", "waiting", "executing"].includes(state)
                    ? { ...card, state: "rejected", status: "rejected" }
                    : card;
            }),
        }));
        this.setMessages(conversationId, messages);
    }

    async uploadAttachment(attachment, conversation) {
        attachment.status = "uploading";
        attachment.progress = 0;
        try {
            const uploaded = await this.api.uploadAttachment(
                attachment.file,
                conversation.channelId || conversation.channel_id,
                (progress) => {
                    attachment.progress = progress;
                }
            );
            attachment.status = "uploaded";
            attachment.progress = 100;
            return uploaded;
        } catch (error) {
            attachment.status = "error";
            attachment.error = this.errorMessage(error, "Upload failed");
            throw error;
        }
    }

    addFiles(files) {
        const available = this.state.maxAttachments - this.state.attachments.length;
        if (files.length > available) {
            this.notification.add(
                _t("You can attach up to %s files per message.", this.state.maxAttachments),
                { type: "warning" }
            );
        }
        for (const file of files.slice(0, Math.max(0, available))) {
            if (!file.size) {
                this.notification.add(_t("Empty files cannot be attached."), { type: "warning" });
                continue;
            }
            if (file.size > this.state.maxAttachmentBytes) {
                this.notification.add(
                    _t("%s is larger than the %s MB attachment limit.", file.name, Math.round(this.state.maxAttachmentBytes / 1024 / 1024)),
                    { type: "danger" }
                );
                continue;
            }
            const duplicate = this.state.attachments.some(
                (item) => item.name === file.name && item.size === file.size && item.file.lastModified === file.lastModified
            );
            if (duplicate) continue;
            this.state.attachments.push({
                localId: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
                file,
                name: file.name,
                size: file.size,
                type: file.type,
                status: "ready",
                progress: 0,
                previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : "",
            });
        }
    }

    removeAttachment(localId) {
        const attachment = this.state.attachments.find((item) => item.localId === localId);
        if (attachment?.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
        this.state.attachments = this.state.attachments.filter((item) => item.localId !== localId);
    }

    clearAttachments() {
        for (const attachment of this.state.attachments) {
            if (attachment.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
        }
        this.state.attachments = [];
    }

    updateConversationPreview(conversationId, text) {
        this.state.conversations = this.state.conversations.map((conversation) =>
            conversation.id === conversationId
                ? { ...conversation, preview: text.slice(0, 90), updatedAt: new Date().toISOString() }
                : conversation
        );
    }

    startRename(conversation) {
        this.state.conversationMenuId = null;
        this.state.renamingConversationId = conversation.id;
        this.state.renameDraft = conversation.title;
    }

    onRenameKeydown(conversation, event) {
        if (event.key === "Enter") event.currentTarget.blur();
        if (event.key === "Escape") {
            this.state.renamingConversationId = null;
            this.state.renameDraft = "";
        }
    }

    async commitRename(conversation) {
        if (conversation.id !== this.state.renamingConversationId) return;
        const title = this.state.renameDraft.trim();
        this.state.renamingConversationId = null;
        if (!title || title === conversation.title) return;
        try {
            const updated = await this.api.updateConversation(conversation.id, { name: title });
            this.state.conversations = this.state.conversations.map((item) =>
                item.id === conversation.id ? updated : item
            );
        } catch (error) {
            this.notification.add(this.errorMessage(error, "The conversation could not be renamed."), {
                type: "danger",
            });
        }
    }

    async archiveConversation(conversation) {
        this.state.conversationMenuId = null;
        if (this.isConversationRunActive(conversation.id)) {
            this.notifyConversationRunGuard("archive");
            return;
        }
        try {
            await this.api.updateConversation(conversation.id, { archived: true });
            this.state.conversations = this.state.conversations.filter((item) => item.id !== conversation.id);
            if (conversation.id === this.state.activeConversationId) {
                const [next] = this.state.conversations;
                if (next) await this.selectConversation(next.id);
                else this.clearActiveConversation();
            }
        } catch (error) {
            this.notification.add(this.errorMessage(error, "The conversation could not be archived."), {
                type: "danger",
            });
        }
    }

    deleteConversation(conversation) {
        this.state.conversationMenuId = null;
        if (this.isConversationRunActive(conversation.id)) {
            this.notifyConversationRunGuard("delete");
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Delete conversation?"),
            body: _t(
                "This permanently deletes the NextBot workspace conversation and its agent run history. Messages already shared in Discuss may remain there."
            ),
            confirmLabel: _t("Delete"),
            confirmClass: "btn-danger",
            confirm: async () => {
                if (this.isConversationRunActive(conversation.id)) {
                    this.notifyConversationRunGuard("delete");
                    return false;
                }
                await this.api.deleteConversation(conversation.id);
                this.messageCache.delete(conversation.id);
                this.eventCache.delete(conversation.id);
                this.taskCache.delete(conversation.id);
                this.state.conversations = this.state.conversations.filter((item) => item.id !== conversation.id);
                if (conversation.id === this.state.activeConversationId) {
                    const [next] = this.state.conversations;
                    if (next) await this.selectConversation(next.id);
                    else this.clearActiveConversation();
                }
            },
        });
    }

    isConversationRunActive(conversationId) {
        return Boolean(
            this.state.activeRun && this.state.activeRun.conversationId === conversationId
        );
    }

    notifyConversationRunGuard(operation) {
        this.notification.add(
            operation === "archive"
                ? _t("Stop the active NextBot run before archiving this conversation.")
                : _t("Stop the active NextBot run before deleting this conversation."),
            { type: "warning" }
        );
    }

    clearActiveConversation() {
        this.state.activeConversationId = null;
        this.state.messages = [];
        this.state.events = [];
        this.state.activeTask = null;
        this.state.hasMoreMessages = false;
    }

    async copyMessage(message) {
        try {
            await browser.navigator.clipboard.writeText(message.content || "");
            this.notification.add(_t("Response copied."), { type: "success" });
        } catch {
            this.notification.add(_t("The response could not be copied."), { type: "warning" });
        }
    }

    openRecord(card) {
        const resModel = card.res_model || card.model || card.resource?.model;
        const resId = Number(card.res_id || card.record_id || card.resource?.id);
        if (!resModel || !resId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: card.title || card.display_name || _t("Record"),
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            // A dialog keeps the conversation visible behind the record.
            target: "new",
        });
    }

    useStarter(prompt) {
        this.state.draft = prompt;
    }

    onMessageScroll(event) {
        const element = event.currentTarget;
        this.stickToBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 96;
    }

    scrollToBottom(smooth = true) {
        if (!this.stickToBottom && smooth) return;
        if (this.scrollFrame) browser.cancelAnimationFrame(this.scrollFrame);
        this.scrollFrame = browser.requestAnimationFrame(() => {
            const element = this.scrollRef.el;
            if (element) element.scrollTo({ top: element.scrollHeight, behavior: smooth ? "smooth" : "auto" });
            this.scrollFrame = null;
        });
    }

    toggleConversationMenu(conversationId) {
        this.state.conversationMenuId =
            this.state.conversationMenuId === conversationId ? null : conversationId;
    }

    onGlobalKeydown(event) {
        if (event.key !== "Escape") return;
        this.state.conversationMenuId = null;
        this.state.historyOpen = false;
        if (browser.innerWidth < 1200) this.state.inspectorOpen = false;
    }

    closePanels() {
        this.state.historyOpen = false;
        this.state.inspectorOpen = false;
    }

    errorMessage(error, fallback) {
        return error?.data?.message || error?.message || fallback;
    }

    stopRunTransport() {
        if (this.pollTimer) browser.clearTimeout(this.pollTimer);
        this.pollTimer = null;
    }

    cleanup() {
        this.stopRunTransport();
        this.busService.unsubscribe(BUS_RUN_EVENT, this._onBusRunEvent);
        this.busService.removeEventListener("BUS:CONNECT", this._onBusConnect);
        this.busService.removeEventListener("BUS:RECONNECT", this._onBusConnect);
        this.busService.removeEventListener("BUS:DISCONNECT", this._onBusDisconnect);
        if (this.searchTimer) browser.clearTimeout(this.searchTimer);
        if (this.deltaFrame) browser.cancelAnimationFrame(this.deltaFrame);
        if (this.scrollFrame) browser.cancelAnimationFrame(this.scrollFrame);
        browser.removeEventListener("keydown", this._globalKeydown);
        this.clearAttachments();
    }
}

registry.category("actions").add("nextbot_workspace", NextBotWorkspace);
