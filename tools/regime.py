#!/usr/bin/env python3
"""Deterministische regime-classificatie uit Crypto.com-candles.

Gebruik:
    python3 tools/regime.py candles.json > regime.json

candles.json:
    {"BTC_USD": {"1D": [<candles>], "4h": [<candles>]}, "ETH_USD": {...}, ...}
waarbij elke candle het formaat van Crypto.com get_candlestick heeft
(open/high/low/close/volume/timestamp, als strings of getallen). Volgorde maakt niet uit.

Uitvoer per instrument: regime (bull/bear/sideways), trend_strength, volatility,
confidence en de ruwe indicatoren, zodat de bot en een mens kunnen nagaan waarom.
Dit is classificatie van wat er al gebeurd is, geen voorspelling.
"""
import json
import sys


def _f(x):
    return float(x)


def ema(values, period):
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def atr_series(c, period=14):
    trs = []
    for i in range(1, len(c)):
        h, l, pc = c[i]["high"], c[i]["low"], c[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return []
    out = [sum(trs[:period]) / period]
    for tr in trs[period:]:
        out.append((out[-1] * (period - 1) + tr) / period)
    return out


def adx(c, period=14):
    if len(c) < 2 * period + 1:
        return None
    pdm, ndm, trs = [], [], []
    for i in range(1, len(c)):
        up = c[i]["high"] - c[i - 1]["high"]
        dn = c[i - 1]["low"] - c[i]["low"]
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)
        h, l, pc = c[i]["high"], c[i]["low"], c[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))

    def wilder(xs):
        s = [sum(xs[:period])]
        for x in xs[period:]:
            s.append(s[-1] - s[-1] / period + x)
        return s

    str_, spdm, sndm = wilder(trs), wilder(pdm), wilder(ndm)
    dxs = []
    for t, p, n in zip(str_, spdm, sndm):
        if t == 0:
            dxs.append(0.0)
            continue
        pdi, ndi = 100 * p / t, 100 * n / t
        dxs.append(0.0 if pdi + ndi == 0 else 100 * abs(pdi - ndi) / (pdi + ndi))
    if len(dxs) < period:
        return None
    a = sum(dxs[:period]) / period
    for d in dxs[period:]:
        a = (a * (period - 1) + d) / period
    return a


def normalize(raw):
    c = [
        {
            "ts": x["timestamp"],
            "open": _f(x["open"]),
            "high": _f(x["high"]),
            "low": _f(x["low"]),
            "close": _f(x["close"]),
        }
        for x in raw
    ]
    c.sort(key=lambda x: x["ts"])
    return c


def trend(c, fast, slow):
    """+1 opwaarts, -1 neerwaarts, 0 geen duidelijke richting."""
    closes = [x["close"] for x in c]
    ef, es = ema(closes, fast), ema(closes, slow)
    slope = (es[-1] - es[-6]) / es[-6] if len(es) > 6 else 0.0
    last = closes[-1]
    if last > es[-1] and ef[-1] > es[-1] and slope > 0:
        d = 1
    elif last < es[-1] and ef[-1] < es[-1] and slope < 0:
        d = -1
    else:
        d = 0
    return d, ef[-1], es[-1], slope


def classify(daily_raw, h4_raw):
    d = normalize(daily_raw)
    if len(d) < 30:
        return {"status": "insufficient_data", "candles_daily": len(d)}

    d_dir, ema_f, ema_s, slope = trend(d, 10, 30)
    a = adx(d) or 0.0

    h4_dir = None
    if h4_raw:
        h = normalize(h4_raw)
        if len(h) >= 30:
            h4_dir, *_ = trend(h, 10, 30)

    # Volatiliteit: huidige ATR% t.o.v. mediaan over het venster
    atrs = atr_series(d)
    closes = [x["close"] for x in d]
    atr_pct = [atrs[i] / closes[i + 14] for i in range(len(atrs))]
    cur = atr_pct[-1]
    med = sorted(atr_pct)[len(atr_pct) // 2]
    ratio = cur / med if med else 1.0
    if ratio < 0.75:
        vol = "low"
    elif ratio < 1.3:
        vol = "normal"
    elif ratio < 1.8:
        vol = "high"
    else:
        vol = "extreme"

    if a < 20 or d_dir == 0:
        regime = "sideways"
    else:
        regime = "bull" if d_dir == 1 else "bear"

    # Confidence: ADX-sterkte, plus/min eens met 4h-trend
    conf = 0.5 if regime == "sideways" and a < 15 else min(a / 40, 1.0) * 0.8
    if h4_dir is not None:
        want = {"bull": 1, "bear": -1, "sideways": 0}[regime]
        conf += 0.2 if h4_dir == want else -0.15
    conf = round(max(0.05, min(conf, 0.95)), 2)

    return {
        "status": "ok",
        "regime": regime,
        "trend_strength": round(min(a / 50, 1.0), 2),
        "volatility": vol,
        "confidence": conf,
        "indicators": {
            "close": round(closes[-1], 8),
            "ema10_d": round(ema_f, 8),
            "ema30_d": round(ema_s, 8),
            "ema30_slope_5d": round(slope, 5),
            "adx14_d": round(a, 2),
            "atr14_pct": round(cur, 5),
            "atr_ratio_vs_median": round(ratio, 2),
            "h4_trend": h4_dir,
            "last_candle": d[-1]["ts"],
            "candles_daily": len(d),
        },
    }


def main():
    data = json.load(open(sys.argv[1]))
    out = {}
    for inst, tf in data.items():
        try:
            out[inst] = classify(tf.get("1D", []), tf.get("4h", []))
        except Exception as e:  # nooit de hele run laten klappen op één coin
            out[inst] = {"status": "error", "error": str(e)[:200]}
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
