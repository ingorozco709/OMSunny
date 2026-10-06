#!/usr/bin/env python3
"""Reporte diario de operación del portafolio Sunny Metrum (lunes a viernes, 7:00 a. m. hora de Bogotá).

Uso:
  python3 reporte_diario.py                      # ventana automática que termina ahora
  python3 reporte_diario.py --fin 2026-10-05T07:00 [--inicio 2026-10-02T07:00]
  python3 reporte_diario.py --salida reporte.html --json resumen.json

Ventana: martes a viernes, las últimas 24 h. Lunes, desde el viernes a las 7:00 (fin de semana completo).
Variables de entorno: METRUM_API_URL, METRUM_USERNAME, METRUM_PASSWORD.
Solo lee datos de Metrum; no escribe nada en la plataforma.
"""
import os, sys, json, math, time, argparse, html, re, statistics as st
import datetime as dt, concurrent.futures as cf, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
BOG = dt.timedelta(hours=5)           # Bogotá = UTC-5, sin horario de verano
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
RESERVA = 22.0                        # SOC a partir del cual se considera la batería en reserva (piso típico 20 %)
GAP_RADIO = 75000                     # ms: un hueco de tensión se asocia al evento de red más cercano dentro de este radio
PV_MIN_KWH = 5.0                      # una casa cuyo inversor nunca pasa de este valor diario (energyPD) no tiene FV instalada: solo baterías de respaldo
PV_MIN_DIAS = 5                       # días con dato necesarios para decidir que una casa no tiene FV
EXCLUIDOS = []                        # (ciudad, casa, motivo) de lo que se dejó fuera del reporte; lo llena main()
YIELD_PATRON = {"CALI": 1188, "COSTA": 1323}      # kWh/kWp·año: yield patrón de comparación por región, definido por el usuario
CIUDADES_COSTA = {"TURBACO", "BARRANQUILLA", "CARTAGENA"}
BATERIA_LLENA_SOC = 99                # % de SOC con el que se considera la batería llena
LLENO_TARDE_H = 16                    # hora local: batería llena entre LLENO_ANTES_H y esta hora = "producción limitada en la tarde"; después ya casi no hay sol que limitar
LLENO_ANTES_H = 12                   # hora local: batería llena antes de esta hora = "producción limitada" (con la batería llena la producción se limita al consumo)
CONSUMO_BAJO = 0.75                  # consumo del día por debajo de esta fracción del habitual de la casa (mediana de sus días previos) = "bajo consumo"

def patron_yield(ciudad):
    """Yield patrón (kWh/kWp·año) de la región de la ciudad: Cali o costa; None si la ciudad no está en ninguna."""
    c = (ciudad or "").strip().upper()
    return YIELD_PATRON["CALI"] if c == "CALI" else (YIELD_PATRON["COSTA"] if c in CIUDADES_COSTA else None)

# ------------------------------------------------------------------ Metrum
BASE = os.environ.get("METRUM_API_URL", "").rstrip("/")
_tok = {"t": None, "ts": 0}

def req(method, path, body=None, token=True, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + get_token()
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    for intento in range(3):
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, raw[:200].decode("utf8", "ignore")
        except Exception:
            if intento == 2:
                return 0, None
            time.sleep(2 * (intento + 1))

def get_token():
    if _tok["t"] and time.time() - _tok["ts"] < 6000:
        return _tok["t"]
    c, d = req("POST", "/api/auth/login", {"username": os.environ["METRUM_USERNAME"], "password": os.environ["METRUM_PASSWORD"]}, token=False)
    assert c == 200, f"login Metrum falló ({c})"
    _tok["t"], _tok["ts"] = d["token"], time.time()
    return _tok["t"]

def listar_dispositivos():
    out, page = [], 0
    while True:
        c, d = req("GET", f"/api/user/devices?pageSize=100&page={page}")
        assert c == 200, f"no se pudo listar dispositivos ({c})"
        out += d["data"]
        if not d.get("hasNext"):
            return out
        page += 1

ATTR_KEYS = "city,zone,gateway,mettype,spcus,invbrand,invmodel,invcap,invtype"

def atributos(dv):
    c, a = req("GET", f"/api/plugins/telemetry/DEVICE/{dv['id']['id']}/values/attributes?keys={ATTR_KEYS}")
    r = {z["key"]: z["value"] for z in a} if c == 200 and isinstance(a, list) else {}
    return dv, r

def serie(dev_id, keys, t0, t1, limit=5000):
    c, d = req("GET", f"/api/plugins/telemetry/DEVICE/{dev_id}/values/timeseries?keys={keys}&startTs={int(t0)}&endTs={int(t1)}&limit={limit}&agg=NONE&orderBy=ASC", timeout=120)
    return dev_id, (d if c == 200 and isinstance(d, dict) else {})

# ------------------------------------------------------------------ utilidades
def hb(t, seg=False):
    return (dt.datetime.utcfromtimestamp(t / 1000) - BOG).strftime("%H:%M:%S" if seg else "%H:%M")

def fecha_bog(t):
    return (dt.datetime.utcfromtimestamp(t / 1000) - BOG)

def hbd(t):
    d = fecha_bog(t)
    return f"{d.day} {MESES[d.month-1]} {d.strftime('%H:%M')}"

def ts_bog(y, m, d, hh=0, mm=0):
    return int(((dt.datetime(y, m, d, hh, mm) + BOG) - dt.datetime(1970, 1, 1)).total_seconds() * 1000)

def fmt(s):
    s = int(round(s))
    if s <= 0:
        return "0 s"
    h, r = divmod(s, 3600); m, x = divmod(r, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {x:02d} s" if x else f"{m} min"
    return f"{x} s"

def dec(x, n=1):
    return (f"%.{n}f" % x).replace(".", ",")

def esc(x):
    return html.escape(str(x), quote=True)

def num(v):
    try:
        return float(v)
    except Exception:
        return None

def S(data, key):
    """Serie ordenada [(ts, valor)] con valores numéricos como float y textos tal cual."""
    out = []
    for p in sorted(data.get(key, []), key=lambda p: p["ts"]):
        f = num(p["value"])
        out.append((p["ts"], f if f is not None else p["value"]))
    return out

def pares(ev):
    out, o = [], None
    for t, v in ev:
        if v == "po" and o is None:
            o = t
        elif v == "pr" and o is not None:
            out.append([o, t]); o = None
        elif v == "pr" and o is None:
            out.append([None, t])
    if o is not None:
        out.append([o, None])
    return out

def antes(L, t, tol=1800000):
    c = [(k, v) for k, v in L if k <= t and t - k <= tol]
    return c[-1] if c else None

def despues(L, t, tol=1800000):
    c = [(k, v) for k, v in L if k >= t and k - t <= tol]
    return c[0] if c else None

def contador(L, t, tol=1800000):
    """Valor del contador acumulado en el instante t (muestra más cercana dentro de la tolerancia)."""
    c = [(abs(k - t), v) for k, v in L if abs(k - t) <= tol and isinstance(v, float)]
    return min(c)[1] if c else None

def delta(L, a, b):
    x, y = contador(L, a), contador(L, b)
    if x is None or y is None or y < x:
        return None
    return y - x

try:
    KWP = json.load(open(os.path.join(HERE, "potencia_instalada.json"), encoding="utf8"))
except (OSError, ValueError):
    KWP = {}
HMC = {}   # cierres diarios de los medidores (CenergyAI, CenergyAE) por dispositivo
def bal_dia(s, d0, d1):
    """Balance de medidores del día: generación = demanda (CenergyAI del medidor solar) − importada + exportada (CenergyAI/AE del medidor de red). Devuelve (generación kWh, demanda kWh) o None."""
    for r in s["red"]:
        for q in s["solar"]:
            L = HMC.get(r["id"], {}); M = HMC.get(q["id"], {})
            dem = delta(M.get("CenergyAI", []), d0, d1); imp = delta(L.get("CenergyAI", []), d0, d1); exp_ = delta(L.get("CenergyAE", []), d0, d1)
            if dem is not None and imp is not None and exp_ is not None:
                return (dem - imp + exp_) / 1000, dem / 1000
    return None

# ------------------------------------------------------------------ ventana
def ventana(args):
    ahora = dt.datetime.utcnow() - BOG
    fin = dt.datetime.strptime(args.fin, "%Y-%m-%dT%H:%M") if args.fin else ahora.replace(second=0, microsecond=0)
    if args.inicio:
        ini = dt.datetime.strptime(args.inicio, "%Y-%m-%dT%H:%M")
    elif fin.weekday() == 0:            # lunes: desde el viernes a las 7:00
        v = fin - dt.timedelta(days=3)
        ini = v.replace(hour=7, minute=0)
    else:
        ini = fin - dt.timedelta(hours=24)
    f = lambda d: ts_bog(d.year, d.month, d.day, d.hour, d.minute)
    return f(ini), f(fin), ini, fin

# ------------------------------------------------------------------ sistemas
def construir_sistemas(devs, attrs):
    """Agrupa dispositivos por (ciudad, casa). Una casa = medidor de red + medidor solar + inversor(es) + gateway(s)."""
    pul = {}
    for dv in devs:
        if dv["type"] == "pulsar":
            a = attrs[dv["id"]["id"]]
            pul[dv["name"]] = a.get("spcus")
    SYS = {}
    for dv in devs:
        a = attrs[dv["id"]["id"]]
        gw = a.get("gateway") if dv["type"] != "pulsar" else dv["name"]
        casa = a.get("spcus") or pul.get(gw)
        ciudad = a.get("city") or "SIN CIUDAD"
        if not casa:
            continue
        s = SYS.setdefault((ciudad, casa), dict(ciudad=ciudad, zona=a.get("zone") or "", casa=casa, inv=[], red=[], solar=[], pul=[], marca="", modelo="", cap=None))
        s["zona"] = s["zona"] or a.get("zone") or ""
        rec = dict(id=dv["id"]["id"], name=dv["name"], attrs=a)
        if dv["type"] == "inverter":
            s["inv"].append(rec)
        elif dv["type"] == "meter":
            (s["red"] if a.get("mettype") == "red" else s["solar"]).append(rec)
        elif dv["type"] == "pulsar":
            s["pul"].append(rec)
    return SYS

def cargar_exclusiones():
    """exclusiones.json (opcional): {"excluir": ["Casa X"], "incluir": ["Casa Y"]} para corregir a mano la regla automática."""
    ruta = os.path.join(HERE, "exclusiones.json")
    try:
        with open(ruta, encoding="utf8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    norm = lambda L: {str(x).strip().lower() for x in d.get(L, [])}
    return norm("excluir"), norm("incluir")

def motivo_exclusion(s, HPD, d_ini, d_fin, manual_ex, manual_in):
    """Devuelve el motivo por el que un sistema no entra al reporte, o None si debe incluirse.
    - Pilotos (nombre con "Piloto").
    - Casas sin generación FV: solo tienen las baterías de respaldo instaladas, así que el inversor nunca supera PV_MIN_KWH al día.
    """
    nombre = s["casa"].strip().lower()
    if nombre in manual_in:
        return None
    if nombre in manual_ex:
        return "lista manual"
    if "piloto" in nombre:
        return "piloto"
    dias_dato = {}
    for d0 in range(d_ini, d_fin, 86400000):
        b = bal_dia(s, d0, d0 + 86400000)
        if b is not None:
            dias_dato[d0] = b[0]
    if len(dias_dato) >= PV_MIN_DIAS and max(dias_dato.values()) <= PV_MIN_KWH:
        return "sin generación FV (solo baterías)"
    return None

def ordenar_ciudad(c):
    o = ["CALI", "TURBACO", "BARRANQUILLA", "CARTAGENA"]
    return (o.index(c) if c in o else 99, c)

def num_casa(nombre):
    m = re.search(r"\d+", nombre)
    return (int(m.group()) if m else 0, nombre)

def elegir_activo(lst, datos, claves):
    """Entre varios dispositivos de la misma casa, el que tiene el dato más reciente."""
    mejor, mt = None, -1
    for r in lst:
        d = datos.get(r["id"], {})
        t = max([p["ts"] for k in claves for p in d.get(k, [])] or [-1])
        if t > mt:
            mejor, mt = r, t
    return mejor, mt


TRANSFER_MAX = 120   # s: un hueco "al caer" de hasta 2 min es la transferencia a isla; un hueco "durante" de 2 min o más es una caída del respaldo
SOC_AGOTADA = 12     # % de SOC con el que se considera batería agotada
RETARDO_MIN = 60     # s: si la casa ve más de 1 min sin tensión al caer la red y la batería estaba cargada (SOC al inicio del corte > RESERVA), es un retardo de transferencia
UNION_S = 60         # s: huecos del arranque con menos de este tiempo de tensión entre ellos cuentan como una sola interrupción (algunos Deye cortan dos veces con ~9 s de por medio)

def interrupcion_al_caer(hu):
    """(s sin tensión, n huecos) de la interrupción que ve la casa al caer la red: el primer hueco "al caer" más los que le siguen pegados (< UNION_S de tensión en medio).
    Los huecos separados (a mitad del corte o al volver la red) no se suman."""
    gs = sorted(hu, key=lambda h: h["a"])
    ini = next((h for h in gs if h["tipo"] == "al caer"), None)
    if ini is None:
        return 0, 0
    fin = ini["a"] + ini["d"] * 1000
    seg, n = ini["d"], 1
    for h in gs:
        if h["a"] > ini["a"] and h["tipo"] in ("al caer", "durante") and h["a"] - fin <= UNION_S * 1000:
            seg += h["d"]; n += 1; fin = max(fin, h["a"] + h["d"] * 1000)
    return seg, n

def veredicto_respaldo(c, bpw, soc, W1):
    """(veredicto, fuente, causa) de un corte. Veredicto: total | total con transferencia | retardo de transferencia | caída durante el respaldo | sin respaldo."""
    a = c["a"]; b = c["b"] if c["b"] is not None else W1
    pw = [v for t, v in bpw if a <= t <= b]
    if pw:
        med = st.median(pw)
        fuente = "batería" if med > 200 else ("solar" if med < -200 else "solar + batería llena")
    else:
        fuente = None
    hu = c.get("hu") or []
    durante = [h for h in hu if h["tipo"] == "durante" and h["d"] >= TRANSFER_MAX]
    caer, n_caer = interrupcion_al_caer(hu)
    soc0 = c.get("soc0")
    cargada = soc0 is not None and soc0 > RESERVA
    causa = None
    if not hu:
        v = "Respaldo total"
    elif durante:
        v = "Caída durante el respaldo"
        h0 = min(durante, key=lambda h: h["a"])
        sc = [x for t, x in soc if t <= h0["a"] + 300000]
        sc = sc[-1] if sc else None
        causa = "batería agotada" if sc is not None and sc <= SOC_AGOTADA else ("SOC %d %%: revisar inversor" % round(sc) if sc is not None else "revisar inversor")
    elif c.get("cob") is not None and c["cob"] < 5:
        v = "Sin respaldo"
    elif caer > RETARDO_MIN and cargada:
        v = "Retardo de transferencia"
        causa = f"sin tensión {fmt(caer)} al caer" + (f" en {n_caer} huecos" if n_caer > 1 else "") + f" · SOC {soc0:.0f} %"
    else:
        v = "Respaldo total con transferencia"
    return v, fuente, causa

# ------------------------------------------------------------------ análisis por sistema
def analizar(s, D, W0, W1, dias):
    """D: datos por id de dispositivo. Devuelve un dict con interrupciones, respaldo, rendimiento, exportación y comunicación."""
    inv, t_inv = elegir_activo(s["inv"], D, ["BattSOC", "voltGridA", "activityState"])
    red, t_red = elegir_activo(s["red"], D, ["voltageA", "energyAE", "event", "activityState"])
    sol, t_sol = elegir_activo(s["solar"], D, ["energyAI", "event", "activityState"])
    pu, t_pu = elegir_activo(s["pul"], D, ["activityState"])
    di = D.get(inv["id"], {}) if inv else {}
    dr = D.get(red["id"], {}) if red else {}
    ds = D.get(sol["id"], {}) if sol else {}
    dp = D.get(pu["id"], {}) if pu else {}
    s["marca"] = ((inv["attrs"].get("invbrand") or "") if inv else "").upper()
    s["modelo"] = ((inv["attrs"].get("invmodel") or "") if inv else "").strip()
    s["cap_inv"] = num(inv["attrs"].get("invcap")) if inv else None
    s["cap"] = KWP.get(s["casa"].strip().lower())   # potencia pico instalada en DC (kWp), del archivo de sistemas
    R = dict(sys=s, inv_name=inv["name"] if inv else None)
    # --- comunicación
    R["ult"] = dict(inv=t_inv if t_inv > 0 else None, red=t_red if t_red > 0 else None, solar=t_sol if t_sol > 0 else None)
    # el gateway solo registra cambios de estado (online/offline), no una muestra periódica
    gwa = S(dp, "activityState")
    R["gw"] = gwa[-1] if gwa else None
    # --- batería
    soc = [(t, v) for t, v in S(di, "BattSOC") if isinstance(v, float)]
    soc = [(t, v) for i, (t, v) in enumerate(soc) if not (v == 0.0 and 0 < i < len(soc) - 1 and soc[i-1][1] > 10 and soc[i+1][1] > 10)]
    vga, vgb, vgc = (S(di, k) for k in ("voltGridA", "voltGridB", "voltGridC"))
    R["soc"] = soc
    # --- estado actual de la red (señal del inversor, umbral < 5 V; regla del equipo)
    live = bool(soc) and W1 - soc[-1][0] <= 30 * 60000
    def bajo(L): return bool(L) and isinstance(L[-1][1], float) and L[-1][1] < 5
    vg_bajo = live and bajo(vga) and (not vgb or bajo(vgb)) and (not vgc or bajo(vgc))
    ra = S(dr, "activityState")
    red_muerto = bool(ra) and ra[-1][1] == "noResponse"
    rv = [(t, v) for t, v in S(dr, "voltageA") if isinstance(v, float)]
    # primera muestra del inversor sin entrada de red (< 5 V) en la racha actual
    t_caida = None
    for t, v in reversed(vga):
        if isinstance(v, float) and v >= 5:
            break
        t_caida = t
    # el medidor de red solo cuenta como "presente" si tiene una muestra igual o posterior a la caída del inversor: un medidor sin tensión deja de enviar datos y su último valor ("123 V") es viejo
    red_presente = bool(rv) and W1 - rv[-1][0] <= 45 * 60000 and rv[-1][1] >= 90 and not red_muerto and (t_caida is None or rv[-1][0] >= t_caida - 120000)
    # inversor sin entrada de red mientras el medidor de red marca tensión: inversor aislado, no es un corte de red
    R["aislado"] = bool(vg_bajo and red_presente)
    R["live"] = live; R["vg_bajo"] = vg_bajo; R["soc_ult"] = soc[-1] if soc else None
    # --- cortes de red (medidor de red)
    ev_red = [(t, v) for t, v in S(dr, "event") if v in ("po", "pr")]
    cortes = []
    for a, b in pares(ev_red):
        if a is None:
            if b is not None and b >= W0:          # el corte empezó antes del historial consultado
                cortes.append(dict(a=W0, b=b, abierto=False, ant=True, estimado=True))
            continue
        fin_c = b if b is not None else W1
        if fin_c < W0 or a > W1:
            continue
        cortes.append(dict(a=a, b=b, abierto=b is None, ant=False))
    # corte en curso sin evento aún (el medidor de red sin tensión no envía eventos hasta que vuelve)
    en_curso = vg_bajo and not R["aislado"] and (red_muerto or not cortes or cortes[-1]["b"] is not None)
    if en_curso and not any(c["abierto"] for c in cortes):
        # inicio estimado: primera muestra de inversor con tensión < 5 V tras la última con red
        t_ini = None
        for t, v in reversed(vga):
            if isinstance(v, float) and v >= 5:
                break
            t_ini = t
        cortes.append(dict(a=t_ini if t_ini else W1 - 15 * 60000, b=None, abierto=True, ant=False, estimado=True))
    R["en_curso"] = en_curso
    # tensión en la casa (medidor solar, lado respaldado) durante un corte en curso: si hay tensión, el BESS está respaldando
    sv = [(t, v) for t, v in S(ds, "voltageA") if isinstance(v, float)]
    R["sol_v"] = sv[-1] if sv else None
    R["bess"] = bool(en_curso and sv and W1 - sv[-1][0] <= 20 * 60000 and sv[-1][1] >= 130)
    # --- huecos de tensión en la casa (medidor solar)
    ev_sol = [(t, v) for t, v in S(ds, "event") if v in ("po", "pr")]
    huecos = []
    for a, b in pares(ev_sol):
        if a is None:
            continue
        fin_h = b if b is not None else W1
        if fin_h < W0 or a > W1:
            continue
        huecos.append(dict(a=a, b=b, d=(fin_h - a) / 1000))
    bpw = sorted((t, v) for r in s["inv"] for t, v in S(D.get(r["id"], {}), "BattPower") if isinstance(v, (int, float)))
    # --- respaldo por corte
    # cada hueco del medidor solar cuenta en un solo corte (regla del equipo): el que empieza cerca de su inicio (al caer), si no el que lo contiene,
    # si no el último que terminó hasta 10 min antes. Sin esto, un hueco que empieza justo antes de un segundo corte también se sumaba al corte anterior.
    dueno = {}
    for h in huecos:
        mejor = None
        for c in cortes:
            if c["a"] is None:
                continue
            fin_c = c["b"] if c["b"] is not None else W1
            if abs(h["a"] - c["a"]) <= GAP_RADIO: rango = (0, abs(h["a"] - c["a"]))
            elif c["a"] <= h["a"] <= fin_c: rango = (1, 0)
            elif fin_c < h["a"] <= fin_c + 10 * 60000: rango = (2, h["a"] - fin_c)
            else: continue
            if mejor is None or rango < mejor[0]:
                mejor = (rango, c)
        if mejor:
            dueno[id(h)] = mejor[1]
    usados = set()
    for c in cortes:
        if c["a"] is None:
            c.update(dur=None, hu=[], perc=0, caer=None, volver=None, cob=None); continue
        fin_c = c["b"] if c["b"] is not None else W1
        c["a_v"] = max(c["a"], W0); c["b_v"] = min(fin_c, W1)
        c["dur"] = (c["b_v"] - c["a_v"]) / 1000
        hu = [h for h in huecos if dueno.get(id(h)) is c]
        for h in hu:
            usados.add(id(h))
            if abs(h["a"] - c["a"]) <= GAP_RADIO: h["tipo"] = "al caer"
            elif c["b"] is not None and abs(h["a"] - c["b"]) <= GAP_RADIO: h["tipo"] = "al volver"
            else: h["tipo"] = "durante" if (c["b"] is None or h["a"] < c["b"]) else "al reconectar"
        c["hu"] = hu
        c["perc"] = sum(h["d"] for h in hu)
        c["caer"] = sum(h["d"] for h in hu if h["tipo"] == "al caer")
        c["volver"] = sum(h["d"] for h in hu if h["tipo"] in ("al volver", "al reconectar"))
        # regla del equipo: respaldo = (tiempo medidor de red − tiempo medidor solar) / tiempo medidor de red, en cada corte (incluye los huecos al caer, a mitad y al volver)
        c["cob"] = max(0.0, 100.0 * (1 - c["perc"] / c["dur"])) if c["dur"] else None
        # batería durante el corte
        s0 = antes(soc, c["a"]) or (soc[0] if soc else None)
        en = [v for t, v in soc if c["a"] <= t <= (c["b"] if c["b"] is not None else W1)]
        s1 = despues(soc, c["b"]) if c["b"] is not None else (soc[-1] if soc else None)
        c["soc0"] = s0[1] if s0 else None; c["socmin"] = min(en) if en else None; c["soc1"] = s1[1] if s1 else None
        # veredicto de respaldo: tipo de hueco en el medidor solar + quién alimenta la casa + causa de la caída
        c["veredicto"], c["fuente"], c["causa"] = veredicto_respaldo(c, bpw, soc, W1)
    R["cortes"] = [c for c in cortes if c["a"] is not None]
    R["huecos_fuera"] = [h for h in huecos if id(h) not in usados]
    R["huecos"] = huecos
    # --- estados del inversor
    est = []
    run = S(di, "invrun")
    for t, v in run:
        if W0 <= t <= W1 and v in ("fault", "alarm", "standby", "activating", "shutting_down"):
            est.append((t, v))
    ev_i = [(t, v) for t, v in S(di, "event") if W0 <= t <= W1]
    R["est"] = est; R["codigos"] = ev_i
    # --- generación FV por día (contador diario energyPD, Wh)
    R["pv"] = {}; R["dem"] = {}
    for d0, d1 in dias:
        b = bal_dia(s, d0, d1)
        R["pv"][d0] = b[0] if b else None
        R["dem"][d0] = b[1] if b else None
    R["pv_hist"] = {}
    # --- energía en medidores (kWh): exportación e importación de red, consumo del lado respaldado
    aE = S(dr, "energyAE"); aI = S(dr, "energyAI"); cI = S(ds, "energyAI")
    segs = []
    for d0, d1 in dias:
        segs.append((d0, max(d0, W0), min(d1, W1)))
    R["exp"] = {}; R["imp"] = {}; R["cons"] = {}
    for d0, a, b in segs:
        for nombre, L in (("exp", aE), ("imp", aI), ("cons", cI)):
            x = delta(L, a, b)
            R[nombre][d0] = x / 1000 if x is not None else None
    for nombre, L in (("exp", aE), ("imp", aI), ("cons", cI)):
        x = delta(L, W0, W1)
        R[nombre]["total"] = x / 1000 if x is not None else None
    return R

# ------------------------------------------------------------------ agregación
def eventos_de_red(RS):
    """Agrupa los cortes de varios sistemas de la misma ciudad que empiezan con menos de 3 min de diferencia."""
    L = []
    for R in RS:
        for c in R["cortes"]:
            L.append((R["sys"]["ciudad"], c["a"], R, c))
    L.sort(key=lambda x: (ordenar_ciudad(x[0]), x[1]))
    ev = []
    for ciudad, a, R, c in L:
        if ev and ev[-1]["ciudad"] == ciudad and a - ev[-1]["ult"] <= 180000:
            e = ev[-1]; e["ult"] = a; e["m"].append((R, c))
        else:
            ev.append(dict(ciudad=ciudad, ini=a, ult=a, m=[(R, c)]))
    for e in ev:
        e["n"] = len(set(id(R) for R, c in e["m"]))
        e["cortes"] = len(e["m"])
        e["fin"] = None if any(c["b"] is None for R, c in e["m"]) else max(c["b"] for R, c in e["m"])
        durs = [c["dur"] for R, c in e["m"] if c["dur"]]
        e["dur"] = st.median(durs) if durs else None
    return ev

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fin"); ap.add_argument("--inicio")
    ap.add_argument("--salida", default="reporte_diario.html"); ap.add_argument("--json", default="resumen_diario.json")
    args = ap.parse_args()
    W0, W1, ini, fin = ventana(args)
    es_lunes = fin.weekday() == 0 and not args.inicio
    # días locales de la ventana cuya jornada solar termina antes del fin (para generación y exportación)
    d = ini.replace(hour=0, minute=0, second=0, microsecond=0)
    dias = []
    while d.date() < fin.date():
        dias.append((ts_bog(d.year, d.month, d.day), ts_bog(d.year, d.month, d.day) + 86400000))
        d += dt.timedelta(days=1)
    if not dias:
        dias = [(ts_bog(ini.year, ini.month, ini.day), ts_bog(ini.year, ini.month, ini.day) + 86400000)]
    t_cons = time.time()
    devs = listar_dispositivos()
    with cf.ThreadPoolExecutor(8) as ex:
        attrs = {dv["id"]["id"]: a for dv, a in ex.map(atributos, devs)}
    SYS = construir_sistemas(devs, attrs)
    # histórico de generación FV (9 días): patrón propio de cada casa y detección de casas sin FV
    HPD = {}
    h0 = ts_bog(ini.year, ini.month, ini.day) - 9 * 86400000
    tareas2 = [(r["id"], "energyPD", h0, W1 + 600000) for s in SYS.values() for r in s["inv"]]
    with cf.ThreadPoolExecutor(8) as ex:
        for i, d in ex.map(lambda t: serie(*t), tareas2):
            HPD[i] = S(d, "energyPD")
    tareas3 = [(r["id"], "CenergyAI,CenergyAE", h0 - 3600000, W1 + 600000) for s in SYS.values() for r in s["red"] + s["solar"]]
    with cf.ThreadPoolExecutor(8) as ex:
        for i, d in ex.map(lambda t: serie(*t), tareas3):
            HMC[i] = {"CenergyAI": S(d, "CenergyAI"), "CenergyAE": S(d, "CenergyAE")}
    # se excluyen los pilotos y las casas que solo tienen las baterías de respaldo (sin generación FV);
    # estas últimas no suman en generación, yield, cobertura ni exportación, pero se analizan aparte (SOLO_BAT)
    manual_ex, manual_in = cargar_exclusiones()
    EXCLUIDOS.clear()
    SOLO_BAT = []
    for k in sorted(SYS, key=lambda k: (ordenar_ciudad(k[0]), num_casa(k[1]))):
        m = motivo_exclusion(SYS[k], HPD, h0, dias[-1][1], manual_ex, manual_in)
        if m:
            EXCLUIDOS.append((k[0], SYS[k]["casa"], m))
            if m != "piloto":
                SOLO_BAT.append(SYS[k])
    for ciudad, casa, _ in EXCLUIDOS:
        del SYS[(ciudad, casa)]
    # telemetría
    IK = "invrun,invstate,voltGridA,voltGridB,voltGridC,BattSOC,BattPower,energyPD,activityState,event"
    MR = "event,voltageA,activityState,FlagStaProf,energyAE,energyAI,powerAI"
    MS = "event,activityState,energyAI,voltageA"
    tipo = {dv["id"]["id"]: dv["type"] for dv in devs}
    tareas = []
    for s in list(SYS.values()) + SOLO_BAT:
        for r in s["inv"]: tareas.append((r["id"], IK, W0 - 4 * 3600000, W1 + 600000))
        for r in s["red"]: tareas.append((r["id"], MR, W0 - 12 * 3600000, W1 + 600000))
        for r in s["solar"]: tareas.append((r["id"], MS, W0 - 12 * 3600000, W1 + 600000))
        for r in s["pul"]: tareas.append((r["id"], "activityState", W0 - 12 * 3600000, W1 + 600000))
    D = {}
    with cf.ThreadPoolExecutor(8) as ex:
        for i, d in ex.map(lambda t: serie(*t), tareas):
            D[i] = d
    # análisis
    RS = []
    for k in sorted(SYS, key=lambda k: (ordenar_ciudad(k[0]), num_casa(k[1]))):
        s = SYS[k]
        if not (s["inv"] or s["red"]):
            continue
        R = analizar(s, D, W0, W1, dias)
        inv, _ = elegir_activo(s["inv"], D, ["BattSOC", "voltGridA", "activityState"])
        hist, dem_hist = {}, {}
        if True:
            for q in range(1, 10):
                d0 = dias[0][0] - q * 86400000
                b = bal_dia(s, d0, d0 + 86400000)
                hist[d0] = b[0] if (b and b[0] > 0) else None
                dem_hist[d0] = b[1] if (b and b[1] > 0) else None      # consumo del cliente (demanda del medidor solar) de cada día previo
        R["pv_hist"] = hist; R["dem_hist"] = dem_hist; R["inv_id"] = inv["id"] if inv else None
        RS.append(R)
    # batería llena: primera hora de cada día evaluado en que el SOC llega a BATERIA_LLENA_SOC entre las 06:00 y las 18:00. Explica un yield bajo en sistemas
    # sin exportación: con la batería llena el inversor limita la producción FV al consumo de la casa.
    def _lleno(t):
        R, d0, d1 = t
        pts = sorted((p["ts"], num(p["value"])) for p in serie(R["inv_id"], "BattSOC", d0, d1, 1000)[1].get("BattSOC", []))
        return R, d0, next((ts for ts, v in pts if v is not None and v >= BATERIA_LLENA_SOC and d0 + 6 * 3600000 <= ts <= d0 + 18 * 3600000), None)
    for R in RS:
        R["lleno"] = {}
    with cf.ThreadPoolExecutor(8) as ex:
        for R, d0, ts in ex.map(_lleno, [(R, d0, d1) for R in RS if R["inv_id"] for d0, d1 in dias]):
            R["lleno"][d0] = ts
    # casas que solo tienen baterías: cortes, SOC y eventos del inversor, sin generación FV
    RB = [analizar(s, D, W0, W1, dias) for s in SOLO_BAT if s["inv"] or s["red"]]
    if os.environ.get("DUMP_PK"):
        import pickle; pickle.dump((RS, D, W0, W1), open(os.environ["DUMP_PK"], "wb"))
    if os.environ.get("DUMP_SV"):
        json.dump([dict(casa=R["sys"]["casa"], ciudad=R["sys"]["ciudad"], en_curso=R["en_curso"], sol_v=R.get("sol_v"), bess=R.get("bess"), W1=W1) for R in RS], open(os.environ["DUMP_SV"], "w"))
    exec(open(os.path.join(HERE, "reporte_html.py"), encoding="utf8").read(), globals())
    generar(RS, W0, W1, ini, fin, es_lunes, dias, args, t_cons, RB)

if __name__ == "__main__":
    main()
