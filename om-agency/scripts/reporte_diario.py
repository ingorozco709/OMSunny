#!/usr/bin/env python3
"""Reporte diario O&M de Proyecto Sunny (ultimas 24 h) desde la telemetria de Metrum.

Uso:  python3 om-agency/scripts/reporte_diario.py --out /tmp/reporte.html [--horas 24]

Credenciales: variables de entorno METRUM_API_URL, METRUM_USERNAME, METRUM_PASSWORD.
Escribe el HTML (pagina completa para publicar como artefacto) y un resumen de texto por stdout.

Metodo (mismo del reporte mensual):
  * Interrupcion del OR     = pares po -> pr del medidor de red.
  * Interrupcion percibida  = pares po -> pr del medidor solar.
  * Respaldo                = interrupcion OR - interrupcion percibida (minimo 0).
  * Generacion              = demanda (medidor solar) - importacion + exportacion (medidor de red),
                              con los acumulados energyAI/energyAE de 15 min.
  * Exportacion activa      = energyAE del medidor de red.
Se excluyen "Piloto Promigas" y "Piloto Huawei".
"""
import argparse, datetime as dt, html, json, os, statistics as st, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
BOG = dt.timezone(dt.timedelta(hours=-5))
EXCLUIR = {"Piloto HUAWEI", "Piloto Promigas"}
GAP_EVENTO = 15 * 60e3     # cortes del OR mas cercanos que esto forman un solo evento
PRE, POST = 2 * 60e3, 15 * 60e3
MIN = 60.0

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
        if ga.get("spcus") in EXCLUIR:
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
        e = dict(ini=i0, fin=i1, n=len(g), or_s=orS, cl_s=clS, soc=(s0[-1] if s0 else None), en_curso=(abierto is not None and abierto >= i0 and i1 >= b))
        e["bk_s"] = None if clS is None else max(0.0, orS - clS)
        e["excede"] = None if clS is None else clS > orS
        r["eventos"].append(e)
    # interrupciones del medidor solar con red presente
    usados = [x for g in grupos for x in si if x[1] > g[0][0] - PRE and x[0] < g[-1][1] + POST]
    r["solo_cliente"] = [x for x in si if x not in usados and a <= x[0] <= b]
    return r


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


def clase_p(p):
    return "none" if p is None else "ok" if p >= 90 else "warn" if p >= 50 else "crit"


def construir(res, a, b, kwp_tab, ausentes):
    ini = dt.datetime.fromtimestamp(a / 1000, BOG)
    fin = dt.datetime.fromtimestamp(b / 1000, BOG)
    eventos = [(r, e) for r in res for e in r["eventos"]]
    n_casas_ev = len({r["casa"] for r, e in eventos})
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
        if k and r.get("gen") is not None:
            r["des"] = 100 * (r["gen"] / k["kwp"]) / (k["yield_diseno"] / 365)
        r["des7"] = r.get("des7")
    des = [r["des"] for r in res if r["des"] is not None and r["casa"] not in ausentes]
    des_med = st.mean(des) if des else None

    # ---------------- puntos relevantes
    pts = []
    if not eventos:
        pts.append(("ok", "Sin interrupciones del OR en las últimas 24 h en ninguno de los sistemas."))
    else:
        zonas_ev = sorted({r["zona"].title() for r, e in eventos})
        pts.append(("warn" if (efec or 100) < 90 else "ok",
                    f"{len(eventos)} eventos de red en {n_casas_ev} sistemas ({', '.join(zonas_ev)}). Interrupción acumulada {n1(OR/3600,1)} h; respaldo {n1(efec,1) if efec is not None else '—'} %."))
        peor = sorted([(r, e) for r, e in eventos if e["bk_s"] is not None and e["or_s"] >= 30 and e["bk_s"] / e["or_s"] < 0.5 or (e["excede"])], key=lambda t: -(t[1]["cl_s"] or 0))
        for r, e in peor[:6]:
            pts.append(("crit", f"{r['casa']} ({r['zona'].title()}, {r['marca']}): el cliente estuvo {fmt_min(e['cl_s'])} min sin energía en un corte del OR de {fmt_min(e['or_s'])} min a las {hora(e['ini'])}"
                        + (f"; entró con SOC {e['soc']:.0f} %." if e["soc"] is not None else ".")))
        bajos = [(r, e) for r, e in eventos if e["soc"] is not None and e["soc"] <= 21 and e["or_s"] >= 120]
        if bajos:
            pts.append(("warn", "Entraron al corte con la batería en el piso (SOC ≤ 21 %): " + ", ".join(sorted({r['casa'] for r, e in bajos})) + "."))
        enc = [r["casa"] for r, e in eventos if e["en_curso"]]
        if enc:
            pts.append(("crit", "Interrupción del OR en curso a la hora del corte del reporte: " + ", ".join(sorted(set(enc))) + "."))
    # microcortes: el cliente peor que la red
    micro = [r["casa"] for r, e in eventos if e["or_s"] < 60 and e["excede"]]
    if micro:
        pts.append(("warn", f"{len(micro)} microcortes (< 1 min) donde el cliente quedó sin energía más tiempo que la red: " + ", ".join(sorted(set(micro))) + "."))
    if ausentes:
        pts.append(("none", "🧳 Posible ausencia del hogar (consumo y generación caídos): " + ", ".join(sorted(ausentes)) + ". Revisar antes de despachar técnico."))
    if des_med is not None:
        bajos = sorted([r for r in res if r["des"] is not None and r["casa"] not in ausentes], key=lambda r: r["des"])[:3]
        pts.append(("none", f"Rendimiento del día: {n1(des_med,1)} % del yield de diseño en promedio. Menor: " + ", ".join(f"{r['casa']} ({n1(r['des'],0)} %)" for r in bajos) + "."))
    if exp > 0:
        top = sorted([r for r in res if r.get("exp")], key=lambda r: -r["exp"])[:3]
        pts.append(("none", f"Exportación de energía activa: {n1(exp,1)} kWh. Mayor: " + ", ".join(f"{r['casa']} ({n1(r['exp'],1)} kWh)" for r in top) + "."))
    corte = b - 2 * 3600e3
    sin_red = [r["casa"] for r in res if (r.get("red_ultimo") or 0) < corte]
    sin_inv = [r["casa"] for r in res if r.get("inv_ultimo") is not None and r["inv_ultimo"] < corte]
    if sin_red:
        pts.append(("crit", f"Sin telemetría del medidor de red hace más de 2 h: {len(sin_red)} sistemas ({', '.join(sin_red[:12])}{'…' if len(sin_red) > 12 else ''})."))
    if sin_inv:
        pts.append(("warn", f"Sin telemetría del inversor hace más de 2 h: {len(sin_inv)} sistemas ({', '.join(sin_inv[:12])}{'…' if len(sin_inv) > 12 else ''})."))
    llenas = [r["casa"] for r in res if r.get("soc_min") is not None and r["soc_min"] >= 95]
    if llenas:
        pts.append(("none", f"Batería sin bajar de 95 % en todo el periodo (sin respaldo disponible para ciclar): {len(llenas)} sistemas."))

    # ---------------- HTML
    css = open(os.path.join(HERE, "reporte_diario.css"), encoding="utf-8").read()
    zonas = {}
    for r in res:
        zonas.setdefault(r["zona"], []).append(r)
    ptxt = "".join(f'<li class="pt {c}"><span class="pill {c}">{ {"ok":"Bien","warn":"Atención","crit":"Crítico","none":"Dato"}[c] }</span><span>{html.escape(t)}</span></li>' for c, t in pts)
    kpis = f"""<div class="kpis">
<div class="kpi"><b>{len(eventos)}</b><span>Eventos de red en {n_casas_ev} de {len(res)} sistemas</span></div>
<div class="kpi {clase_p(efec) if efec is not None else ''}"><b>{n1(efec,1)+' %' if efec is not None else '—'}</b><span>Tiempo respaldado ({n1(OR/3600,1)} h de interrupción del OR sumadas)</span></div>
<div class="kpi"><b>{n1(gen,0)} kWh</b><span>Generación 24 h · cobertura {n1(100*gen/dem,0) if dem else '—'} % de la demanda</span></div>
<div class="kpi"><b>{n1(des_med,1)+' %' if des_med is not None else '—'}</b><span>Rendimiento medio vs. yield de diseño</span></div>
<div class="kpi"><b>{n1(exp,1)} kWh</b><span>Exportación de energía activa</span></div>
</div>"""
    sec = []
    for z in sorted(zonas, key=lambda z: (-len(zonas[z]), z)):
        rs = sorted(zonas[z], key=lambda r: (-(sum(e["or_s"] for e in r["eventos"])), r["casa"]))
        zo = sum(e["or_s"] for r in rs for e in r["eventos"] if e["bk_s"] is not None)
        zb = sum(e["bk_s"] for r in rs for e in r["eventos"] if e["bk_s"] is not None)
        zp = (100 * zb / zo) if zo else None
        filas = []
        for r in rs:
            evs = r["eventos"]
            orS = sum(e["or_s"] for e in evs); clS = sum(e["cl_s"] or 0 for e in evs); bkS = sum(e["bk_s"] or 0 for e in evs)
            p = (100 * bkS / orS) if orS else None
            estado = "Sin cortes"
            cl = "none"
            if evs:
                if any(e["excede"] for e in evs) or (p is not None and p < 50):
                    estado, cl = "Falló", "crit"
                elif p is not None and p < 90:
                    estado, cl = "Parcial", "warn"
                else:
                    estado, cl = "Respaldo OK", "ok"
            det = " · ".join(f"{hora(e['ini'])} ({fmt_min(e['or_s'])} min)" for e in evs)
            marca = ("🧳 " if r["casa"] in ausentes else "") + html.escape(r["casa"])
            filas.append(f"""<tr><td class="casa">{marca}<span class="sub">{html.escape(r['marca'])}</span></td>
<td class="num">{fmt_min(orS) if evs else '—'}<span class="sub">{det}</span></td><td class="num">{fmt_min(clS) if evs else '—'}</td><td class="num strong">{fmt_min(bkS) if evs else '—'}</td>
<td class="socc">{('<div class="bar"><i class="'+cl+'" style="width:'+str(min(100,p or 0))+'%"></i></div><span class="num">'+n1(p,0)+' %</span>') if p is not None else '<span class="muted">—</span>'}</td>
<td><span class="pill {cl}">{estado}</span></td><td class="num">{n1(r.get('soc_min'),0) if r.get('soc_min') is not None else '—'}</td>
<td class="num">{n1(r.get('gen'),1)}</td><td class="num">{(n1(r['des'],0)+' %') if r['des'] is not None else '—'}</td><td class="num">{n1(r.get('exp'),2)}</td></tr>""")
        sec.append(f"""<section class="zone"><div class="zhead"><div><div class="eyebrow">{html.escape(rs[0]['ciudad'].title())} · {html.escape(rs[0]['op'])}</div><h2>{html.escape(z.title())}</h2></div>
<div class="zk"><span><b>{len(rs)}</b> sistemas</span><span><b>{sum(len(r['eventos']) for r in rs)}</b> eventos</span><span><b class="{clase_p(zp)}t">{(n1(zp,1)+' %') if zp is not None else '—'}</b> respaldado</span></div></div>
<div class="tablewrap"><table><thead><tr><th>Sistema</th><th>Interrupción OR (min)</th><th>Percibida (min)</th><th>Respaldado (min)</th><th>% respaldado</th><th>Resultado</th><th>SOC mín. %</th><th>Gen. kWh</th><th>Rend. %</th><th>Export. kWh</th></tr></thead><tbody>{''.join(filas)}</tbody></table></div></section>""")
    titulo = f"Reporte diario O&amp;M · {fin.strftime('%d/%m/%Y')}"
    page = f"""<title>Reporte diario Sunny</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{css}
.pts{{list-style:none;margin:0;padding:0;display:grid;gap:10px}} .pt{{display:flex;gap:12px;align-items:baseline;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 14px}} .pt .pill{{flex:none}}
</style>
<div class="wrap">
<header>
<div class="eyebrow">O&amp;M · Proyecto Sunny · {len(res)} sistemas</div>
<h1>{titulo}</h1>
<p>Ventana: {ini.strftime('%d/%m %H:%M')} a {fin.strftime('%H:%M')} (hora Bogotá), últimas {int(round((b-a)/3600e3))} h. Respaldo = interrupción del OR (medidor de red) menos interrupción percibida por el cliente (medidor solar). Se excluyen Piloto Promigas y Piloto Huawei.</p>
</header>
{kpis}
<section><h2>Puntos relevantes</h2><ul class="pts">{ptxt}</ul></section>
{''.join(sec)}
<section class="note"><h2 style="font-size:1rem">Notas</h2><ul>
<li>Generación = demanda − importación + exportación, con acumulados de 15 min de los medidores; rendimiento = generación / kWp frente al yield de diseño del conjunto (solo los sistemas con kWp en <code>om-agency/data/kwp.json</code>).</li>
<li>Los cortes del OR separados por menos de 15 min se agrupan en un evento; las interrupciones del medidor solar entre 2 min antes y 15 min después se asignan a ese evento.</li>
<li>🧳 Ausencia del hogar: en los 2 últimos días completos la demanda cayó a la mitad o menos de su nivel habitual (percentil 90 de 14 días) y la generación cayó con ella.</li>
</ul></section>
</div>"""
    resumen = "\n".join(f"- [{c}] {t}" for c, t in pts)
    return page, resumen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reporte_diario.html")
    ap.add_argument("--horas", type=int, default=24)
    args = ap.parse_args()
    login()
    ahora = dt.datetime.now(BOG)
    b = int(ahora.timestamp() // 900 * 900 * 1000)
    a = b - args.horas * 3600 * 1000
    hoy0 = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    dias = [hoy0 - dt.timedelta(days=i) for i in range(14, -1, -1)]   # 15 cierres -> 14 dias completos
    kwp_tab = json.load(open(os.path.join(HERE, "..", "data", "kwp.json"), encoding="utf-8"))
    flota = cargar_flota()
    print(f"Flota: {len(flota)} sistemas", file=sys.stderr)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda h: procesar(h, a, b, hoy0, dias), flota))
        hist = list(ex.map(lambda h: historial(h, hoy0, dias, kwp_tab), flota))
    # desempeno 7 dias y regla de ausencia (usa el portafolio del dia para normalizar el clima)
    pg = [sum((hh["gen"][i] or 0) for hh in hist if hh) for i in range(14)]
    pmed = st.median([x for x in pg if x]) if any(pg) else None
    ausentes = set()
    for r, hh in zip(res, hist):
        if not hh:
            continue
        k = kwp_tab.get(r["casa"])
        g7 = [x for x in hh["gen"][-7:] if x is not None]
        if k and len(g7) >= 5:
            r["des7"] = 100 * (sum(g7) / len(g7) * 365 / k["kwp"]) / k["yield_diseno"]
        dm = [x for x in hh["dem"] if x]
        gm = [x for x in hh["gen"] if x]
        if len(dm) >= 8 and len(gm) >= 8 and pmed:
            md, mg = pct90(dm), pct90(gm)
            malos = 0
            for i in (-1, -2):
                d, g = hh["dem"][i], hh["gen"][i]
                if d is not None and g is not None and pg[i] and d <= 0.5 * md and (g / mg) / (pg[i] / pmed) <= 0.7:
                    malos += 1
            if malos == 2:
                ausentes.add(r["casa"])
    page, resumen = construir(res, a, b, kwp_tab, ausentes)
    open(args.out, "w", encoding="utf-8").write(page)
    print(f"HTML: {args.out}")
    print("RESUMEN")
    print(resumen)


if __name__ == "__main__":
    main()
