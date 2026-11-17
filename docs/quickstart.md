# AlphaLedger Pro — quick start for buyers

1. **Install the tool** (the free and Pro versions are the same code; the key unlocks Pro):

   ```bash
   pip install alphaledger          # or: pip install "alphaledger[license]"
   alphaledger demo                 # sanity check: synthetic data + sample report
   ```

2. **Install your key** — save the `license_xxxx.json` file you received from Gumroad to:

   ```
   ~/alphaledger-license.json
   ```

   or point the environment variable at it:

   ```bash
   export ALPHALEDGER_LICENSE=/path/to/license_xxxx.json
   ```

3. **Confirm the tier**:

   ```bash
   alphaledger license
   # Pro license · you@example.com · expires 2027-01-01
   ```

4. **Run a Pro report**:

   ```bash
   alphaledger report -i your_returns.csv \
       --name "My strategy" \
       --walkforward --montecarlo \
       --compare peers/strategy_a.csv peers/strategy_b.csv \
       -o report.html
   ```

   Open `report.html` in any browser. Single file, no external assets.

5. **Or use the UI**: `alphaledger serve` → http://127.0.0.1:8765, drag in your CSV,
   tick Walk-forward / Monte Carlo.

## License terms
- Per-seat, unlimited reports, lifetime use for the purchased period.
- No activation server, no telemetry, works offline.
- Key file is signed with Ed25519; editing the file invalidates it.
- Support: reply to the Gumroad receipt email.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `Pro feature` message but key installed | check `alphaledger license` shows the path; re-export `ALPHALEDGER_LICENSE` |
| `no numeric column found` | CSV needs a date column plus a return / equity column; see README "Input formats" |
| Report is huge | charts are embedded as PNG by design so the file works offline; that is ~400 KB–1.5 MB |
| Sharpe looks off | make sure returns are fractions (`0.01`, not `1.0`); price series are auto-converted |
