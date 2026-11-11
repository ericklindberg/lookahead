# Isolated fictional demonstration

Use a new dedicated test bot and test DM, never a production bot/profile.
The development harness assumes a sibling stock Hermes v0.23.0 checkout.
Set `LOOKAHEAD_DEMO_ROOT` to an absolute, dedicated directory on a spacious disk;
it must not overlap any live Hermes home. Supply `LOOKAHEAD_DEMO_CHAT_ID`,
`LOOKAHEAD_DEMO_USER_ID` and `LOOKAHEAD_TEST_BOT_USERNAME` explicitly.
Supply `TELEGRAM_BOT_TOKEN` and the evaluation model's `MINIMAX_API_KEY` through
an approved local secret environment, never chat, command arguments, screenshots,
or a committed file. The harness passes model credentials to stock `hermes auth
add` and writes the test bot token only to the isolated host's mode-600 `.env`.
These are host credentials, not plugin state. Remove the isolated home securely
when no longer needed. This harness is optional; ordinary plugin operation uses
stock host authentication and does not read credential files.

```sh
bash scripts/demo_up.sh
# Follow the freshly dated fictional lines printed by the harness.
bash scripts/demo_down.sh
```

The native PM installs tools first, then the Telegram extra in that same isolated
home. Wait for the connected gate. Do not run another gateway/acceptance harness
on the same token. Demo start explicitly resets only its stopped fictional plugin
state and owned jobs; it retains host sessions/dependencies/credentials.

Visible demo timing is 3-minute prep lead, 2-minute follow-up delay, zero spacing
and cap 6; quiet 22:00–08:00 still applies. Production defaults remain evening-before,
120-minute follow-up, 30-minute spacing and cap 3. Never use demo settings silently.

1. Send `/start` in the dedicated DM if necessary. Paste the printed Acorn plan
   without asking for a reminder. Check `/lookahead list` for actual capture.
2. Wait for the native scheduled preparation brief. It contains a quotation,
   local date/time, suggested preparation and an open question, not completed work.
3. Wait for one post-event question. Reply: “It went well. I will send the revised
   Acorn budget tomorrow at 10:00.” Check the parent→next-step link in the list.
4. Leave another follow-up unanswered to demonstrate no repeated nag. Show
   `/lookahead status`, then `/lookahead stop`, and run `demo_down.sh`.

Same-day capture is not reliable: small historical trials yielded 3/5 at +4 minutes,
1/5 at +30 minutes, 5/5 for tomorrow 09:30. These are not accuracy estimates.
An acknowledgement is not evidence of capture. Prefer tomorrow's plan and honest
elapsed-time cuts. A successful demo does not erase misses.

For a short video, clearly label cuts between capture, preparation and follow-up;
never force cron, edit due times or fast-forward the clock. Hide tokens, private
chats, account IDs, user names and notification previews. API send acknowledgement,
phone viewing and actual inbound phone input are different evidence levels.
The automated Telegram harness uses CLI input and does not prove the latter two.
Private receipts remain outside the repository and are not safe to publish as-is.
