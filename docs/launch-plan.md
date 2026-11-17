# Launch plan and copy

## Positioning
Do not sell "another tearsheet library". Sell **the robustness check**: most retail backtests look
great on the full sample and die in one regime. AlphaLedger shows the fold-by-fold truth in one command.

## Free → Paid funnel
1. GitHub repo (free, Apache-2.0) — the discovery layer. README headline: *one command, one HTML file, zero data leaving your machine.*
2. `alphaledger demo` — 3-second sample report, no data needed. This is the hook.
3. Free reports carry a **Pro analysis locked** card pointing at Gumroad.
4. Pro key = $39 one-time, lifetime updates.

## Where to post (English audience)
- r/algotrading, r/quant (read rules first; self-promo usually needs a value-first comment, not a link dump)
- X / Twitter: builder threads with the actual chart screenshots
- Hacker News "Show HN" — only after the repo has a demo GIF and a working `pip install`
- Quant forums / Discord servers where backtest review questions are common

## X post (English, 280 chars style)

> Backtests lie in one regime.
>
> I built AlphaLedger: one command turns a CSV of returns into a tearsheet with a fold-by-fold
> walk-forward verdict, Monte Carlo drawdown stress, and strategy comparison.
>
> Runs fully offline. Open-source core.
>
> `pip install alphaledger && alphaledger demo`
> → https://github.com/<account>/alphaledger

## Follow-up thread beats
1. Screenshot: equity + drawdown panel. "This is the part everyone posts."
2. Screenshot: monthly heatmap. "This is the part that hides the truth — three months carry the year."
3. Screenshot: walk-forward fold table. "Same strategy, split into 4 folds. Fold 3 has no edge."
4. Screenshot: Monte Carlo. "What your max drawdown could have been, if history reshuffled."
5. CTA: free repo + $39 Pro key.

## Compliance notes
- Never promise returns or imply the tool predicts markets. Keep the disclaimer in every listing.
- Do not use exchange logos or imply affiliation.
- State clearly that the core is Apache-2.0 and derived from QuantStats.
