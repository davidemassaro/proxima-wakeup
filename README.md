# proxima-wakeup

Two small integration scripts that sit between the [Proxima Hotel module](https://wiki.myproxima.info/knowledge-base/documentazione-per-lintegrazione-del-modulo-hotel-proxima-tramite-api/) (a PBX/hotel-telephony system following the FIAS protocol) and the hotel's PMS / legacy serial call-accounting system.

- **`PO_call.py`** — polls Proxima for expired wakeup calls and notifies the front desk (email + an automated voice call back to the room).
- **`serial_proxima.py`** — receives Proxima's webhooks (room status, call billing) and forwards them, re-encoded as fixed-width serial strings, to a legacy PMS over TCP (Moxa serial-to-Ethernet gateway) or a real serial port.

## How it fits with Proxima

Per Proxima's API docs, the PMS and Proxima exchange events in both directions:

- **PMS → Proxima**: REST calls to endpoints like `/api/v2/hotel/wakeup-request`, `/api/v2/hotel/check-in`, etc. (Basic Auth, user in the `interop` group). Not used by these scripts — they only *read* wakeup state via the `ucpanel` panel API.
- **Proxima → PMS**: webhooks configured in Proxima's admin panel (URL, HTTP method, auth, headers, body with `{$replace_...}` placeholders), for events such as room status, DND, minibar/call billing, and wakeup status. `serial_proxima.py` is the receiving end of these.

## Components

### PO_call.py — wakeup watchdog

Logs into Proxima's `ucpanel` API, lists rooms and their pending wakeup calls, and for every wakeup whose timeout has passed:

- sends an automated voice message back to the room (`.../api/v2/phone/robot-call`)
- emails the front desk (answered / not answered)
- logs the event and dedupes by `wakeup_uuid` in `wakeup_uuids.txt`, so the same expired wakeup isn't re-notified on the next run

Meant to be run periodically (cron / Task Scheduler), not as a daemon.

```bash
python PO_call.py
```

### serial_proxima.py — webhook → serial/TCP bridge

A small FastAPI app exposing two webhook endpoints that Proxima can be configured to call, protected with HTTP Basic Auth:

| Endpoint | Proxima event | Body |
|---|---|---|
| `POST /room-status` | Stato camera | `{"room": "<replace_room_number>", "status": "<replace_maid_status>"}` |
| `POST /bill-call` | Billing – Telefonata | `{"room": "...", "call_destination": "<replace_call_dst>", "call_duration_formatted": "<replace_call_billsec_timed>"}` |

Each request is translated into a fixed-width (62-char) record matching the legacy PMS serial protocol and sent either over TCP to a Moxa serial gateway or directly to a COM/serial port.

```bash
python serial_proxima.py --send_mode tcp --moxa_ip 192.168.1.50 --moxa_port 4001
# or
python serial_proxima.py --send_mode serial --com COM6
# --debug runs one example of each record instead of starting the server
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in real values — never commit .env
```

| Variable | Used by | Purpose |
|---|---|---|
| `MAIL_FROM`, `MAIL_TO` | PO_call.py | Front-desk notification email addresses |
| `SMTP_SERVER`, `SMTP_PORT` | PO_call.py | Outgoing mail relay |
| `PHONE_API_URL`, `PHONE_API_USERNAME`, `PHONE_API_PASSWORD` | PO_call.py | Proxima robot-call API |
| `UCPANEL_LOGIN_URL`, `UCPANEL_USERNAME`, `UCPANEL_PASSWORD`, `UCPANEL_ROOMS_URL` | PO_call.py | Proxima `ucpanel` panel API (wakeup polling) |
| `WEBHOOK_USERNAME`, `WEBHOOK_PASSWORD` | serial_proxima.py | Basic Auth Proxima must send on its webhook calls |

Set the matching URL/auth/body template for `/room-status` and `/bill-call` in Proxima's admin panel → API → webhook configuration.

## Notes

- `requirements.txt` pins what's needed to run both scripts (FastAPI + uvicorn for the webhook server, requests for PO_call.py, pyserial, pytz).
- Proxima notifications are stateless and can arrive with a delay of a few seconds; `PO_call.py`'s dedupe file and `serial_proxima.py`'s stateless webhooks are designed around that.
- Request/response schemas for the PMS → Proxima endpoints aren't public; Proxima provides a Postman collection to certified partners.
