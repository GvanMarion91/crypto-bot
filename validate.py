#!/usr/bin/env python3
"""Valideer een strategiebriefing: schema + logische checks.

    python3 validate.py strategy/latest.json
Exitcode 0 = OK. Draai dit ook op de Pi vóór je een nieuwe briefing gebruikt.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def check(path):
    doc = json.loads(Path(path).read_text())
    schema = json.loads((HERE / "schema.json").read_text())
    jsonschema.validate(doc, schema, format_checker=jsonschema.FormatChecker())

    errs = []
    gen, until = ts(doc["generated_at"]), ts(doc["valid_until"])
    if gen.tzinfo is None or until.tzinfo is None:
        errs.append("tijden moeten een tijdzone hebben (Z of +00:00)")
    elif not (timedelta(0) < until - gen <= timedelta(hours=36)):
        errs.append("valid_until moet na generated_at liggen en max 36 uur later")

    assets = doc["assets"]
    b = doc["market"]["breadth"]
    counts = {"bull": 0, "bear": 0, "sideways": 0}
    for a in assets.values():
        counts[a["regime"]] += 1
    if counts != b:
        errs.append(f"breadth {b} klopt niet met assets {counts}")

    known = set(assets) | {"ALL"}
    for w in doc["chaos_windows"]:
        if ts(w["end_utc"]) <= ts(w["start_utc"]):
            errs.append(f"chaos-venster eindigt vóór start: {w['reason']}")
        for x in w["assets"]:
            if x not in known:
                errs.append(f"onbekend asset in chaos-venster: {x}")
    for e in doc["events"]:
        for x in e["assets"]:
            if x not in known:
                errs.append(f"onbekend asset in event: {x}")

    order = ["low", "elevated", "high", "extreme"]
    for name, a in assets.items():
        if a["volatility"] == "extreme" and order.index(a["risk_level"]) < 2:
            errs.append(f"{name}: extreme volatiliteit maar risk_level {a['risk_level']}")
        if a["risk_level"] == "extreme" and a["tradable"]:
            errs.append(f"{name}: risk_level extreme maar tradable=true")

    if doc["status"] == "degraded":
        for name, a in assets.items():
            if a["tradable"]:
                errs.append(f"degraded briefing maar {name} tradable=true")

    if errs:
        raise ValueError("; ".join(errs))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("gebruik: validate.py <briefing.json>")
    try:
        check(sys.argv[1])
    except Exception as e:
        print(f"FOUT: {e}")
        sys.exit(1)
    print("OK")
