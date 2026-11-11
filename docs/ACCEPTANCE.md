# Acceptance on stock Hermes

Qualification used an unmodified stock Hermes v0.23.0 checkout.
The concise results and limitations are in [TEST-EVIDENCE.md](TEST-EVIDENCE.md).
Raw gateway logs, transport transcripts, credentials and account identifiers are
not distributed. The summary is not a substitute for transport receipts.

## Reproduce offline checks

```sh
STOCK_ROOT=<stock-hermes-checkout> ENV_ROOT=<isolated-test-root> bash scripts/test.sh
hermes plugins doctor . --ci
hermes plugins validate . --install-deps --json
```

The test launcher creates a fresh HOME/HERMES_HOME. No live model or platform is
used by unit tests. Run plugin CLI validation in a disposable profile too.

## Optional live qualification

The scripts are operator-run development harnesses, not plugin startup code.
Use a dedicated test bot and isolated home, fictional messages, and explicit
permission before any live send. See [DEMO-SCRIPT.md](DEMO-SCRIPT.md).
`acceptance_stock.py` uses a local scripted transport/provider; it proves wiring,
not model accuracy. `acceptance_telegram.py` sends at most two labeled messages
through the native elapsed scheduler, then verifies a CLI-seeded next-step link.
It is not an inbound phone-DM round trip. Never force ticks or change the clock
and call that spontaneous scheduled delivery. Private outputs go to a sibling
`lookahead-private-evidence` directory, outside the repository. Review them before
sharing: token redaction does not remove personal information or account IDs.
