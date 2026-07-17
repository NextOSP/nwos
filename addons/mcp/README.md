# Model Context Protocol Gateway

The `mcp` addon exposes installed NextOSP/Odoo models through one native,
stateless [Model Context Protocol](https://modelcontextprotocol.io/) endpoint.
It uses ORM metadata, access controls, and record rules, so custom and newly
installed modules are available without module-specific adapters.

## Installation and configuration

1. Install **Model Context Protocol (MCP) Gateway** from Apps.
2. Open **MCP Gateway > Settings** and enable the endpoint.
3. Configure the deployment's `dbfilter` so the request hostname resolves to
   exactly one database. The endpoint deliberately does not accept a database
   name in the request body.
4. Create an API key for the integration user. MCP uses the standard `rpc`
   API-key scope and executes with that user's companies, ACLs, and record
   rules.
5. Add comma-separated browser origins under **Allowed Origins** when a
   web-based MCP client is hosted on a different origin. Non-browser clients
   may omit `Origin`.

The endpoint is `POST /mcp`. A minimal initialization request is:

```bash
curl https://erp.example.com/mcp \
  --request POST \
  --header 'Authorization: Bearer YOUR_API_KEY' \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json' \
  --data '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-11-25",
      "capabilities": {},
      "clientInfo": {"name": "example-client", "version": "1.0"}
    }
  }'
```

The transport is stateless: it does not issue an MCP session ID, and any
worker may serve any request. JSON-RPC notifications return an empty HTTP 202
response.

## Model coverage

The gateway discovers registered, non-transient models and exposes generic MCP
tools for:

- model, field, view, and operation discovery;
- search/read, direct reads, and grouped aggregation;
- policy-controlled create and update operations;
- preview/confirm deletion and allowlisted workflow methods;
- report discovery/rendering and attachment operations.

Resources provide model schemas, records, result pages, reports, attachments,
and binary fields. Large binary values are delivered through short-lived,
user-bound, single-use download tokens rather than inline base64 values.

Every business operation uses the authenticated user's normal ORM environment.
Installing this addon does not bypass model ACLs, record rules, company rules,
field restrictions, validation, mail tracking, or ORM hooks.

## Policies and safety defaults

No per-model configuration is required. Every model is discoverable, readable,
creatable and updatable by default; only deletion is opt-in. Effective access is
always bounded by the ORM permissions of the user whose API key is used, so a
policy can only ever narrow that account, never widen it. Use **MCP Gateway >
Model Policies** to enable deletes, narrow discovery or reads, choose
allowed/blocked fields, set a result limit, or expose reports and attachments
more selectively. Mutating model methods must be listed one per line under
**Workflow Methods**. Archiving a policy denies all MCP access to that model;
delete the policy to restore the default behavior.

Delete and workflow calls require a preview followed by a confirmation token.
Tokens are bound to the user, company, operation, arguments, records, and
previewed record versions; they expire quickly and can be consumed only once.
Credential and framework-secret fields remain blocked regardless of policy.

## Operations

**MCP Gateway > Audit Logs** records the caller, client metadata, operation,
record identifiers, timing, and success/error category. It does not record
business field values or binary content. A daily scheduled action deletes logs
older than the configured retention period (90 days by default).

Use the settings page to constrain request and response bytes, batch size, page size,
execution timeout, confirmation lifetime, download lifetime, allowed origins,
and audit retention. Keep TLS termination and hostname-to-database routing at
the reverse proxy/application deployment layer.

## Client compatibility

Point any Streamable HTTP MCP client at `https://YOUR_HOST/mcp` and configure
the API key as a Bearer token. The addon does not provide stdio or legacy SSE
transport, OAuth authorization-server flows, server-initiated sampling, or
stateful notifications.
