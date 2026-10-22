# Demo video script (target 2:55, hard limit 3:00; trim the lesson shot if you run long)

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
| 0:15–1:05 | Click **Review an offer**. Answer the first follow-up with "flat", the second with "my income is 25000 and expenses 14000". Hold on the card, then scroll to **Ask the lender**. | "I was offered fifty thousand rupees at twenty-four percent, with a two thousand fee. The server asks me two follow-ups, flat or reducing and my budget: that's MCP elicitation. Fifty-one sixty-seven a month, I only receive forty-eight thousand, and the *true* yearly cost is sixty-three percent, not twenty-four. It tells me what to ask the lender." Point at the **Flat vs reducing** warning. |
| 1:05–1:25 | Scroll to **Behind the scenes** and read the agent lines slowly | "The card on the screen is not drawn by the page: it's an MCP App served by my server, shown in a sandboxed frame, and every message is listed here. Alexa+ made one call. Behind it a supervisor planned and re-planned: a loan analyst, an affordability agent, a coach, and a verifier that checks every spoken number against the calculator." *(Say plainly that these agents are rule-based, not language models.)* |
| 1:25–1:35 | Type `can I afford 9000 a month` | "Change the payment and it says tight, with the reason." |
| 1:35–2:05 | Click **Save a loan**, **Log a payment**, **My loans** | "It tracks my loans and repayments across conversations, so the coaching builds up over time." |
| 2:05–2:15 | Click **Teach me** | "And it teaches one short lesson at a time, with a quiz question." |
| 2:15–2:40 | Switch to the terminal: run `python -m eval.smoke` (or show its saved output) and point at the PASS lines, the spec version line and the latency line | "Under the hood this is a real MCP server over Streamable HTTP, spec 2025-11-25. It exposes eight tools and answers in well under a hundred milliseconds, far inside Alexa+'s five hundred millisecond budget. Every number comes from a calculator, never from a language model." |
| 2:40–2:55 | Back to the browser, or show the README limitations section | "I tested with a simulated Alexa+ screen, not a real device. The code is open source on GitHub. Sahayak: financial education, in your own words." |

## Rules to follow in the video
- **Say out loud that the screen is a simulated Alexa+ experience.** The rules allow it, but the video must show it clearly.
- Don't show any API keys, AWS console pages or personal details.
- Keep a card on screen long enough to read (3 seconds).
- Don't claim anything that isn't running: no Bedrock, no real Alexa+ device.

## Phrases the router understands (use these exactly)
- `should I take a loan of 50000 at 24 percent for 12 months with a fee of 2000`  → answer `flat`, then `my income is 25000 and expenses 14000` (the **Review an offer** button)
- `I was offered a loan of 50000 at 24 percent for 12 months with a fee of 2000`  → single-agent explanation (the **Explain a loan** button)
- `my income is 25000 and my expenses are 14000`
- `can I afford 4500 a month` (for a "tight" result, try `can I afford 9000 a month`)
- `add a loan called shop credit of 12000 at 18 percent for 12 months reducing`
- `I paid 2000 on loan 1`
- `show my loans`
- `teach me something`
