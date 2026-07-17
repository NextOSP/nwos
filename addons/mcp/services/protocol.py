# Part of NextOSP. See LICENSE file for full copyright and licensing details.

"""Small, synchronous MCP JSON-RPC protocol implementation.

The HTTP transport lives in :mod:`nwos.addons.mcp.controllers.main`.  Keeping
the protocol independent from the request object makes it possible to test the
wire contract without starting an HTTP server and, importantly, does not add an
asyncio runtime to the WSGI/gevent worker.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from typing import Any

from nwos.exceptions import AccessDenied, AccessError, MissingError, UserError


_logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"
LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = (
    LATEST_PROTOCOL_VERSION,
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)


class MCPProtocolError(Exception):
    """An error which is safe to expose on the MCP wire."""

    def __init__(self, code: int, message: str, data: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = dict(data) if data else None


class InvalidRequest(MCPProtocolError):
    def __init__(self, message: str = "Invalid Request"):
        super().__init__(-32600, message)


class MethodNotFound(MCPProtocolError):
    def __init__(self, method: str):
        super().__init__(-32601, "Method not found", {"method": method})


class InvalidParams(MCPProtocolError):
    def __init__(self, message: str = "Invalid method parameters"):
        super().__init__(-32602, message)


class MCPProtocol:
    """Dispatch MCP requests to an ``mcp.gateway`` model recordset.

    ``execution_context`` should return a fresh transaction savepoint.  It is
    entered once per JSON-RPC call, so a failing item in a compatibility batch
    cannot leave the transaction aborted or roll back successful siblings.
    """

    def __init__(
        self,
        gateway: Any,
        *,
        execution_context: Callable[[], Any] | None = None,
        error_callback: Callable[[str, dict[str, Any], Exception, float], None] | None = None,
        success_callback: Callable[[str, dict[str, Any], float], None] | None = None,
        max_batch_size: int = 20,
    ):
        self.gateway = gateway
        self.execution_context = execution_context or nullcontext
        self.error_callback = error_callback
        self.success_callback = success_callback
        self.max_batch_size = max(1, max_batch_size)

    def handle(self, payload: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Return a JSON-RPC response, or ``None`` for notifications.

        JSON-RPC batches are retained for client compatibility even though
        newer MCP revisions discourage batching.  Empty and oversized batches
        are rejected as one invalid request.
        """
        if isinstance(payload, list):
            if not payload:
                return self.error_response(None, InvalidRequest())
            if len(payload) > self.max_batch_size:
                return self.error_response(
                    None,
                    InvalidRequest(f"Batch exceeds the limit of {self.max_batch_size} requests"),
                )
            responses = [self._handle_message(message) for message in payload]
            return [response for response in responses if response is not None] or None
        return self._handle_message(payload)

    def _handle_message(self, message: Any) -> dict[str, Any] | None:
        request_id = self._safe_request_id(message)
        is_notification = self._is_notification(message)
        method = (
            message.get("method", "")
            if isinstance(message, Mapping) and isinstance(message.get("method"), str)
            else ""
        )
        raw_params = message.get("params", {}) if isinstance(message, Mapping) else {}
        params: dict[str, Any] = dict(raw_params) if isinstance(raw_params, Mapping) else {}
        started = time.monotonic()
        try:
            method, params = self._validate_message(message)
            with self.execution_context():
                result = self._dispatch(method, params)
        except MCPProtocolError as exc:
            self._report_error(method, params, time.monotonic() - started, exc)
            return None if is_notification else self.error_response(request_id, exc)
        except (AccessDenied, AccessError) as exc:
            self._report_error(method, params, time.monotonic() - started, exc)
            _logger.info("MCP operation denied", exc_info=True)
            if method == "tools/call":
                return self._tool_error_response(request_id, is_notification, "Permission denied")
            error = MCPProtocolError(-32001, "Permission denied", {"type": "access_error"})
            return None if is_notification else self.error_response(request_id, error)
        except MissingError as exc:
            self._report_error(method, params, time.monotonic() - started, exc)
            if method == "tools/call":
                return self._tool_error_response(
                    request_id, is_notification, "The requested records were not found"
                )
            error = MCPProtocolError(
                -32004,
                "The requested resource was not found",
                {"type": "not_found"},
            )
            return None if is_notification else self.error_response(request_id, error)
        except UserError as exc:
            self._report_error(method, params, time.monotonic() - started, exc)
            # UserError is explicitly intended for end-user display.  Do not
            # expose its class, traceback, record repr, or exception arguments.
            message_text = str(exc).strip() or "The operation could not be completed"
            message_text = message_text[:1000]
            if method == "tools/call":
                return self._tool_error_response(request_id, is_notification, message_text)
            error = MCPProtocolError(
                -32002,
                message_text,
                {"type": "user_error"},
            )
            return None if is_notification else self.error_response(request_id, error)
        except Exception as exc:
            self._report_error(method, params, time.monotonic() - started, exc)
            _logger.exception("Unhandled MCP gateway error")
            error = MCPProtocolError(-32603, "Internal error")
            return None if is_notification else self.error_response(request_id, error)

        self._report_success(method, params, time.monotonic() - started)
        if is_notification:
            return None
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}

    @staticmethod
    def _tool_error_response(
        request_id: str | int | None,
        is_notification: bool,
        message: str,
    ) -> dict[str, Any] | None:
        if is_notification:
            return None
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": message}],
                "isError": True,
            },
        }

    def _report_error(
        self,
        method: str,
        params: dict[str, Any],
        elapsed: float,
        error: Exception | None = None,
    ) -> None:
        if not method or not self.error_callback:
            return
        if error is None:
            return
        try:
            self.error_callback(method, params, error, elapsed * 1000)
        except Exception:
            _logger.exception("Failed to record MCP operation error")

    def _report_success(self, method: str, params: dict[str, Any], elapsed: float) -> None:
        if not method or not self.success_callback:
            return
        try:
            self.success_callback(method, params, elapsed * 1000)
        except Exception:
            _logger.exception("Failed to record MCP operation success")

    @staticmethod
    def _is_notification(message: Any) -> bool:
        """Only a recognizable JSON-RPC request can be a notification.

        In particular, ``{}`` is an invalid request and needs an error response
        with a null id; treating every mapping without ``id`` as a notification
        would incorrectly suppress that response.
        """
        return (
            isinstance(message, Mapping)
            and message.get("jsonrpc") == JSONRPC_VERSION
            and isinstance(message.get("method"), str)
            and bool(message.get("method"))
            and "id" not in message
        )

    @staticmethod
    def _safe_request_id(message: Any) -> str | int | None:
        if not isinstance(message, Mapping):
            return None
        request_id = message.get("id")
        # bool is an int subclass but is not a useful JSON-RPC identifier.
        if request_id is None or (isinstance(request_id, (str, int)) and not isinstance(request_id, bool)):
            return request_id
        return None

    @staticmethod
    def _validate_message(message: Any) -> tuple[str, dict[str, Any]]:
        if not isinstance(message, Mapping):
            raise InvalidRequest()
        if message.get("jsonrpc") != JSONRPC_VERSION:
            raise InvalidRequest("jsonrpc must be '2.0'")
        method = message.get("method")
        if not isinstance(method, str) or not method:
            raise InvalidRequest("method must be a non-empty string")
        if "id" in message:
            request_id = message["id"]
            if request_id is not None and (
                isinstance(request_id, bool) or not isinstance(request_id, (str, int))
            ):
                raise InvalidRequest("id must be a string, integer, or null")
        params = message.get("params", {})
        if not isinstance(params, Mapping):
            raise InvalidParams("params must be an object")
        return method, dict(params)

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "initialize":
            return self._initialize(params)
        if method == "ping":
            return {}
        if method in {"notifications/initialized", "notifications/cancelled", "notifications/progress"}:
            return None
        if method == "tools/list":
            cursor = self._cursor(params)
            return self._list_result(self.gateway.tools_list(cursor=cursor), "tools")
        if method == "tools/call":
            name = self._required_string(params, "name")
            arguments = params.get("arguments", {})
            if not isinstance(arguments, Mapping):
                raise InvalidParams("arguments must be an object")
            return self._tool_result(self.gateway.tools_call(name, dict(arguments)))
        if method == "resources/list":
            cursor = self._cursor(params)
            return self._list_result(self.gateway.resources_list(cursor=cursor), "resources")
        if method == "resources/templates/list":
            cursor = self._cursor(params)
            return self._list_result(
                self.gateway.resource_templates_list(cursor=cursor),
                "resourceTemplates",
            )
        if method == "resources/read":
            uri = self._required_string(params, "uri")
            return self._resource_result(uri, self.gateway.resources_read(uri))
        if method == "prompts/list":
            cursor = self._cursor(params)
            return self._list_result(self.gateway.prompts_list(cursor=cursor), "prompts")
        if method == "prompts/get":
            name = self._required_string(params, "name")
            arguments = params.get("arguments", {})
            if not isinstance(arguments, Mapping):
                raise InvalidParams("arguments must be an object")
            return self._prompt_result(self.gateway.prompts_get(name, dict(arguments)))
        raise MethodNotFound(method)

    @staticmethod
    def _initialize(params: dict[str, Any]) -> dict[str, Any]:
        requested_version = params.get("protocolVersion")
        if not isinstance(requested_version, str) or not requested_version:
            raise InvalidParams("protocolVersion must be a non-empty string")
        capabilities = params.get("capabilities")
        client_info = params.get("clientInfo")
        if not isinstance(capabilities, Mapping):
            raise InvalidParams("capabilities must be an object")
        if not isinstance(client_info, Mapping) or not isinstance(client_info.get("name"), str):
            raise InvalidParams("clientInfo must contain a name")

        negotiated_version = (
            requested_version
            if requested_version in SUPPORTED_PROTOCOL_VERSIONS
            else LATEST_PROTOCOL_VERSION
        )
        return {
            "protocolVersion": negotiated_version,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "nextosp-mcp",
                "title": "NextOSP MCP Gateway",
                "version": "1.0.0",
            },
            "instructions": (
                "Use schema and discovery tools before operating on records. "
                "All operations run with the authenticated NextOSP user's permissions."
            ),
        }

    @staticmethod
    def _cursor(params: dict[str, Any]) -> str | None:
        unknown = set(params) - {"cursor"}
        if unknown:
            raise InvalidParams(f"Unknown parameter: {sorted(unknown)[0]}")
        cursor = params.get("cursor")
        if cursor is not None and not isinstance(cursor, str):
            raise InvalidParams("cursor must be a string")
        return cursor

    @staticmethod
    def _required_string(params: dict[str, Any], key: str) -> str:
        value = params.get(key)
        if not isinstance(value, str) or not value:
            raise InvalidParams(f"{key} must be a non-empty string")
        return value

    @staticmethod
    def _reject_unknown_params(params: dict[str, Any], allowed: set[str]) -> None:
        unknown = set(params) - allowed
        if unknown:
            raise InvalidParams(f"Unknown parameter: {sorted(unknown)[0]}")

    @staticmethod
    def _list_result(value: Any, key: str) -> dict[str, Any]:
        if value is None:
            return {key: []}
        if isinstance(value, Mapping):
            result = dict(value)
            if key not in result:
                raise MCPProtocolError(-32603, "Gateway returned an invalid result")
            return result
        if isinstance(value, (list, tuple)):
            return {key: list(value)}
        raise MCPProtocolError(-32603, "Gateway returned an invalid result")

    @staticmethod
    def _tool_result(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping) and (
            "content" in value or "structuredContent" in value or "isError" in value
        ):
            return dict(value)

        # Generic gateway implementations may return structured data directly.
        # Supply both representations so older and newer MCP clients can use it.
        text = json.dumps(value, ensure_ascii=False, default=str)
        result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
        if isinstance(value, Mapping):
            result["structuredContent"] = dict(value)
        return result

    @staticmethod
    def _resource_result(uri: str, value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            if "contents" in value:
                return dict(value)
            if "text" in value or "blob" in value:
                content = dict(value)
                content.setdefault("uri", uri)
                return {"contents": [content]}
        if isinstance(value, str):
            return {"contents": [{"uri": uri, "text": value}]}
        if isinstance(value, (list, tuple)):
            return {"contents": list(value)}
        raise MCPProtocolError(-32603, "Gateway returned an invalid resource")

    @staticmethod
    def _prompt_result(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping) and "messages" in value:
            return dict(value)
        if isinstance(value, (list, tuple)):
            return {"messages": list(value)}
        if isinstance(value, str):
            return {
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": value}},
                ],
            }
        raise MCPProtocolError(-32603, "Gateway returned an invalid prompt")

    @staticmethod
    def error_response(request_id: str | int | None, error: MCPProtocolError) -> dict[str, Any]:
        error_body: dict[str, Any] = {"code": error.code, "message": error.message}
        if error.data:
            error_body["data"] = error.data
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error_body}
