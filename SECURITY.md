# Security and privacy

Report vulnerabilities through **GitHub private vulnerability reporting** on this
repository's Security tab once enabled. Do not post secrets or sensitive examples
in public issues. If private reporting is not available yet, wait for a private
channel to be enabled rather than publishing exploit details or credentials.

## Data read and sent

The plugin observes bounded text only from configured admitted operator sessions.
Capture sends up to 4,000 user-text characters to the host-owned model facade.
Brief generation uses bounded captured notes and up to four user messages from
the originating stock session, treated as untrusted data. Host provider routing,
authentication, billing and logs remain the host's responsibility.

Optional Markdown inputs read only explicitly selected regular local agenda and
readiness files (64 KiB each, no symlink/traversal/special files). Optional ICS
reads one selected regular local file or performs read-only HTTPS GET to a configured
calendar URL (1 MiB cap, certificate validation, no redirects/proxy/cookies).
A private calendar link is itself a secret in host config; it is not encrypted by
this plugin and is not copied into the ledger. Status may disclose its hostname.
No calendar writes or account OAuth are performed by the plugin. Calendar text
can be sensitive even after identifiers/links are removed.

## Processes, scheduling and delivery

Registration creates no job and performs no file/model reads. Explicit setup
stages a runner under `$HERMES_HOME/scripts`; it starts the stock Hermes CLI child
process for a tick. The operator explicitly creates the native script-only cron
job. No arbitrary captured text is executed as a command. Native Hermes scheduling
and the configured platform adapter own delivery; empty stdout is silent.
STOP applies only before output handoff and cannot retract queued messages or
silence other plugins. Disable does not delete the job: stop, then pause/remove
only the owned Lookahead job. No telemetry or usage-reporting endpoint exists.

## Persistent state and credentials

Plugin-owned SQLite state under `$HERMES_HOME/plugin-data/lookahead` retains
captured quotations, dates, provenance/session references, policy state,
reservations, follow-up links and opaque forget tombstones. `forget` is not secure
erasure of SQLite WAL, host sessions, provider logs or backups. Calendar metadata
is limited, not a complete private-calendar mirror.

**The installed plugin neither reads credential stores nor stores model/platform
credentials.** It uses stock host-owned model and delivery facilities. The optional
operator-run scripts under `scripts/` are separate development fixtures: they
accept explicit local secret environment variables, invoke stock authentication,
and write a test bot token into an isolated host's mode-600 `.env`. Host credentials
can remain in that isolated home until the operator removes it. Never run those
harnesses against a live profile. Their private logs/receipts may contain account
IDs, host paths and sensitive content even after token redaction; outputs are
outside the repository and must not be published without a separate review.
