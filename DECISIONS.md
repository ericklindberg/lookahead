# Architecture decisions

## Stock host integration

- Compatibility floor: stock Hermes v0.23.0, with no core patches or runtime
  monkeypatches. Registration uses public plugin hooks, tools, commands, CLI
  commands and auxiliary tasks. It performs no scheduling, model calls or reads.
- Conversation capture runs after an admitted operator turn. The configured
  platform, stable user ID and DM ID are explicit; groups and unknown sessions
  fail closed. Read-only stock session lookup establishes provenance. CLI capture
  requires a separate explicit opt-in.
- Extraction and brief generation use the actual host-owned `ctx.llm` facade.
  Provider authentication, routing, timeout enforcement and retries remain the
  host's responsibility; production code reads no credential files and creates
  no provider/platform client.

## Bounded capture and grounded assistance

- Accept at most two definite first-person commitments per turn, with exact
  quotations, supported dates, a configured timezone and conservative validation.
  Relative dates use observation time. Ambiguous same-day weekdays and DST
  folds/gaps fail closed. Acknowledgement is not proof of durable capture.
- Preparation generation returns two bounded suggested-help fields. The plugin
  supplies the captured title, local due time and quotation, not the model.
  Same-subject notes and bounded originating-session user context are untrusted
  data, never instructions or tool authority. Invalid output/errors fall back to
  a deterministic offer, without an automatic model retry loop.
- Same-day extraction misses were observed in small real-model samples. The
  production prompt was not retuned after the holdout. See the evidence summary;
  no general accuracy or perfect injection-resistance claim is made.

## Scheduling, persistence and delivery

- Native script-only cron supplies elapsed wakeups and owns delivery. Empty
  stdout is silent; deterministic no-work policy avoids inference on empty ticks.
  Explicit setup stages a runner under `$HERMES_HOME/scripts` and prints the
  native job command; it never creates a schedule automatically.
- The staged runner resolves installed source explicitly because native cron
  scrubs PYTHONPATH. It launches a stock CLI child to obtain the genuine registered
  plugin context and rechecks native enablement before output.
- Outbound starts STOPPED. Quiet hours, caps, spacing and meeting avoidance apply
  before handoff. A positive prep-lead or nondefault follow-up setting is visible
  demo timing, never an invisible clock override. Normal prep is previous-local-day
  18:00; follow-up defaults to two hours after the event.
- Reserve durably as `handoff_unknown` before generation/output. Crashes or final
  STOP/forget may lose output; unknowns never automatically retry. Stdout is not
  transport receipt, and STOP cannot recall already queued/in-flight output.
- One follow-up per parent; no reply means no repeated nag. The next admitted
  normal turn within 24 hours consumes the correlation window. Captured next
  steps store a parent link. This is temporal correlation, not semantic proof.
- SQLite transactions enforce durable dedup and state transitions. Forget cancels
  pending follow-up and rechecks before brief output, retaining opaque tombstones
  and accounting; it is not erasure of host sessions, WAL, backups or provider logs.
- Disabling a plugin does not remove its native cron job. Stop first, then
  pause/remove only the owned job during teardown.

## Sources

- `Source.read(*, now) -> Snapshot` is the shared seam. Conversation capture is
  primary; bounded local Markdown and read-only ICS are explicit opt-ins.
- ICS accepts one regular local file or configured HTTPS URL, not both. Refuse
  symlinks, redirects, oversized responses and unsupported recurrence series.
  URL configuration is a secret; it is not logged or stored in the ledger.
  Status can show its hostname. No calendar writes, OAuth or account discovery.
- Calendar first scan silently baselines; meaningful revisions share pending,
  policy and reservation logic. Actual event intervals gate meeting avoidance
  across calendar and chat. Failed opted-in reads hold output rather than
  pretending the source is fresh. Successful read time is not proof of upstream
  completeness. Tests use fictional ICS and local transport, not live providers.

## Qualification and optional harnesses

- Unit tests block sockets/DNS and fake model completions while using real stock
  registration/storage APIs. They do not establish model quality or delivery.
- Operator-run scripts are development fixtures, not the production plugin path.
  Dedicated Telegram credentials/identifiers and an isolated root are supplied
  explicitly. Native PM installs tools before its Telegram extra. The same
  isolated home/runtime is reused; source replacement alone does not reload a
  running gateway. Exact process identities protect unrelated owners at teardown.
- Private run output goes outside the repository. Token redaction is not PII
  sanitization. Raw logs/receipts, historical scratch notes and credentials are
  excluded from this fresh-history distribution. See [SECURITY.md](SECURITY.md)
  and [sanitized qualification evidence](docs/TEST-EVIDENCE.md).
