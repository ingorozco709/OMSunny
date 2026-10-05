#!/usr/bin/env python3
"""Reporte diario O&M de Proyecto Sunny (ultimas 24 h) desde la telemetria de Metrum.

Uso:  python3 om-agency/scripts/reporte_diario.py --out /tmp/reporte.html [--horas N]
      (sin --horas: 72 h los lunes para cubrir el fin de semana, 24 h el resto de la semana)

Credenciales: variables de entorno METRUM_API_URL, METRUM_USERNAME, METRUM_PASSWORD.
Escribe el HTML (pagina completa para publicar como artefacto) y un resumen de texto por stdout.

Metodo (mismo del reporte mensual):
  * Interrupcion del OR     = pares po -> pr del medidor de red.
  * Interrupcion percibida  = pares po -> pr del medidor solar.
  * Respaldo                = interrupcion OR - interrupcion percibida (minimo 0).
  * Generacion              = demanda (medidor solar) - importacion + exportacion (medidor de red),
                              con los acumulados energyAI/energyAE de 15 min.
  * Exportacion activa      = energyAE del medidor de red.
Se excluyen "Piloto Promigas", "Piloto Huawei" y la zona Castellana Real (aun no entregada a operaciones).
"""
import re
import argparse, datetime as dt, html, json, os, statistics as st, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
BOG = dt.timezone(dt.timedelta(hours=-5))
EXCLUIR = {"Piloto HUAWEI", "Piloto Promigas"}
# Zonas fuera del analisis: Castellana Real aun no se entrega a operaciones (etapa de estabilizacion).
EXCLUIR_ZONAS = {"CASTELLANA REAL"}
# Sistemas energizados solo con baterias en modo respaldo, sin paneles instalados aun (obra pendiente).
# Ademas de esta lista, todo sistema con generacion neta negativa en la ventana se trata igual.
SIN_PANELES = {"Casa 412p", "Casa 415p", "Casa 447p"}
GAP_EVENTO = 15 * 60e3     # cortes del OR mas cercanos que esto forman un solo evento
PRE, POST = 2 * 60e3, 15 * 60e3
MIN = 60.0
# Clasificacion del tiempo sin respaldo segun el SOC (regla del 05/10/2026): una casa que se queda sin energia
# durante un corte de red puede deberse a bateria sin carga (consumo del cliente) o a falla/demora del equipo.
PISO_SOC = 21.0            # % : bateria en el piso de descarga al apagarse la casa
T_INICIO, T_FIN = 180.0, 90.0   # s : ventana de transicion a OFF-GRID (inicio del corte) y de retorno a la red (final)
CAUSAS = {
    "soc_bajo": "Batería sin carga (SOC ≤ 21 % al apagarse la casa)",
    "inicio": "Demora o falla en la transición a OFF-GRID (primeros 3 min, SOC suficiente)",
    "medio": "Falla del inversor durante el corte (SOC suficiente)",
    "fin": "Demora en el retorno a la red (últimos 90 s del corte, SOC suficiente)",
    "previo": "Casa ya sin energía antes del corte de red",
    "sin_dato": "Sin lectura de SOC",
}
CAUSAS_TRANSICION = ("inicio", "medio", "fin")   # falla o demora del equipo con SOC suficiente
ETIQ_CAUSA = {"soc_bajo": "batería sin carga", "inicio": "demora o falla en la transición a OFF-GRID", "medio": "falla durante el corte",
              "fin": "demora en el retorno a la red", "previo": "ya sin energía antes del corte", "sin_dato": "sin lectura de SOC"}

# ---------------------------------------------------------------- API
BASE = os.environ.get("METRUM_API_URL", "https://monitoreo-metrum.com").rstrip("/")
_tok = None


def _req(method, path, body=None, auth=True):
    h = {"Content-Type": "application/json"}
    if auth:
        h["X-Authorization"] = "Bearer " + _tok
    data = json.dumps(body).encode() if body is not None else None
    for intento in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers=h, method=method), timeout=90) as r:
                t = r.read()
                return json.loads(t) if t else None
        except Exception:
            if intento == 2:
                raise
            time.sleep(2 * (intento + 1))


def login():
    global _tok
    r = _req("POST", "/api/auth/login", {"username": os.environ["METRUM_USERNAME"], "password": os.environ["METRUM_PASSWORD"]}, auth=False)
    _tok = r["token"]


def get(path):
    return _req("GET", path)


def serie(did, keys, a, b, limit=20000):
    r = get(f"/api/plugins/telemetry/DEVICE/{did}/values/timeseries?keys={keys}&startTs={int(a)}&endTs={int(b)}&agg=NONE&limit={limit}")
    return {k: sorted((p["ts"], p["value"]) for p in v) for k, v in r.items()}


def ultimo(did, keys):
    r = get(f"/api/plugins/telemetry/DEVICE/{did}/values/timeseries?keys={keys}")
    return {k: (v[0]["ts"], v[0]["value"]) for k, v in r.items() if v}


# ---------------------------------------------------------------- flota
def cargar_flota():
    u = get("/api/auth/user")
    cid = u["customerId"]["id"]
    devs, p = [], 0
    while True:
        r = get(f"/api/customer/{cid}/deviceInfos?pageSize=100&page={p}")
        devs += r["data"]
        if not r["hasNext"]:
            break
        p += 1
    gws = [d for d in devs if d["type"] == "pulsar"]
    attrs = lambda did: {a["key"]: a["value"] for a in get(f"/api/plugins/telemetry/DEVICE/{did}/values/attributes")}

    def un_gw(g):
        gid = g["id"]["id"]
        ga = attrs(gid)
        if ga.get("spcus") in EXCLUIR or (ga.get("zone") or "").upper() in EXCLUIR_ZONAS:
            return None
        hijos = {}
        for k in get(f"/api/relations/info?fromId={gid}&fromType=DEVICE"):
            did = k["to"]["id"]
            if did in hijos:
                continue
            a = attrs(did)
            hijos[did] = dict(id=did, name=k["toName"], mettype=a.get("mettype"), brand=a.get("invbrand"), model=(a.get("invmodel") or "").strip())
        return dict(casa=ga.get("spcus") or g["name"], zona=(ga.get("zone") or "SIN ZONA"), ciudad=ga.get("city") or "", op=ga.get("spdno") or "", hijos=list(hijos.values()))

    with ThreadPoolExecutor(6) as ex:
        return [h for h in ex.map(un_gw, gws) if h and h["hijos"]]


# ---------------------------------------------------------------- calculos
def valor_en(s, t, tol=35 * MIN * 1000):
    """Ultimo valor con ts <= t (y no mas viejo que tol)."""
    c = [(ts, float(v)) for ts, v in s if ts <= t]
    return c[-1][1] if c and t - c[-1][0] <= tol else None


def delta_kwh(s, a, b):
    v0 = valor_en(s, a)
    v1 = valor_en(s, b)
    if v0 is None or v1 is None or v1 < v0:
        return None
    return (v1 - v0) / 1000


def intervalos(ev, a, b):
    """Pares po->pr que se cruzan con [a, b]. Devuelve (lista, abierto_desde)."""
    out, ini = [], None
    for t, v in ev:
        if v == "po" and ini is None:
            ini = t
        elif v == "pr" and ini is not None:
            out.append([ini, t]); ini = None
    abierto = ini
    out = [x for x in out if x[1] > a and x[0] < b]
    if abierto is not None and abierto < b:
        out.append([abierto, b])
    return out, abierto


def sumar(iv, lo, hi):
    return sum(max(0, min(y, hi) - max(x, lo)) for x, y in iv) / 1000


def pct90(x):
    x = sorted(x)
    return x[int(0.9 * (len(x) - 1))]


def cierres_diarios(s, dias):
    out = []
    for d in dias:
        t = d.timestamp() * 1000
        c = [float(v) for ts, v in s if t - 86400e3 < ts <= t + 5 * 60e3]
        out.append(c[-1] if c else None)
    return out


def deltas(c):
    return [(c[i + 1] - c[i]) / 1000 if c[i] is not None and c[i + 1] is not None and c[i + 1] >= c[i] else None for i in range(len(c) - 1)]


def procesar(h, a, b, hoy0, dias):
    ahora = time.time() * 1000
    red = [x for x in h["hijos"] if x["mettype"] == "red"]
    sol = [x for x in h["hijos"] if x["mettype"] == "solar"]
    inv = [x for x in h["hijos"] if not x["mettype"]]
    r = dict(casa=h["casa"], zona=h["zona"], ciudad=h["ciudad"], op=h["op"], eventos=[], notas=[])
    # medidores: el que tenga datos mas recientes
    def mejor(lst, key):
        if not lst:
            return None
        u = [(ultimo(x["id"], key).get(key, (0, 0))[0], x) for x in lst]
        return max(u, key=lambda t: t[0])
    mr, ms = mejor(red, "voltageA"), mejor(sol, "voltageA")
    r["red_ultimo"] = mr[0] if mr else None
    r["sol_ultimo"] = ms[0] if ms else None
    red_d = mr[1] if mr and mr[0] else None
    sol_d = ms[1] if ms and ms[0] else None
    # inversor: el de SOC mas reciente
    mi = mejor(inv, "BattSOC")
    inv_d = mi[1] if mi and mi[0] else None
    r["inv_ultimo"] = mi[0] if mi else None
    if inv_d:
        marca = inv_d["brand"] or ("LIVOLTEK" if inv_d["name"].startswith("HP") else "DEYE")
        r["marca"] = marca.title()
    else:
        r["marca"] = ""
    if not red_d:
        r["notas"].append("sin medidor de red con datos")
        return r
    # energia en la ventana
    a0 = a - 40 * MIN * 1000
    sr = serie(red_d["id"], "energyAI,energyAE,event", a0 - 6 * 3600e3, b)
    r["imp"] = delta_kwh(sr.get("energyAI", []), a, b)
    r["exp"] = delta_kwh(sr.get("energyAE", []), a, b)
    ss = serie(sol_d["id"], "energyAI,event", a0 - 6 * 3600e3, b) if sol_d else {}
    r["dem"] = delta_kwh(ss.get("energyAI", []), a, b) if sol_d else None
    r["gen"] = None if None in (r["dem"], r["imp"], r["exp"]) else r["dem"] - r["imp"] + r["exp"]
    # SOC
    soc = []
    if inv_d:
        soc = [(t, float(v)) for t, v in serie(inv_d["id"], "BattSOC", a - 3600e3, b).get("BattSOC", [])]
    en_v = [v for t, v in soc if t >= a]
    r["soc_min"] = min(en_v) if en_v else None
    r["soc_fin"] = soc[-1][1] if soc else None
    # interrupciones
    ri, abierto = intervalos(sr.get("event", []), a, b)
    si, _ = intervalos(ss.get("event", []), a - PRE, b + POST) if sol_d else ([], None)
    grupos = []
    for x in sorted(ri):
        if grupos and x[0] - grupos[-1][-1][1] <= GAP_EVENTO:
            grupos[-1].append(x)
        else:
            grupos.append([x])
    for g in grupos:
        i0, i1 = g[0][0], g[-1][1]
        orS = sumar(g, a, b)
        cl = [x for x in si if x[1] > i0 - PRE and x[0] < i1 + POST]
        clS = sumar(cl, i0 - PRE, i1 + POST) if sol_d else None
        s0 = [v for t, v in soc if i0 - 30 * MIN * 1000 <= t <= i0]
        sd = [v for t, v in soc if i0 <= t <= i1 + 15 * MIN * 1000]
        e = dict(ini=i0, fin=i1, n=len(g), or_s=orS, cl_s=clS, soc=(s0[-1] if s0 else None), soc_dur=(min(sd) if sd else None), en_curso=(abierto is not None and abierto >= i0 and i1 >= b), cl_iv=[x for x in cl if x[1] > i0 - PRE],
                 soc_pts=[[t, v] for t, v in soc if i0 - 30 * MIN * 1000 <= t <= i1 + 30 * MIN * 1000])
        e["bk_s"] = None if clS is None else max(0.0, orS - clS)
        e["excede"] = None if clS is None else clS > orS
        r["eventos"].append(e)
    # interrupciones del medidor solar con red presente
    usados = [x for g in grupos for x in si if x[1] > g[0][0] - PRE and x[0] < g[-1][1] + POST]
    r["solo_cliente"] = [x for x in si if x not in usados and a <= x[0] <= b]
    return r


def soc_en(pts, t, tol=20 * MIN * 1000):
    """Ultimo SOC leido hasta el instante t (no mas viejo que tol)."""
    c = [(ts, v) for ts, v in pts if ts <= t]
    return c[-1][1] if c and t - c[-1][0] <= tol else None


def clasificar_evento(e):
    """Reparte el tiempo sin energia en la casa durante un corte de red (el que resta al respaldo, es decir
    min(T_red, T_solar)) segun el SOC y el momento del apagon. Devuelve segundos por causa (claves de CAUSAS):
      soc_bajo : SOC <= PISO_SOC al apagarse la casa (o en los 15 min alrededor), o apagon a mitad del corte con SOC cerca del piso
                 (<= PISO_SOC + 14) que dura hasta que vuelve la red: bateria sin carga por el consumo del cliente.
      inicio   : apagon en los primeros 3 min del corte con SOC suficiente -> demora o falla en la transicion a OFF-GRID.
      medio    : apagon a mitad del corte con SOC suficiente -> falla del inversor durante la autonomia.
      fin      : apagon en los ultimos 90 s del corte (o despues) con SOC suficiente -> demora en el retorno a la red.
      previo   : la casa ya estaba sin energia antes del corte de red (no atribuible al respaldo).
      sin_dato : no hay lectura de SOC para decidir."""
    out = {k: 0.0 for k in CAUSAS}
    if e.get("cl_s") is None or not e.get("or_s"):
        return out
    ini, orS = e["ini"], e["or_s"]
    lo, hi = ini - PRE, e["fin"] + POST
    pts = e.get("soc_pts") or []
    segs = []
    for x, y in e.get("cl_iv", []):
        d = max(0.0, min(y, hi) - max(x, lo)) / 1000
        if d > 0:
            segs.append((x, y, d))
    tot = sum(d for _, _, d in segs)
    if not tot:
        return out
    k = min(orS, tot) / tot          # el tiempo sin energia se acota a T_red, igual que en el calculo del respaldo
    for x, y, d in segs:
        if x < lo:
            causa = "previo"
        else:
            sx = soc_en(pts, x)
            if sx is None:
                sx = e.get("soc")
            cerca = [v for t, v in pts if x - 15 * MIN * 1000 <= t <= y + 15 * MIN * 1000]
            ref = min([v for v in [sx] + cerca if v is not None], default=None)
            if ref is None:
                causa = "sin_dato"
            elif ref <= PISO_SOC:
                causa = "soc_bajo"
            elif (x - ini) / 1000 < max(orS - T_FIN, orS / 2) and y >= ini + orS * 1000 - T_FIN * 1000 and ref <= PISO_SOC + 14:
                # se apago con la bateria cerca del piso y no volvio hasta que regreso la red: se agoto (el logger puede no reportar el SOC final)
                causa = "soc_bajo"
            else:
                off = (x - ini) / 1000
                if off <= min(T_INICIO, orS / 2):
                    causa = "inicio"
                elif off >= max(orS - T_FIN, orS / 2):
                    causa = "fin"
                else:
                    causa = "medio"
        out[causa] += d * k
    return out


def causa_principal(c):
    """Causa con mas tiempo sin energia en un evento (None si no hubo)."""
    k = max(c, key=c.get)
    return k if c[k] > 0 else None


def sumar_causas(items):
    """Suma por causa los segundos sin respaldo de una lista de eventos."""
    tot = {k: 0.0 for k in CAUSAS}
    for e in items:
        for k, v in clasificar_evento(e).items():
            tot[k] += v
    return tot


ESTADO_PATH = os.path.join(HERE, "..", "data", "estado_casas.json")
UMBRAL_AUSENCIA, UMBRAL_REGRESO, RACHA_MIN = 0.5, 0.75, 2


def cargar_estados():
    try:
        return json.load(open(ESTADO_PATH, encoding="utf-8"))
    except Exception:
        return {"casas": {}}


def evaluar_consumo(dem):
    """Valida el consumo del cliente: demanda diaria (medidor solar) frente a su nivel habitual.
    Habitual = mediana de los dias previos a los 3 ultimos (la mediana no se infla con dias de carga de carro electrico). Racha = dias completos seguidos con
    consumo <= 50 % del habitual. Devuelve None si no hay historia suficiente."""
    ref = [x for x in dem[:-3] if x is not None]
    if len(ref) < 10:
        return None
    base = st.median(ref)
    if base < 2:      # consumo habitual muy bajo: no hay base para comparar
        return dict(base=base, racha=0, ult=[None if x is None else round(x, 1) for x in dem[-7:]], regreso=False, bajo=True)
    racha = 0
    for x in reversed(dem):
        if x is not None and x <= UMBRAL_AUSENCIA * base:
            racha += 1
        else:
            break
    reg = sum(1 for x in dem[-2:] if x is not None and x >= UMBRAL_REGRESO * base) == 2
    return dict(base=base, racha=racha, ult=[None if x is None else round(x, 1) for x in dem[-7:]], regreso=reg, bajo=False)


def actualizar_estados(res, hist, dias):
    """Actualiza el estado de cada casa a partir del consumo. Los estados confirmados por una persona
    (ausente_confirmada) no se borran solos: si el consumo se normaliza se marca 'posible_regreso'."""
    est = cargar_estados()
    casas = est.setdefault("casas", {})
    ult_dia = dias[-1] - dt.timedelta(days=1)       # ultimo dia completo
    hoy = dias[-1].date()
    cambios = []
    for r_, hh in zip(res, hist):
        if not hh:
            continue
        ev = evaluar_consumo(hh["dem"])
        c = casas.get(r_["casa"])
        if ev is None:
            continue
        base, racha = round(ev["base"], 1), ev["racha"]
        if c is None and racha >= RACHA_MIN:
            desde = (ult_dia - dt.timedelta(days=racha - 1)).date().isoformat()
            casas[r_["casa"]] = c = dict(estado="posible_ausencia", desde=desde, nota="Detectada por consumo; validar con el cliente.")
            cambios.append(f"{r_['casa']}: posible ausencia desde {desde}")
        elif c is not None:
            if c["estado"] == "posible_ausencia" and ev["regreso"]:
                c["estado"] = "presente"; c["hasta"] = hoy.isoformat()
                cambios.append(f"{r_['casa']}: consumo normalizado, vuelve a presente")
            elif c["estado"] == "ausente_confirmada" and ev["regreso"]:
                c["estado"] = "posible_regreso"; c["regreso_detectado"] = hoy.isoformat()
                cambios.append(f"{r_['casa']}: ausencia confirmada, pero el consumo se normalizó; validar regreso")
            elif c["estado"] == "posible_regreso" and racha >= RACHA_MIN:
                c["estado"] = "ausente_confirmada"; c.pop("regreso_detectado", None)
            elif c["estado"] == "presente" and racha >= RACHA_MIN:
                c["estado"] = "posible_ausencia"; c["desde"] = (ult_dia - dt.timedelta(days=racha - 1)).date().isoformat(); c.pop("hasta", None)
                cambios.append(f"{r_['casa']}: posible ausencia desde {c['desde']}")
        if c is not None:
            c.update(consumo_habitual_kwh=base, consumo_ultimos_7_dias_kwh=ev["ult"], racha_dias_bajos=racha, validado=hoy.isoformat())
    est["actualizado"] = dt.datetime.now(BOG).isoformat(timespec="minutes")
    return est, cambios


def historial(h, hoy0, dias, kwp):
    """Cierres diarios (14 dias) para desempeno de 7 dias y regla de ausencia del hogar."""
    red = [x for x in h["hijos"] if x["mettype"] == "red"]
    sol = [x for x in h["hijos"] if x["mettype"] == "solar"]
    if not red or not sol:
        return None
    a = dias[0].timestamp() * 1000 - 3600e3
    b = time.time() * 1000
    mejor = lambda lst: max(lst, key=lambda x: ultimo(x["id"], "CenergyAI").get("CenergyAI", (0, 0))[0])
    sr = serie(mejor(red)["id"], "CenergyAI,CenergyAE", a, b)
    ss = serie(mejor(sol)["id"], "CenergyAI", a, b)
    dem = deltas(cierres_diarios(ss.get("CenergyAI", []), dias))
    imp = deltas(cierres_diarios(sr.get("CenergyAI", []), dias))
    exp = deltas(cierres_diarios(sr.get("CenergyAE", []), dias))
    gen = [None if None in (d, i, e) else d - i + e for d, i, e in zip(dem, imp, exp)]
    return dict(dem=dem, gen=gen)


# ---------------------------------------------------------------- HTML
ESTADO = {"ok": "Respaldo OK", "warn": "Parcial", "crit": "Falló"}
ORDEN = {"ok": 0, "warn": 1, "crit": 2}
XTRA_CSS = """
:root{--s1:#2a78d6;--s2:#eb6834;--gd:#0ca30c;--wn:#fab219;--cr:#d03b3b;--grid:#e1e0d9;--axis:#c3c2b7;--ink2:#52514e}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--s1:#3987e5;--s2:#d95926;--grid:#2c2c2a;--axis:#383835;--ink2:#c3c2b7}}
:root[data-theme="dark"]{--s1:#3987e5;--s2:#d95926;--grid:#2c2c2a;--axis:#383835;--ink2:#c3c2b7}
.chart{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.chart svg{display:block;width:100%;min-width:760px;height:auto}
.chart h3{margin:0 0 4px;font:600 1.05rem var(--display)} .chart p.sub2{margin:0 0 10px;color:var(--muted);font-size:.85rem}
.lg{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0 0 8px;font-size:.82rem;color:var(--ink2)} .lg i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-2px}
.lg i.dot{border-radius:50%} .lg i.ring{border-radius:50%;background:none;border:2px solid var(--s1);width:10px;height:10px}
.ax{fill:var(--muted);font:12px var(--body)} .lb{fill:var(--fg);font:13px var(--body)} .lb2{fill:var(--ink2);font:12px var(--body)} .vl{fill:var(--fg);font:600 13px var(--body)}
.gl{stroke:var(--grid);stroke-width:1} .ba{stroke:var(--axis);stroke-width:1}
.m-ok{fill:var(--gd)} .m-warn{fill:var(--wn)} .m-crit{fill:var(--cr)} .c1{fill:var(--s1)} .c2{fill:var(--s2)}
td.tp{cursor:help;text-decoration:underline dotted var(--muted);text-underline-offset:4px}
[data-tip]{cursor:default} [data-tip]:hover,[data-tip]:focus{outline:none;filter:brightness(1.12)}
#tip{position:fixed;z-index:50;pointer-events:none;background:var(--surface);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:8px 11px;font-size:.82rem;line-height:1.4;box-shadow:0 6px 20px rgba(0,0,0,.18);max-width:340px}
#tip .t0{font-weight:600;margin-bottom:2px} #tip[hidden]{display:none}
.two{display:grid;grid-template-columns:3fr 2fr;gap:16px} @media (max-width:900px){.two{grid-template-columns:1fr}}
.top{display:grid;gap:10px;margin:0;padding:0;list-style:none} .top li{display:flex;gap:12px;align-items:baseline;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.top .pill{flex:none} details.mas{margin-top:10px} details.mas summary{cursor:pointer;color:var(--accent);font-size:.9rem}
.hb{display:grid;grid-template-columns:140px 1fr auto;gap:10px;align-items:center;font-size:.9rem;margin:6px 0} .hb .tr{height:14px;background:var(--grid);border-radius:4px;overflow:hidden} .hb .tr b{display:block;height:100%;background:var(--s1);border-radius:4px}
.chips2{display:flex;flex-wrap:wrap;gap:8px} .chips2 span{padding:4px 11px;border-radius:999px;font-size:.85rem;background:var(--surface);border:1px solid var(--line)}
details.det>summary{cursor:pointer;font:600 1.1rem var(--display);padding:6px 0}
"""
TIP_JS = """<div id="tip" role="tooltip" hidden></div>
<script>(function(){var tip=document.getElementById('tip');
function show(el,x,y){tip.textContent='';el.getAttribute('data-tip').split('\\n').forEach(function(l,i){var d=document.createElement('div');if(i===0)d.className='t0';d.textContent=l;tip.appendChild(d);});tip.hidden=false;var r=tip.getBoundingClientRect();tip.style.left=Math.max(8,Math.min(x+14,window.innerWidth-r.width-8))+'px';tip.style.top=Math.max(8,y-r.height-12)+'px';}
document.addEventListener('pointermove',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');if(t){show(t,e.clientX,e.clientY);}else{tip.hidden=true;}});
document.addEventListener('focusin',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');if(t){var b=t.getBoundingClientRect();show(t,b.left+b.width/2,b.top);}});
document.addEventListener('focusout',function(){tip.hidden=true;});})();</script>"""


def fmt_min(s):
    if s is None:
        return "—"
    m = s / 60
    return f"{m:.1f}".replace(".", ",") if m < 100 else f"{m:,.0f}".replace(",", ".")


def n1(x, d=1):
    return "—" if x is None else f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def hora(t):
    d = dt.datetime.fromtimestamp(t / 1000, BOG)
    return d.strftime("%H:%M") if d.date() == dt.datetime.now(BOG).date() else d.strftime("%d/%m %H:%M")


def rango(a, b):
    ini = dt.datetime.fromtimestamp(a / 1000, BOG); fin = dt.datetime.fromtimestamp(b / 1000, BOG)
    f = fin.strftime("%H:%M") if ini.date() == fin.date() else fin.strftime("%d/%m %H:%M")
    return f"{hora(a)} – {f}"


def zn(z):
    return z.title().replace("Condominio ", "").replace(" De ", " de ").replace(" By ", " by ").replace(" La ", " la ")


def tip(*lineas):
    return html.escape("\n".join(l for l in lineas if l), quote=True).replace("\n", "&#10;")


def res_evento(e):
    if e["bk_s"] is None:
        return None
    if e["excede"]:
        return "crit"
    p = e["bk_s"] / e["or_s"] if e["or_s"] else 1
    return "crit" if p < 0.5 else "warn" if p < 0.9 else "ok"


def clase_p(p):
    return "none" if p is None else "ok" if p >= 90 else "warn" if p >= 50 else "crit"


def ticks(a, b, horas):
    paso = 6 if horas <= 24 else 12
    d = dt.datetime.fromtimestamp(a / 1000, BOG).replace(minute=0, second=0, microsecond=0)
    while d.hour % paso or d.timestamp() * 1000 < a:
        d += dt.timedelta(hours=1)
    out = []
    while d.timestamp() * 1000 <= b:
        out.append((d.timestamp() * 1000, d.strftime("%H:%M") if (d.hour or horas <= 24) else d.strftime("%d/%m")))
        d += dt.timedelta(hours=paso)
    return out


def svg_linea(res, a, b, horas):
    zonas = {}
    for r in res:
        for e in r["eventos"]:
            zonas.setdefault(r["zona"], []).append((e, r))
    if not zonas:
        return '<p class="note">Sin interrupciones del OR en el periodo: no hay cortes para graficar.</p>'
    orden = sorted(zonas, key=lambda z: (-len([r for r in res if r["zona"] == z]), z))
    W, L, R, T, RH = 1100, 210, 24, 14, 38
    X = lambda t: L + (t - a) / (b - a) * (W - L - R)
    H = T + RH * len(orden) + 32
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Línea de tiempo de interrupciones del OR por zona">']
    for t, lab in ticks(a, b, horas):
        o.append(f'<line class="gl" x1="{X(t):.1f}" y1="{T}" x2="{X(t):.1f}" y2="{H-26}"/><text class="ax" x="{X(t):.1f}" y="{H-8}" text-anchor="middle">{lab}</text>')
    for i, z in enumerate(orden):
        y = T + i * RH
        n_sis = len([r for r in res if r["zona"] == z])
        o.append(f'<text class="lb" x="{L-12}" y="{y+RH/2+1:.0f}" text-anchor="end">{html.escape(zn(z))}</text><text class="ax" x="{L-12}" y="{y+RH/2+15:.0f}" text-anchor="end">{n_sis} sist.</text>')
        o.append(f'<line class="ba" x1="{L}" y1="{y+RH-3}" x2="{W-R}" y2="{y+RH-3}"/>')
        items = sorted(zonas[z], key=lambda t: t[0]["ini"])
        grp = []
        for e, r in items:
            if grp and e["ini"] - grp[-1][-1][0]["ini"] <= 10 * 60e3:
                grp[-1].append((e, r))
            else:
                grp.append([(e, r)])
        for g in grp:
            x0 = max(L, X(min(e["ini"] for e, r in g))); x1 = min(W - R, X(max(e["fin"] for e, r in g)))
            w = max(6.0, x1 - x0)
            peor = max((res_evento(e) or "ok" for e, r in g), key=lambda c: ORDEN[c])
            cnt = {k: sum(1 for e, r in g if res_evento(e) == k) for k in ESTADO}
            malos = sorted({r["casa"] for e, r in g if res_evento(e) in ("warn", "crit")})
            t = tip(f"{zn(z)} · {hora(min(e['ini'] for e, r in g))} a {hora(max(e['fin'] for e, r in g))}",
                    f"{fmt_min(max(e['or_s'] for e, r in g))} min de interrupción del OR · {len(g)} sistemas",
                    f"{cnt['ok']} respaldo OK · {cnt['warn']} parcial · {cnt['crit']} falló",
                    ("Sin respaldo completo: " + ", ".join(malos[:8]) + ("…" if len(malos) > 8 else "")) if malos else "")
            o.append(f'<rect class="m-{peor}" x="{x0:.1f}" y="{y+6}" width="{w:.1f}" height="20" rx="4"/>'
                     f'<rect x="{x0-6:.1f}" y="{y}" width="{w+12:.1f}" height="{RH-4}" fill="transparent" data-tip="{t}" tabindex="0"/>')
            if len(g) > 1 and w >= 6:
                o.append(f'<text class="lb2" x="{x0+w/2:.1f}" y="{y+5}" text-anchor="middle">{len(g)}</text>')
    o.append("</svg>")
    leg = '<div class="lg"><span><i style="background:var(--gd)"></i>Respaldo OK (≥ 90 %)</span><span><i style="background:var(--wn)"></i>Parcial</span><span><i style="background:var(--cr)"></i>Falló (el cliente sin energía)</span><span>El número sobre la marca = sistemas afectados</span></div>'
    return leg + "".join(o)


def svg_respaldo(res):
    filas = []
    for r in res:
        if not r["eventos"]:
            continue
        orS = sum(e["or_s"] for e in r["eventos"]); clS = sum(e["cl_s"] or 0 for e in r["eventos"]); bkS = sum(e["bk_s"] or 0 for e in r["eventos"])
        filas.append((r, orS, clS, bkS))
    sin = [f for f in filas if f[2] <= 0]
    con = sorted([f for f in filas if f[2] > 0], key=lambda f: -f[2])[:14]
    if not con:
        return f'<p class="note">Ningún sistema quedó sin energía durante interrupciones del OR ({len(filas)} sistemas con cortes).</p>'
    W, L, RV, RH = 1100, 230, 330, 30
    mx = (max(f[3] + f[2] for f in con) / 60) or 1
    X = lambda m: L + m / mx * (W - L - RV)
    H = RH * len(con) + 34
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Minutos respaldados y minutos sin energía por sistema">']
    for k in range(0, 5):
        m = mx * k / 4
        o.append(f'<line class="gl" x1="{X(m):.1f}" y1="0" x2="{X(m):.1f}" y2="{H-26}"/><text class="ax" x="{X(m):.1f}" y="{H-8}" text-anchor="middle">{fmt_min(m*60)} min</text>')
    for i, (r, orS, clS, bkS) in enumerate(con):
        y = i * RH + 6
        nm = ("🧳 " if r.get("ausente") else "") + r["casa"]
        o.append(f'<text class="lb" x="{L-12}" y="{y+13}" text-anchor="end">{html.escape(nm)}</text>')
        wb = X(bkS / 60) - L
        wc = X(clS / 60) - L
        if bkS > 0:
            o.append(f'<rect class="c1" x="{L}" y="{y}" width="{max(wb,0):.1f}" height="18" rx="3"/>')
        o.append(f'<rect class="c2" x="{L + wb + (2 if bkS > 0 else 0):.1f}" y="{y}" width="{max(wc,3):.1f}" height="18" rx="3"/>')
        soc = [e["soc"] for e in r["eventos"] if e["soc"] is not None]
        t = tip(f"{r['casa']} · {zn(r['zona'])} · {r['marca']}", f"{fmt_min(orS)} min de interrupción del OR", f"{fmt_min(bkS)} min respaldados · {fmt_min(clS)} min sin energía",
                f"SOC al inicio de los cortes: {', '.join(f'{x:.0f} %' for x in soc[:4])}" if soc else "")
        o.append(f'<rect x="0" y="{y-3}" width="{W}" height="{RH-2}" fill="transparent" data-tip="{t}" tabindex="0"/>')
        o.append(f'<text x="{W-8}" y="{y+14}" text-anchor="end"><tspan class="vl">{fmt_min(clS)} min sin energía</tspan><tspan class="lb2"> · {n1(100*bkS/orS if orS else None,0)} % respaldado</tspan></text>')
    o.append("</svg>")
    leg = '<div class="lg"><span><i style="background:var(--s1)"></i>Respaldado por la batería (min)</span><span><i style="background:var(--s2)"></i>Sin energía en el cliente (min)</span></div>'
    nota = f'<p class="sub2">{"Se muestran los 14 sistemas con más minutos sin energía. " if len([f for f in filas if f[2] > 0]) > 14 else ""}{len(sin)} de {len(filas)} sistemas con cortes respaldaron el 100 %.</p>'
    return leg + "".join(o) + nota


def svg_rendimiento(res, ausentes):
    zonas = {}
    for r in res:
        if r["des"] is not None:
            zonas.setdefault(r["zona"], []).append(r)
    if not zonas:
        return ""
    orden = sorted(zonas, key=lambda z: (-len(zonas[z]), z))
    W, L, RV, VMAX = 1100, 210, 110, 140
    X = lambda v: L + min(max(v, 0), VMAX) / VMAX * (W - L - RV)
    filas, y = [], 10
    for z in orden:
        pts = sorted(zonas[z], key=lambda r: r["des"])
        lanes = []
        pos = []
        for r in pts:
            x = X(r["des"])
            for li, last in enumerate(lanes):
                if x - last >= 13:
                    lanes[li] = x; pos.append(li); break
            else:
                lanes.append(x); pos.append(len(lanes) - 1)
        h = 34 + 15 * (len(lanes) - 1)
        filas.append((z, pts, pos, y, h))
        y += h
    H = y + 30
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Rendimiento de cada sistema frente al yield de diseño, por zona">']
    for v in range(0, VMAX + 1, 20):
        o.append(f'<line class="gl" x1="{X(v):.1f}" y1="6" x2="{X(v):.1f}" y2="{H-26}"/><text class="ax" x="{X(v):.1f}" y="{H-8}" text-anchor="middle">{v} %</text>')
    o.append(f'<line x1="{X(100):.1f}" y1="6" x2="{X(100):.1f}" y2="{H-26}" stroke="var(--fg)" stroke-width="1.5"/><text class="lb2" x="{X(100)+5:.1f}" y="16">100 % = diseño</text>')
    for z, pts, pos, y0, h in filas:
        cy0 = y0 + 17
        o.append(f'<text class="lb" x="{L-12}" y="{cy0+4}" text-anchor="end">{html.escape(zn(z))}</text>')
        o.append(f'<line class="ba" x1="{L}" y1="{y0+h-2}" x2="{W-RV}" y2="{y0+h-2}"/>')
        media = st.mean(r["des"] for r in pts if r["casa"] not in ausentes) if any(r["casa"] not in ausentes for r in pts) else None
        if media is not None:
            o.append(f'<text class="vl" x="{W-8}" y="{cy0+4}" text-anchor="end">media {n1(media,0)} %</text>')
        for r, li in zip(pts, pos):
            cx, cy = X(r["des"]), cy0 + 15 * li
            aus = r["casa"] in ausentes
            bajo = r["des"] < 60 and not aus
            t = tip(f"{'🧳 ' if aus else ''}{r['casa']} · {zn(z)}", f"Rendimiento {n1(r['des'],0)} % del diseño ({n1(r['gen'],1)} kWh)", ("Posible ausencia del hogar" if aus else ""))
            if aus:
                o.append(f'<circle cx="{cx:.1f}" cy="{cy}" r="5.5" fill="var(--surface)" stroke="var(--s1)" stroke-width="2.5"/>')
            else:
                o.append(f'<circle class="{"c2" if bajo else "c1"}" cx="{cx:.1f}" cy="{cy}" r="5.5" stroke="var(--surface)" stroke-width="2"/>')
            o.append(f'<circle cx="{cx:.1f}" cy="{cy}" r="12" fill="transparent" data-tip="{t}" tabindex="0"/>')
            if bajo and r is pts[0]:
                o.append(f'<text class="lb2" x="{cx-10:.1f}" y="{cy+4}" text-anchor="end">{html.escape(r["casa"])} · {n1(r["des"],0)} %</text>')
    o.append("</svg>")
    leg = '<div class="lg"><span><i class="dot" style="background:var(--s1)"></i>Sistema</span><span><i class="dot" style="background:var(--s2)"></i>Menos de 60 % del diseño</span><span><i class="ring"></i>🧳 Posible ausencia del hogar</span></div>'
    bajos = sorted([r for r in res if r["des"] is not None and r["des"] < 60 and r["casa"] not in ausentes], key=lambda r: r["des"])
    nota = (f'<p class="sub2">Bajo 60 % del diseño ({len(bajos)}): ' + ", ".join(f"{html.escape(r['casa'])} {n1(r['des'],0)} %" for r in bajos[:12]) + ("…" if len(bajos) > 12 else "") + ".</p>") if bajos else ""
    return leg + "".join(o) + nota


def svg_energia(res):
    zonas = {}
    for r in res:
        if r.get("dem") is not None and r.get("gen") is not None and r.get("exp") is not None and r.get("imp") is not None:
            z = zonas.setdefault(r["zona"], dict(sol=0.0, red=0.0))
            z["sol"] += max(r["gen"] - r["exp"], 0); z["red"] += max(r["imp"], 0)
    zonas = {k: v for k, v in zonas.items() if v["sol"] + v["red"] > 0}
    if not zonas:
        return ""
    orden = sorted(zonas, key=lambda z: -(zonas[z]["sol"] + zonas[z]["red"]))
    W, L, RV, RH = 720, 160, 210, 36
    H = RH * len(orden) + 8
    o = [f'<svg style="min-width:600px" viewBox="0 0 {W} {H}" role="img" aria-label="Parte de la demanda cubierta por solar frente a la comprada a la red, por zona">']
    for i, z in enumerate(orden):
        sol, red = zonas[z]["sol"], zonas[z]["red"]; tot = sol + red; y = i * RH + 6
        ps = 100 * sol / tot; ws = ps / 100 * (W - L - RV)
        o.append(f'<text class="lb" x="{L-12}" y="{y+14}" text-anchor="end">{html.escape(zn(z))}</text>')
        o.append(f'<rect class="c1" x="{L}" y="{y}" width="{ws:.1f}" height="20" rx="3"/><rect class="c2" x="{L+ws+2:.1f}" y="{y}" width="{max(W-L-RV-ws-2,1):.1f}" height="20" rx="3"/>')
        o.append(f'<text class="vl" x="{W-RV+12}" y="{y+15}">{n1(ps,0)} % solar</text><text class="lb2" x="{W-8}" y="{y+15}" text-anchor="end">{n1(tot,0)} kWh</text>')
        o.append(f'<rect x="0" y="{y-3}" width="{W}" height="{RH-2}" fill="transparent" data-tip="{tip(zn(z), f"{n1(sol,1)} kWh cubiertos por solar ({n1(ps,0)} %)", f"{n1(red,1)} kWh comprados a la red", f"Demanda total {n1(tot,1)} kWh")}" tabindex="0"/>')
    o.append("</svg>")
    leg = '<div class="lg"><span><i style="background:var(--s1)"></i>Cubierto por solar</span><span><i style="background:var(--s2)"></i>Comprado a la red</span></div>'
    return leg + "".join(o)


def barras_exportacion(res):
    top = sorted([r for r in res if r.get("exp")], key=lambda r: -r["exp"])[:6]
    tot = sum(r["exp"] for r in res if r.get("exp"))
    if not top or tot < 0.05:
        return f'<div class="chart"><h3>Exportación de energía activa</h3><p class="sub2">Prácticamente nula en el periodo: {n1(tot,2)} kWh entre todos los sistemas (cero inyección).</p></div>'
    mx = top[0]["exp"]
    filas = "".join(f'<div class="hb"><span>{html.escape(r["casa"])}</span><div class="tr"><b style="width:{100*r["exp"]/mx:.0f}%"></b></div><span class="num">{n1(r["exp"],2)} kWh</span></div>' for r in top)
    return f'<div class="chart"><h3>Exportación de energía activa</h3><p class="sub2">{n1(tot,2)} kWh en total · mayores exportadores</p>{filas}</div>'


def puntos(res, eventos, efec, OR, ausentes, des_med, exp, gen, dem, b, horas):
    pts = []
    n_casas = len({r["casa"] for r, e in eventos})
    if not eventos:
        pts.append(("ok", f"Sin interrupciones del OR en las últimas {horas} h en ninguno de los sistemas."))
    else:
        zonas_ev = sorted({zn(r["zona"]) for r, e in eventos})
        pts.append(("warn" if (efec or 100) < 90 else "ok", f"{len(eventos)} {'evento' if len(eventos) == 1 else 'eventos'} de red en {n_casas} {'sistema' if n_casas == 1 else 'sistemas'} ({', '.join(zonas_ev)}). Interrupción acumulada {n1(OR/3600,1)} h; respaldo {n1(efec,1) if efec is not None else '—'} %."))
        peor = sorted([(r, e) for r, e in eventos if res_evento(e) == "crit" and e["or_s"] >= 30], key=lambda t: -(t[1]["cl_s"] or 0))
        for r, e in peor[:3]:
            _k = causa_principal(clasificar_evento(e))
            pts.append(("crit", f"{r['casa']} ({zn(r['zona'])}, {r['marca']}): {fmt_min(e['cl_s'])} min sin energía en un corte del OR de {fmt_min(e['or_s'])} min a las {hora(e['ini'])}" + (f"; entró con SOC {e['soc']:.0f} %" if e["soc"] is not None else "") + (f"; causa: {ETIQ_CAUSA[_k]}." if _k else ".")))
        if len(peor) > 3:
            pts.append(("crit", f"Otros {len(peor)-3} cortes largos sin respaldo completo (ver gráfica de respaldo)."))
        bajos = sorted({r["casa"] for r, e in eventos if e["soc"] is not None and e["soc"] <= 21 and e["or_s"] >= 120})
        if bajos:
            pts.append(("warn", f"{len(bajos)} sistemas entraron a un corte con la batería en el piso (SOC ≤ 21 %): {', '.join(bajos[:10])}{'…' if len(bajos) > 10 else ''}."))
        # causa del tiempo sin respaldo segun el SOC al apagarse la casa (regla del 05/10/2026)
        cs = [(r, e, clasificar_evento(e)) for r, e in eventos]
        perdido = sum(sum(c.values()) for r, e, c in cs)
        if perdido >= 1:
            def _casas(ks):
                return sorted({r["casa"] for r, e, c in cs if sum(c[k] for k in ks) >= 1}, key=clave_casa)
            def _txt(ks):
                m = sum(c[k] for r, e, c in cs for k in ks)
                cc = _casas(ks)
                return f"{fmt_min(m)} min ({', '.join(cc[:8])}{'…' if len(cc) > 8 else ''})"
            partes = []
            if _casas(("soc_bajo",)): partes.append("batería sin carga (SOC ≤ 21 % al apagarse la casa, consumo del cliente) " + _txt(("soc_bajo",)))
            if _casas(CAUSAS_TRANSICION): partes.append("falla o demora de transición con SOC suficiente " + _txt(CAUSAS_TRANSICION))
            if _casas(("previo", "sin_dato")): partes.append("no atribuible " + _txt(("previo", "sin_dato")))
            pts.append(("crit" if sum(c[k] for r, e, c in cs for k in CAUSAS_TRANSICION) >= 300 else "warn", f"Tiempo sin respaldo {fmt_min(perdido)} min según el SOC al apagarse la casa: " + "; ".join(partes) + "."))
        enc = sorted({r["casa"] for r, e in eventos if e["en_curso"]})
        if enc:
            pts.append(("crit", "Interrupción del OR en curso: " + ", ".join(enc) + "."))
    micro = sorted({r["casa"] for r, e in eventos if e["or_s"] < 60 and e["excede"]})
    if micro:
        pts.append(("warn", f"{len(micro)} sistemas con microcortes (< 1 min) en los que el cliente quedó sin energía más tiempo que la red: {', '.join(micro[:8])}."))
    corte = b - 2 * 3600e3
    sin_red = [r["casa"] for r in res if (r.get("red_ultimo") or 0) < corte]
    sin_inv = [r["casa"] for r in res if r.get("inv_ultimo") is not None and r["inv_ultimo"] < corte]
    if sin_red:
        pts.append(("crit", f"Sin telemetría del medidor de red hace más de 2 h: {len(sin_red)} {'sistema' if len(sin_red) == 1 else 'sistemas'} ({', '.join(sin_red[:10])}{'…' if len(sin_red) > 10 else ''})."))
    if sin_inv:
        pts.append(("warn", f"Sin telemetría del inversor hace más de 2 h: {len(sin_inv)} {'sistema' if len(sin_inv) == 1 else 'sistemas'} ({', '.join(sin_inv[:10])}{'…' if len(sin_inv) > 10 else ''})."))
    if ausentes:
        pts.append(("none", "🧳 Casas con ausencia confirmada o posible por consumo bajo: " + ", ".join(sorted(ausentes, key=clave_casa)) + ". Validar con el cliente antes de despachar un técnico (detalle en Estado de las casas)."))
    if des_med is not None:
        bj = sorted([r for r in res if r["des"] is not None and r["casa"] not in ausentes], key=lambda r: r["des"])[:3]
        pts.append(("none", f"Rendimiento medio {n1(des_med,1)} % del diseño. Menor: " + ", ".join(f"{r['casa']} ({n1(r['des'],0)} %)" for r in bj) + "."))
    sp = sorted(r["casa"] for r in res if r.get("sin_paneles"))
    if sp:
        pts.append(("none", f"{len(sp)} {'sistema energizado' if len(sp) == 1 else 'sistemas energizados'} solo con baterías en modo respaldo (paneles pendientes de instalar): {', '.join(sp)}. No entran en generación ni rendimiento."))
    llenas = [r["casa"] for r in res if r.get("soc_min") is not None and r["soc_min"] >= 95 and not r.get("sin_paneles")]
    if llenas:
        pts.append(("none", f"{len(llenas)} baterías no bajaron de 95 % en todo el periodo (generación recortada si la casa no consume)."))
    return sorted(pts, key=lambda t: {"crit": 0, "warn": 1, "none": 2, "ok": 3}[t[0]])


def cortes_zona(eventos):
    """Agrupa los eventos de los sistemas en cortes de zona (misma zona, inicio a menos de 10 min)."""
    out = []
    for r, e in sorted(eventos, key=lambda x: (x[0]["zona"], x[1]["ini"])):
        for c in out:
            if c["zona"] == r["zona"] and abs(e["ini"] - c["ini"]) <= 10 * MIN * 1000:
                c["items"].append((r, e)); c["fin"] = max(c["fin"], e["fin"]); c["ini"] = min(c["ini"], e["ini"])
                break
        else:
            out.append(dict(zona=r["zona"], ini=e["ini"], fin=e["fin"], items=[(r, e)]))
    for c in out:
        its = c["items"]
        c["n"] = len({r["casa"] for r, e in its})
        c["dur"] = (c["fin"] - c["ini"]) / 1000
        c["res"] = {k: sum(1 for r, e in its if res_evento(e) == k) for k in ("ok", "warn", "crit")}
        bk = sum(e["bk_s"] for r, e in its if e["bk_s"] is not None); org = sum(e["or_s"] for r, e in its if e["bk_s"] is not None)
        c["pct"] = 100 * bk / org if org else None
        socs = [e["soc"] for r, e in its if e["soc"] is not None]
        c["soc_min"] = min(socs) if socs else None
        c["soc_med"] = st.median(socs) if socs else None
        c["piso"] = sorted({r["casa"] for r, e in its if e["soc"] is not None and e["soc"] <= 21})
        sdur = [(e["soc_dur"], r["casa"]) for r, e in its if e.get("soc_dur") is not None]
        c["soc_dur_min"] = min((v for v, _ in sdur), default=None)
        c["piso_dur"] = sorted({cs for v, cs in sdur if v <= 21})
        c["sin_resp"] = sorted({r["casa"] for r, e in its if res_evento(e) in ("warn", "crit")})
    return sorted(out, key=lambda c: c["ini"])


def hm(t):
    return dt.datetime.fromtimestamp(t / 1000, BOG).strftime("%H:%M")


def clave_casa(c):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", c)]


def lista_sistemas(its):
    """Texto por zona con los nombres de los sistemas (sin el prefijo 'Casa ')."""
    por_z = {}
    for r_, e_ in its:
        por_z.setdefault(r_["zona"], set()).add(r_["casa"])
    return [f"{zn(z)} ({len(cs)}): " + ", ".join(c.replace("Casa ", "") for c in sorted(cs, key=clave_casa)) for z, cs in sorted(por_z.items(), key=lambda x: (-len(x[1]), x[0]))]


def html_por_dia(eventos):
    """Resumen por dia y lista de cortes de zona para ventanas de varios dias."""
    if not eventos:
        return ""
    cortes = cortes_zona(eventos)
    dias = {}
    for r, e in eventos:
        dias.setdefault(dt.datetime.fromtimestamp(e["ini"] / 1000, BOG).date(), []).append((r, e))
    sem = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    filas = []
    for d in sorted(dias):
        its = dias[d]
        cz = [c for c in cortes if dt.datetime.fromtimestamp(c["ini"] / 1000, BOG).date() == d]
        OR = sum(e["or_s"] for r, e in its)
        bk = sum(e["bk_s"] for r, e in its if e["bk_s"] is not None); org = sum(e["or_s"] for r, e in its if e["bk_s"] is not None)
        pct = 100 * bk / org if org else None
        k = {x: sum(1 for r, e in its if res_evento(e) == x) for x in ("ok", "warn", "crit")}
        socs = [(e["soc"], r["casa"]) for r, e in its if e["soc"] is not None]
        piso = sorted({c for v, c in socs if v <= 21})
        cd = sumar_causas([e for r, e in its])
        mx = max(cz, key=lambda c: c["dur"])
        tip_cz = tip(f"{sem[d.weekday()]} {d.strftime('%d/%m')} · {len(cz)} cortes de zona", *[f"{zn(c['zona'])} · {hm(c['ini'])}–{hm(c['fin'])} · {fmt_min(c['dur'])} min · {c['n']} sist." for c in cz])
        tip_si = tip(f"{sem[d.weekday()]} {d.strftime('%d/%m')} · {len({r['casa'] for r, e in its})} sistemas afectados", "Casas por zona:", *lista_sistemas(its))
        filas.append(f'<tr><td class="strong">{sem[d.weekday()]} {d.strftime("%d/%m")}</td><td class="num tp" data-tip="{tip_cz}" tabindex="0">{len(cz)}</td><td class="num tp" data-tip="{tip_si}" tabindex="0">{len({r["casa"] for r, e in its})}</td>'
                     f'<td class="num">{n1(OR/3600,1)} h</td><td class="num">{n1(pct,1)+" %" if pct is not None else "—"}</td>'
                     f'<td class="num">{k["ok"]} · {k["warn"]} · {k["crit"]}</td><td class="num">{fmt_min(cd["soc_bajo"])}</td><td class="num">{fmt_min(sum(cd[x] for x in CAUSAS_TRANSICION))}</td><td class="num">{len(piso)}</td>'
                     f'<td class="num">{n1(min(v for v, c in socs),0)+" %" if socs else "—"}</td>'
                     f'<td>{html.escape(zn(mx["zona"]))}, {hora(mx["ini"])[-5:]}–{hora(mx["fin"])[-5:]} ({fmt_min(mx["dur"])} min, {mx["n"]} sist.)</td></tr>')
    t_dia = ('<div class="tablewrap"><table style="min-width:1100px"><thead><tr><th>Día</th><th>Cortes de zona</th><th>Sistemas afectados</th><th>Interrup. OR acumulada (sistema-horas)</th><th>% respaldado</th>'
             '<th>Eventos OK · Parcial · Falló</th><th>Sin respaldo: batería sin carga (min)</th><th>Sin respaldo: falla o demora de transición (min)</th><th>Entraron con SOC ≤ 21 %</th><th>SOC mín. al inicio</th><th>Corte más largo</th></tr></thead><tbody>' + "".join(filas) + '</tbody></table></div>')
    rel = [c for c in cortes if c["dur"] >= 5 * 60 or c["res"]["warn"] or c["res"]["crit"] or c["piso"] or c["piso_dur"]]
    menores = len(cortes) - len(rel)
    fc = []
    for c in sorted(rel, key=lambda c: c["ini"]):
        cl = "crit" if c["res"]["crit"] else "warn" if c["res"]["warn"] else "ok"
        lin = [f"{r_['casa']}: {ESTADO.get(res_evento(e_), 'sin dato')}, SOC al inicio {n1(e_['soc'], 0) if e_['soc'] is not None else '—'} %" for r_, e_ in sorted(c["items"], key=lambda x: clave_casa(x[0]["casa"]))][:30]
        tip_n = tip(f"{zn(c['zona'])} · {hm(c['ini'])}–{hm(c['fin'])} · {c['n']} sistemas", *lin)
        fc.append(f'<tr><td class="num">{hora(c["ini"])} – {hora(c["fin"])[-5:]}</td><td>{html.escape(zn(c["zona"]))}</td><td class="num">{fmt_min(c["dur"])} min</td><td class="num tp" data-tip="{tip_n}" tabindex="0">{c["n"]}</td>'
                  f'<td class="num">{n1(c["pct"],0)+" %" if c["pct"] is not None else "—"}</td>'
                  f'<td><span class="pill {cl}">{c["res"]["ok"]} OK · {c["res"]["warn"]} parc. · {c["res"]["crit"]} fallo</span></td>'
                  f'<td class="num">{n1(c["soc_min"],0) if c["soc_min"] is not None else "—"} % / {n1(c["soc_med"],0) if c["soc_med"] is not None else "—"} %</td>'
                  f'<td class="num">{n1(c["soc_dur_min"],0)+" %" if c["soc_dur_min"] is not None else "—"}</td>'
                  f'<td class="obs">{html.escape(", ".join(c["piso_dur"][:8]) + ("…" if len(c["piso_dur"]) > 8 else "")) or "—"}</td>'
                  f'<td class="obs">{html.escape(", ".join(c["sin_resp"][:8]) + ("…" if len(c["sin_resp"]) > 8 else "")) or "—"}</td></tr>')
    t_cz = ('<div class="tablewrap"><table style="min-width:1000px"><thead><tr><th>Cuándo</th><th>Zona</th><th>Duración</th><th>Sistemas</th><th>% respaldado</th><th>Resultado</th>'
            '<th>SOC al inicio (mín. / mediana)</th><th>SOC mín. durante el corte</th><th>Baterías en el piso (≤ 21 %) durante el corte</th><th>Sin respaldo completo</th></tr></thead><tbody>' + "".join(fc) + '</tbody></table></div>')
    nota = f'<p class="note">{menores} cortes de zona menores a 5 min, sin falla de respaldo y sin baterías en el piso, no se listan; están en el detalle por sistema.</p>' if menores else ""
    return (f'<section><h2>Interrupciones por día</h2><p>Un corte de zona agrupa los sistemas de la misma zona cuyo corte empezó con menos de 10 min de diferencia. '
            f'Cada evento se cuenta en el día en que empezó. SOC = estado de carga de la batería al inicio del corte. El tiempo sin respaldo se separa según el SOC al apagarse la casa: batería sin carga (SOC ≤ 21 %) o falla o demora de transición (SOC suficiente). Pasa el cursor sobre los números de cortes y sistemas para ver cuáles son.</p>{t_dia}'
            f'<h3 style="margin:14px 0 6px;font:600 1.05rem var(--display)">Cortes de zona relevantes</h3>{t_cz}{nota}</section>')


def html_estado_casas(estados, cambios):
    """Tabla de casas que no estan en estado 'presente', con el consumo que sustenta cada estado."""
    casas = (estados or {}).get("casas", {})
    ETQ = {"ausente_confirmada": ("none", "Ausencia confirmada"), "posible_ausencia": ("warn", "Posible ausencia"), "posible_regreso": ("warn", "Posible regreso")}
    filas = []
    for nombre in sorted(casas, key=clave_casa):
        c = casas[nombre]
        if c["estado"] not in ETQ:
            continue
        cl, et = ETQ[c["estado"]]
        ult = c.get("consumo_ultimos_7_dias_kwh") or []
        cons = " · ".join("—" if x is None else n1(x, 1) for x in ult)
        desde = c.get("desde", "")
        dias_ = ""
        if desde:
            dias_ = f'{(dt.datetime.now(BOG).date() - dt.date.fromisoformat(desde)).days} d'
        validar = {"posible_ausencia": "Confirmar con el cliente antes de despachar un técnico.", "ausente_confirmada": c.get("fuente", "Confirmada."), "posible_regreso": "El consumo volvió a su nivel habitual: confirmar el regreso."}[c["estado"]]
        filas.append(f'<tr><td class="casa">{html.escape(nombre)}</td><td><span class="pill {cl}">{et}</span></td><td class="num">{html.escape(desde[8:10] + "/" + desde[5:7]) if desde else "—"}<span class="sub">{dias_}</span></td>'
                     f'<td class="num">{n1(c.get("consumo_habitual_kwh"),1) if c.get("consumo_habitual_kwh") is not None else "—"}</td><td class="num">{cons}</td><td class="num">{c.get("racha_dias_bajos", "—")}</td>'
                     f'<td class="obs">{html.escape(validar)}</td><td class="num">{html.escape(c.get("validado", "—"))}</td></tr>')
    cab = ""
    if cambios:
        cab = '<p class="note">Cambios de hoy: ' + html.escape("; ".join(cambios)) + ".</p>"
    if not filas:
        return f'<section><h2>Estado de las casas</h2><p>Todas las casas muestran consumo normal frente a su nivel habitual.</p>{cab}</section>'
    return ('<section><h2>Estado de las casas</h2><p>Se valida cada día el consumo del cliente (medidor solar) frente a su nivel habitual de los últimos 30 días. '
            'Con 2 o más días completos en 50 % o menos se marca como posible ausencia; con consumo normal 2 días seguidos se quita. '
            'Las ausencias confirmadas por operaciones no se borran solas.</p>'
            '<div class="tablewrap"><table style="min-width:900px"><thead><tr><th>Casa</th><th>Estado</th><th>Desde</th><th>Consumo habitual (kWh/día)</th><th>Últimos 7 días (kWh/día)</th><th>Días seguidos bajos</th><th>Qué hacer</th><th>Validado</th></tr></thead><tbody>'
            + "".join(filas) + f'</tbody></table></div>{cab}</section>')


def construir(res, a, b, kwp_tab, ausentes, horas, estados=None, cambios=()):
    ini = dt.datetime.fromtimestamp(a / 1000, BOG)
    fin = dt.datetime.fromtimestamp(b / 1000, BOG)
    for r in res:
        r["sin_paneles"] = r["casa"] in SIN_PANELES or (r.get("gen") is not None and r["gen"] < 0)
        if r["sin_paneles"]:      # no hay generacion que evaluar; el respaldo si cuenta
            r["gen"] = None
            r["dem"] = None
    eventos = [(r, e) for r in res for e in r["eventos"]]
    n_casas = len({r["casa"] for r, e in eventos})
    OR = sum(e["or_s"] for r, e in eventos)
    BK = sum(e["bk_s"] for r, e in eventos if e["bk_s"] is not None)
    ORm = sum(e["or_s"] for r, e in eventos if e["bk_s"] is not None)
    efec = (100 * BK / ORm) if ORm else None
    gen = sum(r["gen"] for r in res if r.get("gen") is not None)
    dem = sum(r["dem"] for r in res if r.get("dem") is not None)
    exp = sum(r["exp"] for r in res if r.get("exp") is not None)
    for r in res:
        k = kwp_tab.get(r["casa"])
        r["des"] = None
        r["ausente"] = r["casa"] in ausentes
        if k and r.get("gen") is not None:
            r["des"] = 100 * (r["gen"] / k["kwp"]) / (k["yield_diseno"] / 365 * horas / 24)
    des = [r["des"] for r in res if r["des"] is not None and r["casa"] not in ausentes]
    des_med = st.mean(des) if des else None
    pts = puntos(res, eventos, efec, OR, ausentes, des_med, exp, gen, dem, b, horas)
    if horas > 24 and eventos:
        cz_ = cortes_zona(eventos); mx_ = max(cz_, key=lambda c: c["dur"])
        pts.insert(0, ("ok" if not mx_["res"]["crit"] and not mx_["res"]["warn"] else "warn", f"Corte más largo del periodo: {zn(mx_['zona'])}, {rango(mx_['ini'], mx_['fin'])} ({fmt_min(mx_['dur'])} min, {mx_['n']} sistemas): respaldo {n1(mx_['pct'],0) if mx_['pct'] is not None else '—'} %, SOC mínimo al inicio {n1(mx_['soc_min'],0) if mx_['soc_min'] is not None else '—'} %. Detalle por día más abajo."))
    css = open(os.path.join(HERE, "reporte_diario.css"), encoding="utf-8").read()

    top5 = pts[:5]
    resto = pts[5:]
    li = lambda c, t: f'<li><span class="pill {c}">{ {"ok":"Bien","warn":"Atención","crit":"Crítico","none":"Dato"}[c] }</span><span>{html.escape(t)}</span></li>'
    top_html = '<ul class="top">' + "".join(li(c, t) for c, t in top5) + "</ul>"
    if resto:
        top_html += f'<details class="mas"><summary>Ver {"el otro punto" if len(resto) == 1 else f"los otros {len(resto)} puntos"}</summary><ul class="top" style="margin-top:10px">' + "".join(li(c, t) for c, t in resto) + "</ul></details>"
    kpis = f"""<div class="kpis">
<div class="kpi {'crit' if eventos and (efec or 100) < 50 else 'warn' if eventos and (efec or 100) < 90 else ''}"><b>{len(eventos)}</b><span>Eventos de red en {n_casas} de {len(res)} sistemas</span></div>
<div class="kpi {clase_p(efec) if efec is not None else ''}"><b>{(n1(efec,1)+' %') if efec is not None else '—'}</b><span>Tiempo respaldado ({n1(OR/3600,1)} h de interrupción del OR sumadas)</span></div>
<div class="kpi"><b>{n1(gen,0)} kWh</b><span>Generación de {horas} h · {n1(100*(gen-exp)/dem,0) if dem else '—'} % de la demanda cubierta por solar</span></div>
<div class="kpi"><b>{(n1(des_med,1)+' %') if des_med is not None else '—'}</b><span>Rendimiento medio vs. diseño</span></div>
<div class="kpi"><b>{n1(exp,1)} kWh</b><span>Exportación de energía activa</span></div>
</div>"""
    # estado de datos
    corte = b - 2 * 3600e3
    sin_red = [r["casa"] for r in res if (r.get("red_ultimo") or 0) < corte]
    sin_inv = [r["casa"] for r in res if r.get("inv_ultimo") is not None and r["inv_ultimo"] < corte]
    estado = '<div class="chips2">' + (f'<span><b>{len(res)-len(sin_red)}</b> de {len(res)} medidores de red al día</span><span><b>{len(res)-len(sin_inv)}</b> inversores al día (últimas 2 h)</span>') + ("".join(f"<span>Sin datos de red: {html.escape(c)}</span>" for c in sin_red[:10])) + (f'<span>Solo baterías, sin paneles aún: {html.escape(", ".join(sorted(r["casa"] for r in res if r.get("sin_paneles"))))}</span>' if any(r.get("sin_paneles") for r in res) else "") + "</div>"
    # detalle por zona (tablas plegadas)
    zonas = {}
    for r in res:
        zonas.setdefault(r["zona"], []).append(r)
    sec = []
    for z in sorted(zonas, key=lambda z: (-len(zonas[z]), z)):
        rs = sorted(zonas[z], key=lambda r: (-(sum(e["or_s"] for e in r["eventos"])), r["casa"]))
        filas = []
        for r in rs:
            evs = r["eventos"]
            orS = sum(e["or_s"] for e in evs); clS = sum(e["cl_s"] or 0 for e in evs); bkS = sum(e["bk_s"] or 0 for e in evs)
            p = (100 * bkS / orS) if orS else None
            cl, estado_t = "none", "Sin cortes"
            if evs:
                peor = max((res_evento(e) or "ok" for e in evs), key=lambda c: ORDEN[c]) if any(res_evento(e) for e in evs) else "ok"
                cl, estado_t = peor, ESTADO[peor]
            horas_html = "—"
            if evs:
                partes = []
                for e in evs:
                    cli = " · ".join(f"{dt.datetime.fromtimestamp(x / 1000, BOG).strftime('%H:%M')}–{dt.datetime.fromtimestamp(y / 1000, BOG).strftime('%H:%M')}" for x, y in e.get("cl_iv", []) if y - x >= 1000)
                    _k = causa_principal(clasificar_evento(e))
                    _s = f" · SOC {n1(e['soc'], 0)} %" if e.get("soc") is not None else ""
                    partes.append(f"{rango(e['ini'], e['fin'])}" + (f'<span class="sub">cliente sin energía: {cli}{(" · causa: " + ETIQ_CAUSA[_k] + _s) if _k else ""}</span>' if cli else '<span class="sub">cliente sin interrupción</span>'))
                horas_html = "".join(f"<div>{x}</div>" for x in partes)
            filas.append(f"""<tr><td class="casa">{'🧳 ' if r['ausente'] else ''}{html.escape(r['casa'])}<span class="sub">{html.escape(r['marca'])}{' · sin paneles (obra)' if r.get('sin_paneles') else ''}</span></td>
<td class="num">{horas_html}</td><td class="num">{fmt_min(orS) if evs else '—'}</td><td class="num">{fmt_min(clS) if evs else '—'}</td><td class="num">{n1(p,0)+' %' if p is not None else '—'}</td>
<td><span class="pill {cl}">{estado_t}</span></td><td class="num">{n1(r.get('soc_min'),0) if r.get('soc_min') is not None else '—'}</td>
<td class="num">{'sin paneles' if r.get('sin_paneles') else n1(r.get('gen'),1)}</td><td class="num">{(n1(r['des'],0)+' %') if r['des'] is not None else '—'}</td><td class="num">{n1(r.get('exp'),2)}</td></tr>""")
        sec.append(f'<h3 style="margin:18px 0 6px">{html.escape(zn(z))} · {len(rs)} sistemas</h3><div class="tablewrap"><table><thead><tr><th>Sistema</th><th>Hora del corte</th><th>Interrup. OR (min)</th><th>Percibida (min)</th><th>% respaldado</th><th>Resultado</th><th>SOC mín. %</th><th>Gen. kWh</th><th>Rend. %</th><th>Export. kWh</th></tr></thead><tbody>{"".join(filas)}</tbody></table></div>')
    titulo = f"Reporte diario O&amp;M · {fin.strftime('%d/%m/%Y')}"
    por_dia_html = html_por_dia(eventos) if horas > 24 else ""
    estado_casas_html = html_estado_casas(estados, cambios)
    c_lin = svg_linea(res, a, b, horas)
    c_resp = svg_respaldo(res)
    c_rend = svg_rendimiento(res, ausentes)
    c_en = svg_energia(res)
    page = f"""<title>Reporte diario Sunny</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{css}{XTRA_CSS}</style>
<div class="wrap">
<header>
<div class="eyebrow">O&amp;M · Proyecto Sunny · {len(res)} sistemas</div>
<h1>{titulo}</h1>
<p>Últimas {horas} h: {ini.strftime('%d/%m %H:%M')} a {fin.strftime('%d/%m %H:%M')} (hora Bogotá). Respaldo = interrupción del OR (medidor de red) menos la que percibe el cliente (medidor solar). Sin Piloto Promigas, Piloto Huawei ni Castellana Real (en estabilización).</p>
</header>
{kpis}
<section><h2>Lo más importante</h2>{top_html}</section>
{estado_casas_html}
{por_dia_html}
<section><h2>Interrupciones de la red</h2>
<div class="chart"><h3>Cuándo se cayó la red, por zona</h3><p class="sub2">Cada marca es un corte del OR. El color es el peor resultado entre los sistemas afectados (el detalle está al pasar el cursor).</p>{c_lin}</div>
<div class="chart"><h3>Respaldo por sistema</h3>{c_resp}</div>
</section>
<section><h2>Rendimiento y energía</h2>
<div class="chart"><h3>Rendimiento de cada sistema frente al diseño</h3><p class="sub2">Cada punto es un sistema. 100 % = lo que debería generar en el periodo según su yield de diseño.</p>{c_rend}</div>
<div class="two"><div class="chart"><h3>De dónde sale la energía que consumen las casas</h3>{c_en}</div>{barras_exportacion(res)}</div>
</section>
<section><h2>Estado de los datos</h2>{estado}</section>
<section><details class="det"><summary>Detalle por sistema y zona</summary>{"".join(sec)}</details></section>
<section class="note"><h2 style="font-size:1rem">Notas</h2><ul>
<li>Generación = demanda − importación + exportación (acumulados de 15 min de los medidores). Rendimiento = generación / kWp frente al yield de diseño del conjunto; solo para los sistemas con kWp en <code>om-agency/data/kwp.json</code>.</li>
<li>Los cortes del OR separados por menos de 15 min forman un evento; las interrupciones del medidor solar entre 2 min antes y 15 min después se asignan a ese evento.</li>
<li>Sistemas sin paneles (energizados solo con baterías en modo respaldo mientras se termina la cubierta) quedan fuera de generación, rendimiento y cobertura; su respaldo sí se cuenta.</li>
<li>🧳 Ausencia del hogar: se valida el consumo del cliente (medidor solar). Con 2 o más días completos en 50 % o menos de su nivel habitual (mediana de 30 días) pasa a posible ausencia; con 2 días seguidos en 75 % o más vuelve a presente. El estado de cada casa se guarda en <code>om-agency/data/estado_casas.json</code>; las ausencias confirmadas por operaciones no se borran solas.</li>
</ul></section>
</div>
{TIP_JS}"""
    resumen = "\n".join(f"- [{c}] {t}" for c, t in pts)
    return page, resumen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reporte_diario.html")
    ap.add_argument("--horas", type=int, default=0, help="0 = automatico: 72 h los lunes, 24 h los demas dias")
    args = ap.parse_args()
    login()
    ahora = dt.datetime.now(BOG)
    if args.horas <= 0:
        args.horas = 72 if ahora.weekday() == 0 else 24
    b = int(ahora.timestamp() // 900 * 900 * 1000)
    a = b - args.horas * 3600 * 1000
    hoy0 = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    dias = [hoy0 - dt.timedelta(days=i) for i in range(30, -1, -1)]   # 31 cierres -> 30 dias completos
    kwp_tab = json.load(open(os.path.join(HERE, "..", "data", "kwp.json"), encoding="utf-8"))
    flota = cargar_flota()
    print(f"Flota: {len(flota)} sistemas", file=sys.stderr)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda h: procesar(h, a, b, hoy0, dias), flota))
        hist = list(ex.map(lambda h: historial(h, hoy0, dias, kwp_tab), flota))
    # desempeno 7 dias y regla de ausencia (usa el portafolio del dia para normalizar el clima)
    ND = len(dias) - 1
    pg = [sum((hh["gen"][i] or 0) for hh in hist if hh) for i in range(ND)]
    pmed = st.median([x for x in pg if x]) if any(pg) else None
    for r, hh in zip(res, hist):
        if not hh:
            continue
        k = kwp_tab.get(r["casa"])
        g7 = [x for x in hh["gen"][-7:] if x is not None]
        if k and len(g7) >= 5:
            r["des7"] = 100 * (sum(g7) / len(g7) * 365 / k["kwp"]) / k["yield_diseno"]
    estados, cambios = actualizar_estados(res, hist, dias)
    ausentes = {c for c, v in estados["casas"].items() if v["estado"] in ("posible_ausencia", "ausente_confirmada", "posible_regreso")}
    json.dump(estados, open(ESTADO_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    for c in cambios:
        print("ESTADO:", c, file=sys.stderr)
    page, resumen = construir(res, a, b, kwp_tab, ausentes, args.horas, estados, cambios)
    open(args.out, "w", encoding="utf-8").write(page)
    print(f"HTML: {args.out}")
    print("RESUMEN")
    print(resumen)


if __name__ == "__main__":
    main()
