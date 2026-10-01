#!/usr/bin/env python3
"""Revisión de respaldo + SOC — Reserva de Pance, interrupción EMCALI.

Aplica references/reglas-aprendidas.md:
  - offgrid = voltGridA/B/C < 5 V sostenido en las 3 fases (nunca == 0, nunca invstate)
  - latch_state 'open' solo cuenta si currentA/B/C del medidor = 0 en la última hora
  - estado de red solo se afirma si el último voltageA del medidor tiene < 30 min
  - timestamps de cada dispositivo/señal se revisan por separado (heartbeat != telemetría)
  - transiciones casi simultáneas entre casas (<60 s) se marcan como posible acción centralizada
Credenciales: METRUM_API_URL / METRUM_USERNAME / METRUM_PASSWORD (env).
Uso: python3 respaldo_pance.py [--fecha 2026-10-01] [--match 'pance|reserva']
"""
import argparse, json, os, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

BOG = timezone(timedelta(hours=-5))
BASE = os.environ["METRUM_API_URL"].rstrip("/")
TOK = None
OFFGRID_V = 5.0
STALE_MIN = 30

def call(method, path, body=None):
    global TOK
    if TOK is None and path != "/api/auth/login":
        TOK = call("POST", "/api/auth/login", {"username": os.environ["METRUM_USERNAME"],
                                               "password": os.environ["METRUM_PASSWORD"]})["token"]
    h = {"Content-Type": "application/json"}
    if TOK and path != "/api/auth/login":
        h["Authorization"] = f"Bearer {TOK}"
    req = urllib.request.Request(BASE + path, method=method, headers=h,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def num(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None

ATTRS = ["mettype", "gateway", "zone", "city", "sector", "conjunto", "invbrand", "invmodel",
         "invcap", "latch_state", "latch_output"]

def list_devices():
    out, page = [], 0
    while True:
        r = call("POST", "/api/entitiesQuery/find", {
            "entityFilter": {"type": "entityType", "entityType": "DEVICE"},
            "pageLink": {"page": page, "pageSize": 200},
            "entityFields": [{"type": "ENTITY_FIELD", "key": "name"}, {"type": "ENTITY_FIELD", "key": "type"}],
            "latestValues": [{"type": "ATTRIBUTE", "key": k} for k in ATTRS]})
        for row in r.get("data", []):
            lat = row.get("latest", {})
            d = {"id": row["entityId"]["id"],
                 "name": (lat.get("ENTITY_FIELD", {}).get("name") or {}).get("value"),
                 "dtype": (lat.get("ENTITY_FIELD", {}).get("type") or {}).get("value")}
            for k in ATTRS:
                d[k] = (lat.get("ATTRIBUTE", {}).get(k) or {}).get("value") or None
            out.append(d)
        if not r.get("hasNext"):
            return out
        page += 1

def classify(d):  # A.8
    mt = (d.get("mettype") or "").lower()
    if mt in ("solar", "red"): return mt
    if mt in ("inverter", "inversor"): return "inv"
    n = d.get("name") or ""
    if re.match(r"^IN\d", n): return "gw"
    if re.match(r"^HP", n) or re.match(r"^2[45]\d{8}$", n): return "inv"
    if d.get("invbrand") or d.get("invmodel"): return "inv"
    return "otro"

def ts(dev_id, keys, start, end):
    r = call("GET", f"/api/plugins/telemetry/DEVICE/{dev_id}/values/timeseries?keys={','.join(keys)}"
                    f"&startTs={start}&endTs={end}&agg=NONE&limit=20000")
    return {k: sorted(((p["ts"], p["value"]) for p in v), key=lambda x: x[0]) for k, v in r.items()}

def last_ts(dev_id, keys):
    r = call("GET", f"/api/plugins/telemetry/DEVICE/{dev_id}/values/timeseries?keys={','.join(keys)}")
    return {k: (v[0]["ts"] if v else None) for k, v in r.items()}

def fmt(t):
    return datetime.fromtimestamp(t / 1000, BOG).strftime("%m-%d %H:%M") if t else "—"

def offgrid_windows(series):
    """Ventanas con voltGridA/B/C < 5 V en las 3 fases, >=2 muestras seguidas."""
    pts = {}
    for k in ("voltGridA", "voltGridB", "voltGridC"):
        for t, v in series.get(k, []):
            pts.setdefault(t, {})[k] = num(v)
    win, cur = [], None
    for t in sorted(pts):
        vals = [x for x in pts[t].values() if x is not None]
        low = len(vals) > 0 and all(x < OFFGRID_V for x in vals)
        if low:
            cur = cur or [t, t, 0]
            cur[1], cur[2] = t, cur[2] + 1
        elif cur:
            win.append(cur); cur = None
    if cur: win.append(cur + ["abierta"])
    return [w for w in win if w[2] >= 2]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", default="2026-10-01")
    ap.add_argument("--match", default=r"pance|reserva", help="regex sobre nombre/atributos de zona")
    a = ap.parse_args()
    day = datetime.strptime(a.fecha, "%Y-%m-%d").replace(tzinfo=BOG)
    start = int((day - timedelta(hours=6)).timestamp() * 1000)          # 18:00 del día anterior
    now = int(time.time() * 1000)
    end = min(int((day + timedelta(days=1, hours=1)).timestamp() * 1000), now + 3600_000)

    devs = list_devices()
    rx = re.compile(a.match, re.I)
    gws_in = {d["gateway"] or d["name"] for d in devs
              if any(rx.search(str(d.get(k) or "")) for k in ("name", "zone", "city", "sector", "conjunto", "gateway"))}
    casas = {}
    for d in devs:
        g = d["gateway"] or d["name"]
        if g in gws_in:
            casas.setdefault(g, []).append(d | {"cls": classify(d)})
    print(f"# Casas en alcance ({len(casas)}): {sorted(casas)}", file=sys.stderr)

    res = []
    for g, ds in sorted(casas.items()):
        red = next((d for d in ds if d["cls"] == "red"), None)
        invs = [d for d in ds if d["cls"] == "inv"]
        row = {"casa": g, "flags": []}
        # Medidor de red
        if red:
            s = ts(red["id"], ["voltageA", "FlagStaProf", "currentA", "currentB", "currentC"], start, end)
            lt = last_ts(red["id"], ["voltageA", "activityState"])
            row["med_voltageA_ultimo"] = fmt(lt.get("voltageA"))
            row["med_heartbeat_ultimo"] = fmt(lt.get("activityState"))
            stale = not lt.get("voltageA") or (now - lt["voltageA"]) > STALE_MIN * 60_000
            row["red_estado"] = "sin dato reciente" if stale else "en vivo"
            cortes = [t for t, v in s.get("FlagStaProf", []) if num(v) == 128]
            row["FlagStaProf128"] = [fmt(cortes[0]), fmt(cortes[-1])] if cortes else None
            if red.get("latch_state") == "open":
                rec = [num(v) for k in ("currentA", "currentB", "currentC")
                       for t, v in s.get(k, []) if t > now - 3600_000]
                real = rec and all((x or 0) == 0 for x in rec)
                row["flags"].append("relé ABIERTO confirmado" if real else "latch_state=open OBSOLETO (hay corriente)")
            if stale:
                row["flags"].append("telemetría de medidor obsoleta: no se puede afirmar estado EMCALI")
        else:
            row["flags"].append("sin medidor de red identificado")
        # Inversor: elegir candidato con telemetría real (A.9)
        best = None
        for inv in invs:
            s = ts(inv["id"], ["voltGridA", "voltGridB", "voltGridC", "voltEpsA", "freqEps", "BattSOC",
                               "BattPower", "BattCur", "invrun", "invstate"], start, end)
            if s.get("BattSOC") or s.get("voltGridA"):
                best = (inv, s); break
        if not best:
            row["flags"].append("inversor sin telemetría en la ventana")
            res.append(row); continue
        inv, s = best
        row["inversor"] = f'{inv["name"]} ({inv.get("invbrand") or "?"} {inv.get("invmodel") or "?"})'
        lt = last_ts(inv["id"], ["voltGridA", "BattSOC"])
        row["inv_ultimo_dato"] = fmt(max(filter(None, lt.values()), default=None))
        soc = [(t, num(v)) for t, v in s.get("BattSOC", []) if num(v) is not None]
        win = offgrid_windows(s)
        row["offgrid"] = [{"inicio": fmt(w[0]), "fin": fmt(w[1]) if len(w) < 4 else "sigue", "ini_ms": w[0]} for w in win]
        if soc:
            row["SOC_ultimo"] = soc[-1][1]
        for w in row["offgrid"]:
            t0, t1 = w["ini_ms"], (win[row["offgrid"].index(w)][1])
            dur = [(t, v) for t, v in soc if t0 <= t <= t1]
            pre = [v for t, v in soc if t < t0]
            w["SOC_inicio"] = pre[-1] if pre else (dur[0][1] if dur else None)
            w["SOC_min"] = min((v for _, v in dur), default=None)
            eps = [num(v) for t, v in s.get("voltEpsA", []) if t0 <= t <= t1 and num(v) is not None]
            w["EPS_ok_pct"] = round(100 * sum(x > 100 for x in eps) / len(eps)) if eps else None
            w["invrun"] = sorted({v for t, v in s.get("invrun", []) if t0 <= t <= t1})
            bp = [num(v) for t, v in s.get("BattPower", []) if t0 <= t <= t1 and num(v) is not None]
            w["BattPower_rango"] = [min(bp), max(bp)] if bp else None
            if w["EPS_ok_pct"] is not None and w["EPS_ok_pct"] < 90:
                row["flags"].append(f"respaldo incompleto: EPS >100V solo {w['EPS_ok_pct']}% de la ventana")
            if w["SOC_min"] is not None and w["SOC_min"] <= 20:
                row["flags"].append(f"SOC bajó a {w['SOC_min']}% durante el corte")
            if dur and max(v for _, v in dur) - min(v for _, v in dur) < 2 and (dur[0][1] >= 97):
                row["flags"].append("SOC fijo ≥97% durante el corte: batería no descargó (patrón 18PR)")
        if soc and all(v == 0 for _, v in soc):
            row["flags"].append("SOC 0% todo el período")
        res.append(row)

    # Simultaneidad (regla 2026-09-29)
    starts = sorted((w["ini_ms"], r["casa"]) for r in res for w in r.get("offgrid", []))
    grupos, g = [], []
    for t, c in starts:
        if g and t - g[-1][0] > 60_000:
            grupos.append(g); g = []
        g.append((t, c))
    if g: grupos.append(g)
    sim = [[c for _, c in gr] for gr in grupos if len(gr) > 1]

    json.dump({"fecha": a.fecha, "generado": fmt(now), "casas": res, "transiciones_simultaneas": sim},
              open(f"respaldo_pance_{a.fecha}.json", "w"), ensure_ascii=False, indent=1, default=str)
    for r in res:
        print(json.dumps({k: v for k, v in r.items()}, ensure_ascii=False, default=str))
    if sim:
        print("\n⚠ Offgrid simultáneo (<60 s) — revisar marca/modelo antes de despachar:", sim)

if __name__ == "__main__":
    main()
