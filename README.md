# crypto-bot — strategiebriefings

Twee keer per dag (07:00 en 19:00 Amsterdam, ook in het weekend) zet een geplande Claude-taak hier een nieuwe briefing neer:

- `strategy/latest.json` — altijd de meest recente, dit leest de bot
- `strategy/JJJJ-MM-DD-ochtend.json` / `-avond.json` — archief

Het formaat staat in `schema.json`; `validate.py` controleert schema én logica.

## Wat er in staat

**Per coin** (`assets`, bijv. `BTC_USD`): `regime` (bull/bear/sideways), `trend_strength`, `volatility`, `risk_level`, `confidence`, `tradable` en de ruwe indicatoren. Het regime komt uit `tools/regime.py`: een vaste berekening op Crypto.com-dagcandles (EMA10/30, helling, ADX14) met de 4h-trend als bevestiging. Geen gevoel, geen gok — dezelfde candles geven dezelfde uitkomst.

**Markt** (`market`): het totaalregime (BTC weegt het zwaarst), breadth (hoeveel coins in welk regime), nieuwssentiment −2…+2, thema's en een korte samenvatting.

**Agenda**: `events` en `chaos_windows` — tijdvakken rond grote events (Fed, CPI, grote unlocks, ETF-besluiten, beurs-incidenten) waarin de bot beter geen nieuwe posities opent.

Wat er níet in staat: koop/verkoop-signalen, koersdoelen of voorspellingen. Welke sub-bot of strategie bij welk regime hoort, beslist de bot zelf.

## Aanbevolen regels aan de Pi-kant

```
git pull --ff-only
python3 validate.py strategy/latest.json || → veilige modus
```

1. **Verlopen?** `valid_until` in het verleden → veilige modus: geen nieuwe posities, bestaande alleen beheren.
2. **`status: degraded`** → veilige modus (alle coins staan dan op `tradable: false`).
3. **`tradable: false`** voor een coin → geen nieuwe posities in die coin.
4. **Chaos-venster actief** voor een coin of `ALL` → geen nieuwe posities.
5. **`risk_level` high** → kleinere positie; **extreme** → niet handelen.
6. **Lage `confidence`** (< 0,4) → behandel het regime als `sideways`.

Een regimewissel is een reden om van sub-bot te wisselen, niet om open posities paniekerig dicht te gooien — dat is de taak van je eigen stops.

## Disclaimer

Dit is marktanalyse voor eigen gebruik, geen financieel advies. Crypto is volatiel; test elke strategie eerst op papier en handel alleen met geld dat je kunt missen.
