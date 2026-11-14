"""One shape for every chart: the screen draws it as a chart and as a table, and the CSV export is the same rows.

A series is {key, unit, kind, points: [{key, label_en?, label_ar?, value, n}]}. `unit` is count, hours, percent or money (then
`currency` is set). `n` is how many records the value rests on; a value is None when there is nothing to base it on.
"""


def point(key, value, n=None, label_en=None, label_ar=None):
    p = {"key": key, "value": value, "n": n if n is not None else (value if isinstance(value, int) else None)}
    if label_en is not None:
        p["label_en"], p["label_ar"] = label_en, label_ar or label_en
    return p


def series(key, unit, points, currency=None, kind="bar"):
    s = {"key": key, "unit": unit, "kind": kind, "points": points}
    if currency:
        s["currency"] = currency
    return s


def pct(part, whole):
    return round(part * 100 / whole, 1) if whole else None


def avg_hours(deltas):
    """Average of timedeltas in hours, with how many there were. None when there are none."""
    return (round(sum(d.total_seconds() for d in deltas) / len(deltas) / 3600, 1) if deltas else None), len(deltas)


def csv_rows(report):
    """Flatten a report into (section, series, label, value, unit, based_on) rows for download."""
    rows = []
    for s in report.get("series", []):
        unit = s["unit"] + (" " + s["currency"] if s.get("currency") else "")
        for p in s["points"]:
            rows.append([report["section"], s["key"], p.get("label_en") or p["key"], "" if p["value"] is None else p["value"], unit, "" if p["n"] is None else p["n"]])
    return rows
