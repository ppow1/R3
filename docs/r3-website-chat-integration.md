# R3 website Chat integration

The website now proxies the deployed durable conversation API from its backend. The browser only calls same-origin `/api/v1/chat/...` routes. The website validates the existing portal session and derives `X-R3-Principal` from the portal's authenticated email and `steward` role. Browser identity headers are ignored.

The service credential stays in the server-side file referenced by `~/.config/r3/chat.json`; the browser never receives it. The conversation API remains loopback-only at `127.0.0.1:8770`. The website login and password-reset endpoints proxy the existing portal routes on port 8767.

The page is exposed through HTTPS at `/r3/` so the existing portal session cookie remains secure. The reverse proxy strips `/r3` before forwarding to the website on port 8303. Chat history refreshes from `after=0` so earlier delivery-state changes appear. Message retries reuse the same `client_message_id` while a submission is pending.

Initial support is conversation list/create, ordered message history, message send, delivery status refresh, Steward sign-in, and email password reset. Search, rename, archive, delete, conference rooms, and extra message actions remain unavailable until their runtime endpoints and capabilities are implemented.

Regression tests: `python -m unittest discover -s tests -p 'test_chat_api.py'`.

## HR-backed resident routing

The resident selector reads the authenticated HR directory. HR's generic directory projection omits the confidential `extensions.authority_principal` value; the Website adapter obtains it only through `HRCapability.resolve_authority_principal` after native Steward authentication. It never returns that value to the browser.

Authority principals are opaque and case-sensitive. Configure the private file named by `R3_WEBSITE_RESIDENT_RUNTIME_MAP` with explicit bindings to keys in `config/runtime.json`:

```json
{
  "authority_principals": {
    "<exact HR authority principal>": "<configured runtime key>"
  }
}
```

Do not infer runtime keys from HR resident IDs or principal spelling. A missing HR association, missing binding, or runtime key absent from the runtime registry leaves that resident unavailable for Chat. Keep this mapping outside the repository and web-served paths. The configured legacy Grace route continues to use its existing configured runtime key and conversation history.

The website verifies that each conversation belongs to the selected resident before reading or sending messages. All Chat mutations require the native Steward CSRF token and a same-origin request.
