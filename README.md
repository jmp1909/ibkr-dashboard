# IBKR Portfolio & FIRE Dashboard

Pulls your Interactive Brokers account, reconstructs your deposit history, computes
**money-weighted returns**, and writes a single self-contained interactive HTML file.

Everything personal lives in `config.json` — your account, goals, savings phases and
target allocation. The code has nothing about you in it.

## ▶ Try it — [live demo](https://jmp1909.github.io/ibkr-dashboard/)

**[jmp1909.github.io/ibkr-dashboard](https://jmp1909.github.io/ibkr-dashboard/)** — the real
dashboard running on sample data. Drag the sliders, hover the charts. Nothing to install, and
no account involved.

[![Overview](docs/screenshots/overview.png)](https://jmp1909.github.io/ibkr-dashboard/)

## What it shows

| Section | |
|---|---|
| Hero band | Portfolio value, contributions, growth, return, years to target |
| 01 Holdings | Positions with cost basis, true total return, and fund look-through to real regional exposure |
| 02 Drift from target | Target vs actual weights, plus a **buy-only** allocator that points your next contribution at whatever has fallen furthest behind |
| 03 Saved vs market | Your deposits against total value — how much of your wealth is savings rather than returns |
| 04 Money-weighted returns | XIRR over standard windows, from cash flows reconstructed out of the NAV and TWR series |
| 05 Currency | Splits return into asset performance vs exchange-rate movement, with look-through to the currencies actually inside your funds |
| 06 Milestones | Real crossing dates for milestones you've passed, projected dates for the rest |
| 07 The two finish lines | Coast FIRE and full FIRE on an editable life plan: a draggable timeline of phases and one-off events, a yearly chart of income, saving and investment return, and the crossover year when your portfolio starts out-earning your saving |

Charts have hover readouts. The output is one HTML file with no external dependencies, so
you can email it to yourself or open it offline.

## Requirements

- **Python 3.10+**
- **A Java runtime** (JRE 8u192 or later) — needed by IBKR's gateway, not by this project.
  [Eclipse Temurin](https://adoptium.net) works.
- **An Interactive Brokers account.**

## Setup

```
git clone https://github.com/jmp1909/ibkr-dashboard.git
cd ibkr-dashboard
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Try it with bundled sample data — no IBKR account or gateway needed:

```
.venv\Scripts\python.exe src\main.py --demo
```

That writes `dashboard.html`. If it looks right, set up live data.

## Configure

Copy `config.example.json` to `config.json`, then edit it:

| Block | Required | What it controls |
|---|---|---|
| `person.birth_date` | yes | Drives every age on the projection |
| `goal.target` | yes | The number you're aiming at |
| `goal.real_return` | yes | Assumed return after inflation and fees |
| `goal.withdrawal_rate` | yes | Sets the income your target funds |
| `goal.coast_full_age` | yes | Age the coast portfolio must reach the target by, unaided |
| `goal.milestones` | no | Explicit milestone ladder. Omit it and one is generated to fit your target |
| `phases[]` | yes | Your savings timeline — see below |
| `events[]` | no | One-off lump sums: a bonus, an inheritance, or a purchase (negative) |
| `targets` | no | Intended allocation. Must sum to 1. Omit to hide the drift section |
| `lookthrough` | no | Regional split inside each fund, from its factsheet |
| `currency_basket` | no | Currencies held *inside* each fund — not the one it's priced in |
| `currency.enabled` | no | Set false if your funds report in the currency you spend |
| `account.display_currency` | yes | The currency your figures are shown in — see the note below |
| `output.locale` | no | Number formatting, e.g. `en-US` → 1,234,567 · `de-CH` → 1'234'567 · `de-DE` → 1.234.567 |

### A note on currency

`display_currency` **labels** your figures; it does not convert them. IBKR reports your
account in whatever base currency the account itself is set to, and that's the number this
tool receives. So set `display_currency` to match your IBKR base currency — if they
disagree the run prints a warning, because otherwise you'd be reading one currency's
numbers under another's name. To genuinely change the currency, change the account's base
currency in IBKR.

Separately, `currency.asset_currency` is the currency your *funds report in* (often USD).
When that differs from what you spend, section 05 splits your return into what the
investments did and what the exchange rate did.

### Phases

`phases[]` is a list of any length. Each entry is a period with its own income and saving,
so it fits whatever your life actually looks like — not a fixed student → career
template. A promotion, a lower savings rate, a career break: each is just another phase.

```json
{ "id": "break", "label": "Career break", "start": "2032-01", "end": "2032-12",
  "monthly_income": 0, "savings_rate": 0.0, "income_growth": 0.0 }
```

A phase saves either a share of its income (the default: `monthly_income * savings_rate`)
or a fixed amount regardless of income:

```json
{ "id": "masters", "label": "Master's", "start": "2027-09", "end": "2029-06",
  "monthly_income": 900, "saving_mode": "fixed", "monthly_saving": 250 }
```

`end: null` means open-ended. `income_growth` is real annual growth above inflation, counted
from the later of the phase's start and today. Phases **can't overlap** — each month
belongs to at most one — and a gap between phases simply saves nothing. Phases that have
already ended are ignored by the projection but kept, so you can leave them as a record.

The projection always starts from the month of your latest data. A phase that began earlier
shows as starting "now".

### One-off events

```json
"events": [
  { "date": "2030-06", "label": "Inheritance", "amount": 20000 },
  { "date": "2035-03", "label": "Flat deposit", "amount": -60000 }
]
```

### Editing the plan on the dashboard

You don't have to edit JSON. In section 07:

- **Drag** a phase's edges to change when it starts and ends, or drag the middle to move it.
  Where two phases touch, the shared edge moves both; nothing can be moved into the past.
  Arrow keys work too (Shift moves a year). The timeline shows the next 10 years by default
  so short phases are wide enough to grab — switch to 5, 20 or all.
- **Add phase** splits the open-ended last phase; **×** removes one and lets its neighbour
  take over the freed months. Each phase can be renamed and switched between "% of income"
  and "fixed amount" without its current saving jumping.
- **One-off events** are diamonds on the timeline; drag them, or edit name and amount below.

Changes are kept in your browser across reloads. They don't touch `config.json` until you
choose to: **Copy as config** gives you the `goal`, `phases` and `events` blocks to paste in,
and **Reset to config** throws the browser edits away. If `config.json` changes while you
have browser edits, the page tells you and lets you pick which to keep, rather than silently
choosing one.

### Sections that disable themselves

The dashboard hides what it can't describe honestly, so a minimal config still produces a
clean page:

- **no `targets`** → the drift and next-buy section disappears
- **no `lookthrough` entry for your holdings** → the regional exposure panel disappears
  rather than inventing a split
- **no `currency_basket` entry** → the currency-denomination panel disappears
- **`currency.enabled: false`**, or assets and spending in the same currency → the whole
  currency section disappears

The bundled `lookthrough` and `currency_basket` values describe one specific set of ETFs
(VT and some Avantis funds). **If you hold different funds, replace them** — otherwise
those panels describe someone else's portfolio rather than yours.

## Live data

IBKR has no simple REST API. You run a local gateway that proxies authenticated requests.

1. Download the [Client Portal Gateway](https://download2.interactivebrokers.com/portal/clientportal.gw.zip).
2. Unzip it so `clientportal.gw` sits **next to this project folder** (or set
   `IBKR_GATEWAY_HOME` to wherever you put it).
3. Create the one-click launcher:

```
powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
```

That puts **Refresh Dashboard** on your Desktop. Double-click it and it will:

- clear any leftover gateway processes and start a clean one
- open your browser at `https://localhost:5000` for you to log in
- wait for you, pull your data, write `dashboard.html`, and shut the gateway down again

You log in yourself — the script never handles your credentials.

> **Sessions expire after roughly 24 hours** and re-authentication needs a browser. That's
> IBKR's design and no script can work around it. For a genuinely unattended pull, IBKR's
> Flex Query route (scheduled statements delivered by token) is the only reliable option —
> end-of-day only, which for a buy-and-hold portfolio is usually fine.

### Without the launcher

```
cd clientportal.gw
bin\run.bat root\conf.yaml
```

Leave that running, log in at `https://localhost:5000`, then:

```
.venv\Scripts\python.exe src\main.py
```

## How the returns are computed

IBKR reports time-weighted return, which deliberately ignores deposits and withdrawals.
That answers "how did the funds do", not "how did *my money* do" — and while you are
contributing heavily those differ a lot.

So the external cash flows are recovered from the NAV and return series:

```
flow_t = NAV_t - NAV_t-1 * (1 + r_t)
```

Any change in value that the day's return does not explain must be a transfer. An internal
rate of return is then solved over those flows. Replaying the reconstructed flows forward
reproduces the final NAV exactly, which is a reasonable check that the reconstruction is
sound — worth re-checking on your own data rather than trusting it blindly.

`data/nav_history.json` accumulates every pull, because IBKR's performance endpoint only
reaches back about a year — the 3- and 5-year windows fill in on their own over time.

## Notes

- `--demo` uses a separate history file, so experimenting never touches real data.
- `--no-open` skips launching the browser; `-v` gives verbose logging.
- Windows-only launcher. The Python side is cross-platform; on macOS/Linux run
  `bin/run.sh root/conf.yaml` and `python src/main.py` yourself.
- Projections are deterministic: a constant real return every month, ignoring
  sequence-of-returns risk, tax, and any local pension system. They show the shape of the
  problem, not a forecast.

**Not investment advice.** The allocator does arithmetic against targets *you* set; it
never suggests selling, and it knows nothing about your circumstances.

## Licence

MIT
