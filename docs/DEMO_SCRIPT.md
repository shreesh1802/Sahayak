# Demo video script (target 2:40, hard limit 3:00)

Judges are not required to watch past 3:00, so the best material comes first. Record the screen with voiceover
(Windows: Win+G, or OBS). Upload to YouTube or Vimeo as **public**. English only. No music.

## Before recording (2 minutes)
1. Terminal 1, from the repo root: `python -m server.mcp_server`
2. Terminal 2: `python -m web.app`
3. Use a **fresh database** so the loans screen starts empty:
   delete `demo.db` first and start the server with `SAHAYAK_DB=demo.db` (PowerShell: `$env:SAHAYAK_DB="$PWD\demo.db"`).
4. Open http://127.0.0.1:8080 in a clean browser window, zoom to about 110%, close other tabs.
5. Keep a third terminal ready with `python -m pytest -q` and `python -m eval.smoke` already typed.
6. Do one silent dry run, then restart the server with a fresh database before recording.

## Shot list

| Time | On screen | Say (suggested) |
|---|---|---|
| 0:00–0:15 | The empty Sahayak screen | "Millions of first-time borrowers sign loans they don't understand. 'Twelve percent flat' sounds like twelve percent, and fees are taken before the cash arrives. Sahayak is an Alexa+ add-on that explains what a loan really costs, out loud." |
| 0:15–1:00 | Click **Explain a loan**. Wait for the follow-up question, then type or say "flat". Hold on the card. | "I was offered fifty thousand rupees at twenty-four percent, with a two thousand fee. Notice the server asks me a follow-up: flat or reducing? That's MCP elicitation. Now: fifty-one sixty-seven a month, I only receive forty-eight thousand, and the *true* yearly cost is sixty-three percent, not twenty-four." Point at the **Flat vs reducing** warning. |
| 1:00–1:20 | Click **Tell my budget**, then **Can I afford it?** | "It remembers my income and spending, then checks whether the payment is realistic and explains why." |
| 1:20–1:50 | Click **Save a loan**, **Log a payment**, **My loans** | "It tracks my loans and repayments across conversations, so the coaching builds up over time." |
| 1:50–2:05 | Click **Teach me** | "And it teaches one short lesson at a time, with a quiz question." |
| 2:05–2:35 | Switch to the terminal: run `python -m eval.smoke` (or show its saved output) and point at the PASS lines, the spec version line and the latency line | "Under the hood this is a real MCP server over Streamable HTTP, spec 2025-11-25. It exposes seven tools and answers in about eight milliseconds, well inside Alexa+'s five hundred millisecond budget. Every number comes from a calculator, never from a language model." |
| 2:35–2:50 | Back to the browser, or show the README limitations section | "I tested with a simulated Alexa+ screen, not a real device. The code is open source on GitHub. Sahayak: financial education, in your own words." |

## Rules to follow in the video
- **Say out loud that the screen is a simulated Alexa+ experience.** The rules allow it, but the video must show it clearly.
- Don't show any API keys, AWS console pages or personal details.
- Keep a card on screen long enough to read (3 seconds).
- Don't claim anything that isn't running: no Bedrock, no real Alexa+ device.

## Phrases the router understands (use these exactly)
- `I was offered a loan of 50000 at 24 percent for 12 months with a fee of 2000`  → then answer `flat`
- `my income is 25000 and my expenses are 14000`
- `can I afford 4500 a month` (for a "tight" result, try `can I afford 9000 a month`)
- `add a loan called shop credit of 12000 at 18 percent for 12 months reducing`
- `I paid 2000 on loan 1`
- `show my loans`
- `teach me something`
