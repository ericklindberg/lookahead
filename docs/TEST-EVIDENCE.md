# Sanitized qualification evidence

## What was verified

- The development candidate passed **235 tests** on unmodified stock Hermes
  **v0.23.0**. Tests exercise registration, capture gates, scheduling policy,
  SQLite durability, STOP/forget, grounded brief fallback, follow-up correlation,
  and read-only calendar behavior with fictional fixtures.
- Stock plugin doctor and validator passed for that candidate.
- A real-model, real-clock Telegram chain with fictional data passed:
  native CLI conversation capture → native scheduled preparation brief → one
  post-event follow-up → simulated normal CLI reply → persisted next-step capture
  linked to its parent. Two labeled demo messages had Telegram API send
  acknowledgements. The isolated gateway and owned jobs were stopped afterward.

## Public-export recheck

The sanitized export was rerun against the clean stock v0.23.0 checkout:
**235 passed, 0 failed, 0 skipped**, with two upstream manifest-parser deprecation
warnings. Stock `plugins doctor . --ci` passed (one tool, two hooks);
`plugins validate . --install-deps --json` returned `ok: true`, security scan
`safe`, no core overrides and an empty warnings list. Ruff E9/F/C901 passed with
a complexity ceiling of 20. No live credentials or messaging were used in this
recheck. Optional probes needing removed private input now exit with an explicit
SKIP before model/context creation. No unit tests were removed or skipped; two
test files only replace a private numeric identity with a synthetic fixture ID.

## Limits

This is a sanitized summary of prior qualification, not raw or independently
replayable transport evidence. Raw logs/JSON receipts are intentionally excluded.
No claim is made that a person viewed the messages, that the plan/reply originated
on a phone, or that a complete inbound Telegram-DM round trip was demonstrated.
The automated inputs were native CLI chat, not impersonated Telegram user input.
Native Markdown body files from the final live run were pruned during teardown;
that retention gap is not filled with fabricated artifacts. No new live messages
are sent to qualify this public export.

Small historical capture samples were 3/5 at +4 minutes, 1/5 at +30 minutes and
5/5 for tomorrow 09:30; do not generalize them to overall accuracy. Unit tests
use fake models and blocked sockets. Public calendar providers were not contacted
in calendar tests. Stdout/handoff reservations are not delivery receipts, unknown
handoffs never retry automatically, and STOP cannot recall queued output.
