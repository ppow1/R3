# R3 website Chat integration

The website now proxies the deployed durable conversation API from its backend. The browser only calls same-origin `/api/v1/chat/...` routes. The website validates the existing portal session and derives `X-R3-Principal` from the portal's authenticated email and `steward` role. Browser identity headers are ignored.

The service credential stays in the server-side file referenced by `~/.config/r3/chat.json`; the browser never receives it. The conversation API remains loopback-only at `127.0.0.1:8770`. The website login and password-reset endpoints proxy the existing portal routes on port 8767.

The page is exposed through HTTPS at `/r3/` so the existing portal session cookie remains secure. The reverse proxy strips `/r3` before forwarding to the website on port 8303. Chat history refreshes from `after=0` so earlier delivery-state changes appear. Message retries reuse the same `client_message_id` while a submission is pending.

Initial support is conversation list/create, ordered message history, message send, delivery status refresh, Steward sign-in, and email password reset. Search, rename, archive, delete, conference rooms, and extra message actions remain unavailable until their runtime endpoints and capabilities are implemented.

Regression tests: `python -m unittest discover -s tests -p 'test_chat_api.py'`.
