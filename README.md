# Lookahead

A conversation-first readiness radar for stock Hermes **v0.23.0**. Mention a definite upcoming commitment in normal chat. Lookahead captures the quotation and date, delivers a short preparation brief the evening before, and asks once afterwards whether there are next steps. No reminder request is required.

This is a plugin, not a prompt: authenticated capture admission, native elapsed scheduling, durable dedup/reservations, shared caps and spacing, quiet hours, STOP, forget and parent→next-step links persist across chat turns and process restarts. Optional Markdown inputs retain the neutral `Source.read(*, now) -> Snapshot` seam.

## What happens

1. An admitted operator DM completes a normal chat turn. One bounded **host-owned `ctx.llm`** extraction can identify up to two definite first-person commitments with exact source quotations and supported dates.
2. By default, a commitment becomes eligible at **18:00 the previous local day**. A script-only native cron job first checks deterministic policy. **Nothing due = zero model calls.** Each eligible commitment gets its own brief rather than losing other items in a generated batch.
3. One host completion supplies a suggested checklist/talking point and an open question. The plugin supplies the title, local date/time and quotation itself. Same-subject captured notes and up to four bounded user messages from the originating session are available as untrusted data. No arbitrary private files, email, web research or tools are available to the brief generator.
4. **Two hours after the due time**, one follow-up asks: `How did <subject> go? Any next steps I should keep track of?` Quiet hours defer it to the next normal window (default 08:00). No reply means no nag.
5. The next admitted normal chat turn within 24 hours of the latest follow-up reservation is the reply-correlation window. Any captured commitments in that turn store `parent_id`; `/lookahead list` shows parent→next-step IDs. The window is consumed even when the reply has no new commitment. This is temporal correlation, not semantic proof that an arbitrary later message concerns that event.

Example brief (suggestions, not completed work):

```text
Lookahead: Preparation brief — Acorn budget decision meeting
- When: 2030-06-11 10:00 EDT
- You said: "I will meet the Acorn team tomorrow at 10:00 to discuss the budget."
- Suggested prep: List the decision and options you want to discuss.
- Open question: What decision do you need from the team?
```

Output has 4–5 bullets and is capped below 900 characters. Ordinary quotation punctuation is preserved; controls, mentions and markup are sanitized. Long quotations are explicitly labeled excerpts; the full exact source remains in `/lookahead` storage. Invalid/empty/oversized model output, model errors or requested timeouts retain the **existing deterministic offer** as a fallback, never silent loss or an automatic model retry loop. The stock host owns provider routing, retries and enforcement of the requested timeout.

## Calendar (read-only, opt-in)

Calendar meetings do not need to appear in chat. `ics_enabled` defaults to **false**.
Set the following **per-plugin settings** alongside the required `timezone`; choose
exactly one input (this example uses a local file):

```yaml
ics_enabled: true
ics_path: /absolute/path/to/calendar.ics
ics_freshness_hours: 24
ics_timeout_seconds: 5
```

Alternatively omit `ics_path` and configure `ics_url` with your calendar's private
HTTPS iCal address (Google's “Secret address in iCal format” or Outlook's published
ICS link). Do not paste it into chat, screenshots, bug reports or shell history.
Treat that link like a password: anyone possessing it may read your calendar.
Protect the host configuration and backups; Lookahead does not encrypt host config.
Disable with `ics_enabled: false`; this stops reads, not retention of existing ledger
metadata. Rotate/revoke a leaked link at the calendar provider.

**Catalog rule 13 network/privacy disclosure:** when enabled with `ics_url`, each
scheduled scan performs a direct read-only HTTPS GET to the explicitly configured
host. Python stdlib TLS verifies certificates and hostnames. No redirects (even
same-host), environment proxies, credentials, cookies, calendar writes, OAuth,
telemetry or new dependencies are used. Default socket timeout/body deadline is
5 seconds; slow trickles and bodies over 1 MiB are refused. DNS resolution follows
the OS resolver and is not separately deadline-controlled. This option permits an
explicitly selected private-network HTTPS calendar too: configure only trusted
hosts, never URLs supplied by event text. No external calendar provider was contacted
in tests. The private URL is neither logged nor copied into ledger/status/error
messages; status shows only the host, enabled state, fixed errors and skipped count.

Local exports must be absolute regular files with no symlink in any component,
maximum 1 MiB, changed no more than `ics_freshness_hours` ago (24 hours by default,
1–168 allowed), and not more than 60 seconds in the future. A successful scan's
freshness is its read/fetch instant; it does **not** prove upstream completeness or
that the export contains every calendar. An unavailable opted-in calendar holds
both calendar and chat output without resolving existing pending calendar facts.

The parser accepts folded lines and escaped text; UID, SUMMARY, DTSTART/DTEND,
UTC, IANA TZID, floating dates in your configured timezone, and all-day events.
Missing DTEND means 30 minutes for timed events or one local day for all-day events.
Daily/weekly/monthly RRULE supports INTERVAL, COUNT, UNTIL and weekly BYDAY only;
EXDATE, RECURRENCE-ID overrides and cancelled instances are honored. Unsupported
parts/frequencies, RDATE, EXRULE, DURATION, duplicate/missing series masters and
unknown zones skip the **whole series**, counted in status. No partial guessed
series is emitted. Custom VTIMEZONE definitions are not executed. The small explicit
Windows mapping is: Eastern/Central/Mountain/Pacific Standard Time to
America/New_York, America/Chicago, America/Denver, America/Los_Angeles;
GMT Standard Time to Europe/London; UTC to UTC. Other Windows names are rejected
visibly. DST folds choose the first occurrence; gaps skip the series, rather than
silently shifting it. Monthly dates missing in a month (e.g. February 31) are skipped.
Input and expanded events are each capped at 200, with a 100,000-step per-series
expansion ceiling. Expansion uses the configured policy horizon (24 hours by default).

The first scan silently baselines existing meetings, like Markdown. A new event
or meaningful revision can then enter the same pending/reservation/policy path as
chat. IDs hash UID plus original instance start; moved recurring instances retain
identity and change revision. Cancelled/deleted meetings resolve pending facts.
Actual DTSTART–DTEND intervals gate meeting avoidance for **both** sources. Calendar
help offers are not proof of unreadiness and never bypass quiet hours. `/lookahead
list` labels `calendar` versus `chat`; event titles and short description excerpts
are sanitized inert data, with emails/HTTP links removed. Raw UID, attendee/organizer
emails, full descriptions and calendar URLs are not stored. Calendar list metadata
is a last-successful-scan projection, and may be stale if later reads fail. `forget`
currently applies to chat captures only; remove/cancel a calendar meeting at its
source. This adapter feeds the existing prep-offer seam; automated follow-up/brief
features are a separate integration slice, not implemented by this adapter itself.
Fictional Google/Outlook exports are under `tests/fixtures/`.

## Verification

See [sanitized test evidence](docs/TEST-EVIDENCE.md) for stock qualification,
real Telegram API acknowledgements and the limits of that demonstration.
Raw logs, account identifiers and transport receipts are deliberately not published.

## Known capture limitation

**Do not rely on Lookahead to catch every same-day plan.** In 15 native MiniMax-M2.7
trials of one fictional meeting sentence, capture succeeded **3/5** at +4 minutes,
**1/5** at +30 minutes and **5/5** for tomorrow 09:30. All six misses were valid
empty item lists. The prompt already includes the observation clock and timezone;
it has no same-day exclusion. We found no clear defect and made no post-holdout
extraction tune. These tiny operational samples are not a general accuracy
estimate. Check `/lookahead list` rather than treating a chat acknowledgement as
proof of capture. Calendar ICS is a separate explicit opt-in source, not a hidden
fallback for missed conversation capture. See [verification limits](docs/TEST-EVIDENCE.md); raw receipts are private.

## Install on stock Hermes

Requires stock Hermes **v0.23.0 or newer**; qualification used v0.23.0.
From a checkout of this repository:

```sh
hermes plugins install .
hermes plugins enable lookahead
hermes plugins doctor lookahead --ci
```

No catalog listing is assumed. Configure the settings below before resuming output.
See [SECURITY.md](SECURITY.md) before enabling capture or calendar reads.

## Explicit setup

### Native Telegram prerequisites

Run the supported stock package-manager sequence **in the same HOME/HERMES_HOME/runtime that will run the gateway**:

```sh
hermes pm install --tools-only
hermes pm install --extra telegram
```

A fresh isolated home needs the first step for stock PM's tool-closure preflight (ffmpeg, node, npm, ripgrep). The second installs the pinned `python-telegram-bot` extra into the **PM-managed environment**, not necessarily the checkout's development `.venv`. Launch the gateway and subsequent CLI through the normal **`hermes` entry point**. For this source-checkout qualification that is the PM-generated `stock-hermes/.hermes/bin/hermes`; do not launch the gateway via `stock-hermes/.venv/bin/python`, copy site-packages, or hardcode an environment hash. Wait for `Connected to Telegram` in the isolated gateway log before sending demo data.

The optional demo harness uses a dedicated isolated home, never your live profile.
See [the demo guide](docs/DEMO-SCRIPT.md) for explicit local configuration.
Credentials must be supplied by the operator; none are bundled.

Enable this standalone plugin with stock Hermes, then configure `plugins.entries.lookahead.settings`:

```yaml
plugins:
  enabled: [lookahead]
  entries:
    lookahead:
      settings:
        timezone: America/New_York
        operator_platform: telegram
        operator_user_id: YOUR_STABLE_USER_ID
        operator_chat_id: YOUR_DM_CHAT_ID
        capture_enabled: true
```

Use your own stock-configured platform/home channel. Native cron scrubs provider-key environment variables: if your credential exists only in the shell or `.env`, save it through the **stock operator credential flow**, e.g. `hermes auth add minimax --type api-key` (secure local prompt), so the host facade can resolve it from its native pool. Never paste keys in chat. The plugin never reads credentials or constructs a provider/platform client. Registration performs no scheduling, file reads or model calls.

```sh
hermes lookahead setup --deliver telegram
# Review the command it prints, then explicitly create the job:
hermes cron create 'every 1m' --name lookahead --no-agent --script lookahead_tick.py --deliver telegram
hermes lookahead resume
```

Setup stages a small runner under the active `HERMES_HOME/scripts`. It launches the documented stock CLI process (`python -m hermes_cli.main lookahead tick`) to receive the actual registered `PluginContext`, including `ctx.llm` and host trust gates. It does not instantiate a provider facade, patch core, bypass approvals or read credential stores. Native cron still owns delivery and empty stdout remains silent. `setup` does **not** create a schedule. Outbound starts STOPPED; capture defaults ON after enablement plus explicit timezone/binding. Disabling the plugin or removing its package makes the staged runner silent before ledger access.

## Demo timing — visible, not hidden hooks

```yaml
        offer_lead_minutes: 5
        followup_delay_minutes: 1
        spacing_minutes: 0
```

`offer_lead_minutes: 0` (default) keeps previous-local-day 18:00. A positive value changes **new captures** to due minus that many minutes, never earlier than capture time. Follow-up defaults to 120 minutes. Status reports both values and `demo_timing: true` whenever either differs from its default. Quiet hours and caps still apply; `spacing_minutes: 0` is an explicit demonstration configuration, not an automatic bypass. Restore normal values after a demo; changing offer timing does not silently rewrite existing captures.

## Controls and privacy

`/lookahead status`, `list [page]`, `forget <64-hex-id>`, `stop`, `resume` require the configured stable operator DM coordinates. Exact plain `STOP` / `RESUME` are consumed only there; other users/groups fail closed. `forget` cancels that event's pending follow-up and suppresses a concurrently generated brief at the last pre-output readback. It preserves an opaque tombstone and metadata-free accounting, not forensic erasure of SQLite WAL, backups, original Hermes sessions or model logs.

Capture is bound to admitted operator sessions using stock read-only `SessionDB.get_session`; CLI capture is separately opt-in via `capture_cli: true`. Capture sends at most 4,000 user-text characters through auxiliary task `lookahead_capture` (512 output tokens, requested timeout 8s). Brief task `lookahead_brief` sends bounded captured notes and originating-session user context (300 output tokens, requested timeout 8s). Both use the configured stock model and may incur its cost; no model/provider/auth override is requested by production code. Captured injection text is treated as JSON data under a separate system instruction, never tool authority. This reduces injection risk; it is not a proof of perfect model instruction resistance.

Supported dates: tomorrow, weekdays/next weekdays and ISO calendar dates, optionally `at HH:MM`. Date-only means 09:00 in the configured timezone and is marked assumed. A bare weekday on that same weekday and explicit DST folds/gaps are rejected. Relative dates use observation time, not an unavailable original authored timestamp. Lexical/provenance gates are conservative and can miss genuine plans mixed with hypothetical/negative text. Inspect the real-model evaluation before choosing a deployment model.

## Delivery boundary and teardown

Defaults: quiet 22:00–08:00, 3 normal handoff batches per local day, 30-minute spacing. Briefs and follow-ups share those limits and STOP. Captured commitments never qualify for the optional fixture-readiness overnight urgency exception. A reservation is durably `handoff_unknown` **before** generation/output. Crashes or final STOP/forget can lose output; unknowns never automatically retry. Plugin stdout is not a delivery receipt. STOP cannot recall queued/in-flight messages or police other plugins/native notices.

To tear down: `hermes lookahead stop`, then pause/remove **only your owned Lookahead cron job** with native `hermes cron pause <id>` / `hermes cron remove <id>`. Disabling alone does not remove native jobs. Never remove unrelated jobs.

## Sources and tests

`ConversationSource` is primary. Optional `MarkdownSource` takes explicitly selected absolute regular local files, bounded to 64 KiB / 200 rows, with symlink/traversal/special-file refusal, strict tables, aware times and freshness checks. Exact tables: agenda `id | at | title | readiness_key`; readiness `key | status | detail` (`ready` or `not_ready`). Initial Markdown scans silently baseline existing facts. Generate fresh fictional files with `python scripts/make_demo.py --output /new/directory`. Read-only ICS is also available as described above.

```sh
bash scripts/test.sh
```

The launcher defaults to a clean sibling `stock-hermes` v0.23.0 checkout.
Override with `STOCK_ROOT=<stock-hermes-checkout>` and `ENV_ROOT=<isolated-test-root>`.
It creates fresh HOME/HERMES_HOME and blocks test sockets/DNS. Tests use fake models,
real stock registration/storage and actual policy/transactions; they do not prove
model accuracy or platform receipt. See [acceptance](docs/ACCEPTANCE.md) and
[sanitized evidence](docs/TEST-EVIDENCE.md).
