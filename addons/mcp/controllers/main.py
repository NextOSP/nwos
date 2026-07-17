# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from http import HTTPStatus

from gevent import Timeout as GeventTimeout
from werkzeug.exceptions import NotFound, RequestEntityTooLarge

from nwos import http
from nwos.exceptions import AccessDenied, AccessError, MissingError, UserError
from nwos.http import request

from ..services.protocol import (
    LATEST_PROTOCOL_VERSION,
    MCPProtocol,
    MCPProtocolError,
    SUPPORTED_PROTOCOL_VERSIONS,
)


_logger = logging.getLogger(__name__)

_DATABASE_ARGUMENTS = {"db", "database", "dbname"}
_DATABASE_HEADERS = {
    "x-nwos-database",
    "x-odoo-database",
    "x-flectra-database",
    "x-openerp-database",
}
_ORIGIN_SPLIT_RE = re.compile(r"[\s,]+")
_METADATA_NAME_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,255}$")
_MODEL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,254}$")
_DEFAULT_MAX_REQUEST_BYTES = 1024 * 1024
_DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
_DEFAULT_MAX_BATCH_SIZE = 20


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


class MCPController(http.Controller):
    """Stateless Streamable HTTP transport for the native MCP gateway."""

    def _config(self, name, default=None):
        # Configuration is framework metadata, not business data.  Reading it
        # as the API-key user would make endpoint security depend on Settings
        # model access instead of the configured MCP policy.
        return request.env["ir.config_parameter"].sudo().get_param(name, default)

    def _limit(self, name, default, minimum=1, maximum=None):
        try:
            value = int(self._config(name, default))
        except (TypeError, ValueError):
            value = default
        value = max(minimum, value)
        return min(value, maximum) if maximum is not None else value

    def _response_headers(self, protocol_version=None):
        return [
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("MCP-Protocol-Version", protocol_version or LATEST_PROTOCOL_VERSION),
            *self._cors_headers(),
        ]

    def _cors_headers(self):
        headers = [
            ("Vary", "Origin"),
        ]
        origin = request.httprequest.headers.get("Origin")
        if origin and self._check_origin():
            headers.append(("Access-Control-Allow-Origin", origin))
        return headers

    def _json_response(self, body, *, status=HTTPStatus.OK, protocol_version=None):
        serialized = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        maximum = self._limit(
            "mcp.max_response_bytes",
            _DEFAULT_MAX_RESPONSE_BYTES,
            minimum=1024,
            maximum=16 * 1024 * 1024,
        )
        if len(serialized) > maximum:
            # The size check runs after protocol dispatch. Roll back the whole
            # request so a client never receives an error for a mutation that
            # was nevertheless committed and then retries it.
            request.env.cr.rollback()
            body = MCPProtocol.error_response(
                MCPProtocol._safe_request_id(body),
                MCPProtocolError(-32009, "Response exceeds the configured size limit"),
            )
        return request.make_json_response(
            body,
            headers=self._response_headers(protocol_version),
            status=status,
        )

    def _unauthorized_response(self):
        response = self._transport_error(
            HTTPStatus.UNAUTHORIZED,
            "A Bearer API key is required",
            code=-32001,
        )
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    def _empty_response(self, *, status=HTTPStatus.ACCEPTED, protocol_version=None):
        return request.make_response(
            b"",
            headers=self._response_headers(protocol_version),
            status=status,
        )

    def _transport_error(self, status, message, *, code=-32600):
        error = MCPProtocolError(code, message)
        return self._json_response(
            MCPProtocol.error_response(None, error),
            status=status,
        )

    def _check_origin(self):
        origin = request.httprequest.headers.get("Origin")
        if not origin:
            return True

        configured = self._config("mcp.allowed_origins", "") or ""
        allowed = {item.rstrip("/") for item in _ORIGIN_SPLIT_RE.split(configured) if item}
        server_origin = request.httprequest.host_url.rstrip("/")
        return "*" in allowed or origin.rstrip("/") == server_origin or origin.rstrip("/") in allowed

    @staticmethod
    def _accepts_json():
        accept = request.httprequest.headers.get("Accept")
        if not accept:
            return True
        return request.httprequest.accept_mimetypes.best_match(["application/json"]) is not None

    @staticmethod
    def _explicit_database_requested():
        # The ``X-NWOS-Database`` routing header (see ``_DATABASE_HEADERS``) is the
        # supported way to target one database on a multi-database server, so it is
        # allowed: an API key only authenticates against its own database, so the
        # header cannot reach data another key could not. Query-string database
        # arguments stay rejected -- they are an ambiguous, cacheable side channel
        # for a JSON-RPC POST.
        return bool(set(request.httprequest.args.keys()) & _DATABASE_ARGUMENTS)

    @staticmethod
    def _has_bearer_token():
        authorization = request.httprequest.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        return separator == " " and scheme.lower() == "bearer" and bool(token.strip())

    @staticmethod
    def _payload_selects_database(payload):
        messages = payload if isinstance(payload, list) else [payload]
        return any(
            isinstance(message, dict) and bool(set(message) & _DATABASE_ARGUMENTS)
            for message in messages
        )

    def _requested_protocol_version(self):
        version = request.httprequest.headers.get("MCP-Protocol-Version")
        if version and version not in SUPPORTED_PROTOCOL_VERSIONS:
            return None, self._transport_error(
                HTTPStatus.BAD_REQUEST,
                "Unsupported MCP-Protocol-Version",
            )
        return version or LATEST_PROTOCOL_VERSION, None

    @staticmethod
    def _metadata_value(value, maximum):
        if value is None:
            return ""
        # Keep audit metadata single-line and bounded.  It is diagnostic data,
        # never authorization input.
        return re.sub(r"[\x00-\x1f\x7f]+", " ", str(value)).strip()[:maximum]

    def _gateway_context(self, payload, protocol_version):
        request_id = request.httprequest.headers.get("X-Request-ID")
        if not request_id and isinstance(payload, dict):
            candidate = payload.get("id")
            if isinstance(candidate, (str, int)) and not isinstance(candidate, bool):
                request_id = candidate
        request_id = self._metadata_value(request_id, 128) or uuid.uuid4().hex

        client_name = None
        messages = payload if isinstance(payload, list) else [payload]
        for message in messages:
            if not isinstance(message, dict) or message.get("method") != "initialize":
                continue
            client_info = message.get("params", {}).get("clientInfo", {})
            if isinstance(client_info, dict) and isinstance(client_info.get("name"), str):
                client_name = client_info["name"]
                break
        client_name = self._metadata_value(
            client_name or request.httprequest.headers.get("User-Agent") or "MCP client",
            255,
        )
        ip_address = self._metadata_value(request.httprequest.remote_addr, 64)
        return {
            "mcp_request_id": request_id,
            "mcp_client_name": client_name,
            "mcp_ip_address": ip_address,
            "mcp_protocol_version": protocol_version,
        }

    @staticmethod
    def _audit_protocol_event(
        metadata, method, params, duration_ms, *, status="success", error=None
    ):
        arguments = params.get("arguments", {}) if isinstance(params, dict) else {}
        if not isinstance(arguments, dict):
            arguments = {}
        requested_operation = params.get("name") if method == "tools/call" else method
        operation = (
            requested_operation
            if isinstance(requested_operation, str)
            and _METADATA_NAME_RE.fullmatch(requested_operation)
            else (method if _METADATA_NAME_RE.fullmatch(method or "") else "invalid_request")
        )
        model_name = arguments.get("model")
        if not isinstance(model_name, str) or not _MODEL_NAME_RE.fullmatch(model_name):
            model_name = None
        raw_record_ids = arguments.get("ids")
        if raw_record_ids is None and "id" in arguments:
            raw_record_ids = [arguments["id"]]
        record_ids = []
        if isinstance(raw_record_ids, (list, tuple)):
            record_ids = [
                record_id
                for record_id in raw_record_ids[:1000]
                if isinstance(record_id, int)
                and not isinstance(record_id, bool)
                and record_id > 0
            ]
        try:
            with request.env.cr.savepoint():
                request.env["mcp.audit.log"].log_event(
                    request_id=metadata["mcp_request_id"],
                    client_name=metadata["mcp_client_name"],
                    ip_address=metadata["mcp_ip_address"],
                    model_name=model_name,
                    operation=operation,
                    record_ids=record_ids or None,
                    status=status,
                    duration_ms=duration_ms,
                    error_category=error.__class__.__name__ if error else None,
                )
        except Exception:
            _logger.exception("Failed to write MCP audit event")

    @http.route(
        "/mcp",
        type="http",
        auth="none",
        methods=["OPTIONS"],
        csrf=False,
        readonly=True,
        save_session=False,
    )
    def cors_preflight(self):
        """CORS preflight without weakening authentication on ``POST``."""
        if not request.db or self._explicit_database_requested():
            raise NotFound()
        if not _as_bool(self._config("mcp.enabled", "False"), default=False):
            raise NotFound()
        if not self._check_origin():
            return self._empty_response(status=HTTPStatus.FORBIDDEN)

        requested_method = request.httprequest.headers.get("Access-Control-Request-Method")
        if requested_method and requested_method.upper() != "POST":
            return self._empty_response(status=HTTPStatus.METHOD_NOT_ALLOWED)
        allowed_headers = {
            "authorization", "content-type", "accept", "mcp-protocol-version",
            "x-request-id",
        }
        requested_headers = {
            header.strip().lower()
            for header in request.httprequest.headers.get(
                "Access-Control-Request-Headers", ""
            ).split(",")
            if header.strip()
        }
        if not requested_headers <= allowed_headers:
            return self._empty_response(status=HTTPStatus.FORBIDDEN)

        response = self._empty_response(status=HTTPStatus.NO_CONTENT)
        response.headers["Access-Control-Allow-Methods"] = "POST"
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, Accept, MCP-Protocol-Version, X-Request-ID"
        )
        response.headers["Access-Control-Max-Age"] = "600"
        return response

    @http.route(
        "/mcp/download/<string:token>",
        type="http",
        auth="none",
        methods=["OPTIONS"],
        csrf=False,
        readonly=True,
        save_session=False,
    )
    def cors_download_preflight(self, token):
        """Authorize browser download preflight without inspecting the token."""
        del token
        if not request.db or self._explicit_database_requested():
            raise NotFound()
        if not _as_bool(self._config("mcp.enabled", "False"), default=False):
            raise NotFound()
        if not self._check_origin():
            return self._empty_response(status=HTTPStatus.FORBIDDEN)

        requested_method = request.httprequest.headers.get(
            "Access-Control-Request-Method"
        )
        if requested_method and requested_method.upper() != "GET":
            return self._empty_response(status=HTTPStatus.METHOD_NOT_ALLOWED)
        allowed_headers = {
            "authorization", "accept", "mcp-protocol-version", "x-request-id",
        }
        requested_headers = {
            header.strip().lower()
            for header in request.httprequest.headers.get(
                "Access-Control-Request-Headers", ""
            ).split(",")
            if header.strip()
        }
        if not requested_headers <= allowed_headers:
            return self._empty_response(status=HTTPStatus.FORBIDDEN)

        response = self._empty_response(status=HTTPStatus.NO_CONTENT)
        response.headers["Access-Control-Allow-Methods"] = "GET"
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Accept, MCP-Protocol-Version, X-Request-ID"
        )
        response.headers["Access-Control-Max-Age"] = "600"
        return response

    @http.route(
        "/mcp",
        type="http",
        auth="bearer",
        methods=["POST"],
        csrf=False,
        readonly=False,
        save_session=False,
        max_content_length=16 * 1024 * 1024,
    )
    def mcp(self):
        # ``auth='bearer'`` intentionally permits an interactive session as a
        # framework fallback.  MCP is an API-key-only surface, so narrow it.
        if not self._has_bearer_token():
            return self._unauthorized_response()
        if not _as_bool(self._config("mcp.enabled", "False"), default=False):
            return self._transport_error(
                HTTPStatus.NOT_FOUND,
                "MCP endpoint is disabled",
                code=-32004,
            )
        if self._explicit_database_requested():
            return self._transport_error(
                HTTPStatus.BAD_REQUEST,
                "Explicit database selection is not supported",
            )
        if not self._check_origin():
            return self._transport_error(
                HTTPStatus.FORBIDDEN,
                "Origin is not allowed",
                code=-32001,
            )
        if request.httprequest.mimetype != "application/json":
            return self._transport_error(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "Content-Type must be application/json",
            )
        if not self._accepts_json():
            return self._transport_error(
                HTTPStatus.NOT_ACCEPTABLE,
                "Accept must allow application/json",
            )

        protocol_version, error_response = self._requested_protocol_version()
        if error_response:
            return error_response

        max_request_bytes = self._limit(
            "mcp.max_request_bytes",
            _DEFAULT_MAX_REQUEST_BYTES,
            maximum=16 * 1024 * 1024,
        )
        content_length = request.httprequest.content_length
        if content_length is not None and content_length > max_request_bytes:
            return self._transport_error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "Request body is too large",
            )
        request.httprequest.max_content_length = max_request_bytes
        try:
            raw_body = request.httprequest.get_data(cache=True)
        except RequestEntityTooLarge:
            return self._transport_error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "Request body is too large",
            )
        if len(raw_body) > max_request_bytes:
            return self._transport_error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "Request body is too large",
            )
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json_response(
                MCPProtocol.error_response(None, MCPProtocolError(-32700, "Parse error")),
                status=HTTPStatus.BAD_REQUEST,
                protocol_version=protocol_version,
            )
        if self._payload_selects_database(payload):
            return self._transport_error(
                HTTPStatus.BAD_REQUEST,
                "Explicit database selection is not supported",
            )

        max_batch_size = self._limit(
            "mcp.max_batch_size",
            _DEFAULT_MAX_BATCH_SIZE,
            maximum=100,
        )
        metadata = self._gateway_context(payload, protocol_version)
        gateway = request.env["mcp.gateway"].with_context(**metadata)
        protocol = MCPProtocol(
            gateway,
            execution_context=request.env.cr.savepoint,
            error_callback=lambda method, params, error, duration: self._audit_protocol_event(
                metadata, method, params, duration, status="error", error=error
            ),
            success_callback=lambda method, params, duration: self._audit_protocol_event(
                metadata, method, params, duration
            ),
            max_batch_size=max_batch_size,
        )
        execution_timeout = self._limit(
            "mcp.execution_timeout", 30, minimum=1, maximum=300
        )
        try:
            with GeventTimeout(execution_timeout):
                response_body = protocol.handle(payload)
        except GeventTimeout:
            # A compatibility batch may have completed earlier siblings.  A
            # timeout invalidates the whole HTTP transaction so no response can
            # claim a timed-out mutation was committed.
            request.env.cr.rollback()
            timeout_error = TimeoutError("MCP request timed out")
            self._audit_protocol_event(
                metadata,
                "request",
                {},
                execution_timeout * 1000,
                status="error",
                error=timeout_error,
            )
            request_id = MCPProtocol._safe_request_id(payload)
            response_body = MCPProtocol.error_response(
                request_id,
                MCPProtocolError(-32008, "Request timed out"),
            )
        if response_body is None:
            return self._empty_response(protocol_version=protocol_version)
        response_protocol_version = protocol_version
        if isinstance(response_body, dict):
            result = response_body.get("result")
            if (
                isinstance(result, dict)
                and result.get("protocolVersion") in SUPPORTED_PROTOCOL_VERSIONS
            ):
                response_protocol_version = result["protocolVersion"]
        return self._json_response(
            response_body,
            protocol_version=response_protocol_version,
        )

    @http.route(
        "/mcp/download/<string:token>",
        type="http",
        auth="bearer",
        methods=["GET"],
        csrf=False,
        readonly=False,
        save_session=False,
    )
    def download(self, token):
        """Consume a short-lived, user-bound binary download token."""
        if not self._has_bearer_token():
            raise NotFound()
        if not _as_bool(self._config("mcp.enabled", "False"), default=False):
            raise NotFound()
        if self._explicit_database_requested() or not self._check_origin():
            raise NotFound()
        started = time.monotonic()
        protocol_version = (
            request.httprequest.headers.get("MCP-Protocol-Version")
            or LATEST_PROTOCOL_VERSION
        )
        metadata = self._gateway_context({}, protocol_version)
        try:
            with request.env.cr.savepoint():
                result = request.env["mcp.gateway"].with_context(**metadata).download(token)
                if not isinstance(result, dict):
                    raise ValueError("invalid download result")
                content = result.get("content")
                if isinstance(content, memoryview):
                    content = content.tobytes()
                elif isinstance(content, bytearray):
                    content = bytes(content)
                if not isinstance(content, bytes):
                    raise ValueError("invalid download content")

                mimetype = result.get("mimetype") or "application/octet-stream"
                if not isinstance(mimetype, str) or "\r" in mimetype or "\n" in mimetype:
                    mimetype = "application/octet-stream"
                filename = result.get("filename") or "download"
                if not isinstance(filename, str):
                    filename = "download"
                filename = filename.replace("\\", "/").rsplit("/", 1)[-1].replace("\x00", "")[:255]
                filename = filename or "download"
        except (AccessDenied, AccessError, MissingError, UserError) as error:
            self._audit_protocol_event(
                metadata,
                "download",
                {},
                (time.monotonic() - started) * 1000,
                status="error",
                error=error,
            )
            raise NotFound() from None
        except Exception as error:
            self._audit_protocol_event(
                metadata,
                "download",
                {},
                (time.monotonic() - started) * 1000,
                status="error",
                error=error,
            )
            _logger.exception("Failed to serve MCP binary download")
            raise NotFound() from None

        self._audit_protocol_event(
            metadata,
            "download",
            {},
            (time.monotonic() - started) * 1000,
        )

        return request.make_response(
            content,
            headers=[
                ("Content-Type", mimetype),
                ("Content-Disposition", http.content_disposition(filename)),
                ("Content-Length", str(len(content))),
                ("Cache-Control", "private, no-store"),
                ("X-Content-Type-Options", "nosniff"),
                *self._cors_headers(),
            ],
        )
