# Genera el HTML del reporte diario. Se ejecuta dentro de reporte_diario.py (comparte sus funciones y constantes).

EXTRA_CSS = """
table.dt th{font-size:9.5px;letter-spacing:0;line-height:1.5;padding:10px 8px 8px;min-width:70px;white-space:nowrap}
table.dt th:first-child{min-width:120px}
table.dt td,table.dt th{padding-inline:6px;font-size:12.5px} table.dt th{white-space:normal;line-height:1.25;vertical-align:bottom}
table.dt td.n{white-space:nowrap} table.dt td small{white-space:nowrap}
tr.ciudad td{background:var(--line2);font-family:var(--f-d);font-weight:600;font-size:14px;letter-spacing:.02em}
.status.ok{background:var(--isl-bg);color:var(--good);border-color:var(--good)} .status.ok i{background:var(--good)}
.status.warn{background:var(--warn-bg);color:var(--warn-ink);border-color:var(--warn)} .status.warn i{background:var(--warn)}
.bar{display:block;height:9px;background:var(--accent);border-radius:2px;min-width:2px} .bar.crit{background:var(--crit)} .bar.warn{background:var(--ser)}
ul.pts{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:10px}
ul.pts li{display:flex;gap:10px;align-items:flex-start;font-size:14.5px;max-width:none}
ul.pts li .pill{flex:none;margin-top:2px}
details{border:1px solid var(--line);border-radius:6px;padding:10px 14px;background:var(--surface)}
details summary{cursor:pointer;font-weight:600}
table.dt th{font-size:9.5px;letter-spacing:0;line-height:1.5;padding:10px 8px 8px;min-width:70px;white-space:nowrap}
table.dt th:first-child{min-width:120px}
h1 .gh{font-size:.42em;font-weight:500;color:var(--muted);white-space:nowrap}
.sema{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.sm-card{background:var(--surface);border:1px solid var(--line);border-left:6px solid var(--line);border-radius:6px;padding:12px 14px;min-width:0;display:flex;flex-direction:column;gap:2px}
.sm-card.g{border-left-color:var(--good)} .sm-card.w{border-left-color:var(--warn)} .sm-card.c{border-left-color:var(--crit)}
.sm-card .t{display:flex;gap:8px;align-items:center;font-weight:600;font-size:13.5px}
.sm-card .ic{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;font-size:12px;font-weight:700;color:#fff;background:var(--muted)}
.sm-card.g .ic{background:var(--good)} .sm-card.w .ic{background:var(--warn);color:#2a1d00} .sm-card.c .ic{background:var(--crit)}
.sm-card .v{font-family:var(--f-d);font-size:36px;font-weight:700;line-height:1.05;font-variant-numeric:tabular-nums}
.sm-card small{color:var(--muted);font-size:11.5px;font-family:var(--f-m);white-space:normal}
svg rect.tl.g{fill:var(--good)} svg rect.tl.g.lite{fill:var(--good);opacity:.55} svg rect.tl.w{fill:var(--warn)} svg rect.tl.c{fill:var(--crit)}
svg text.soc-t{font-family:var(--f-m);font-size:9.5px;font-weight:600;fill:#fff;pointer-events:none}
svg rect.tl{stroke:var(--surface);stroke-width:1} svg rect.tl:hover{stroke:var(--ink);stroke-width:1.5}
svg .pat{stroke:var(--ink2);stroke-width:1.6} svg .lim{stroke:var(--warn);stroke-width:1.6;stroke-dasharray:5 4}
svg circle.yd{stroke:var(--surface);stroke-width:2} svg circle.yd.ok{fill:var(--accent)} svg circle.yd.w{fill:var(--warn)} svg circle.yd:hover{stroke:var(--ink)}
.legend i.lg{width:14px;height:10px;border-radius:2px;display:inline-block} .legend i.lg.g{background:var(--good)} .legend i.lg.g.lite{opacity:.55} .legend i.lg.w{background:var(--warn)} .legend i.lg.c{background:var(--crit)}
.legend i.dotl{width:10px;height:10px;border-radius:50%;display:inline-block} .legend i.dotl.ok{background:var(--accent)} .legend i.dotl.w{background:var(--warn)}
.sm-card .v .de{font-size:16px;font-weight:600;color:var(--ink2)}
.sm-card .kv{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;border-top:1px solid var(--line2);padding-top:3px;margin-top:3px} .sm-card .kv span{color:var(--ink2)} .sm-card .kv b{font-variant-numeric:tabular-nums}
svg rect.gb.gen{fill:var(--accent)} svg rect.gb.con{fill:var(--muted);opacity:.55}
svg rect.hb.g{fill:var(--good)} svg rect.hb.a{fill:var(--accent)} svg rect.hb.w{fill:var(--warn)} svg rect.hb.c{fill:var(--crit)}
svg polyline.sl{fill:none;stroke:var(--muted);stroke-width:1.2;opacity:.45;stroke-linejoin:round} svg polyline.sl:hover{opacity:1;stroke-width:2}
svg polyline.sl.hi{stroke:var(--crit);stroke-width:2.4;opacity:1}
svg rect.band{fill:var(--crit-bg);opacity:.7}
.legend i.lg.gen{background:var(--accent)} .legend i.lg.con{background:var(--muted);opacity:.55} .legend i.lg.gris{background:var(--muted);opacity:.45;height:3px} .legend i.lg.band{background:var(--crit-bg);border:1px solid var(--line)}
svg line.dl2{stroke:var(--accent);stroke-width:2.2} svg line.dl2.r{stroke:var(--crit)}
svg line.mn{stroke:var(--ink);stroke-width:2} svg line.mn.r{stroke:var(--crit)}
svg circle.d0{fill:var(--surface);stroke:var(--ink2);stroke-width:2}
svg circle.d1{fill:var(--accent);stroke:var(--surface);stroke-width:1.5} svg circle.d1.r{fill:var(--crit)}
svg text.soc-n{font-family:var(--f-m);font-size:11px;fill:var(--ink2)}
svg rect.hit,svg rect.hitb{fill:transparent} svg g.hg:hover rect.hitb{fill:var(--line2);opacity:.7} svg g.dm:hover rect.hit{fill:var(--line2);opacity:.7}
.legend i.dotl.hueco{background:var(--surface);border:2px solid var(--ink2);box-sizing:border-box} .legend i.lg.marca{width:3px;height:12px;background:var(--ink)}
svg rect.hm.g{fill:var(--good)} svg rect.hm.w{fill:var(--warn)} svg rect.hm.c{fill:var(--crit)} svg rect.hm.n{fill:var(--line2)}
svg text.hmt{font-family:var(--f-m);font-size:10px;font-weight:600;fill:#fff;pointer-events:none} svg text.hmt.w{fill:#2a1d00} svg text.hmt.n{fill:var(--muted)}
svg circle.yd.t{fill:var(--accent);opacity:.55}
.legend i.lg.vacia{background:var(--line2);border:1px solid var(--line)} .legend i.lg.a{background:var(--accent)} .legend i.dotl.t{background:var(--accent);opacity:.55}
.soc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:6px 22px}
.soc-row{display:flex;align-items:center;gap:8px;font-size:12.5px}
.soc-row .sn{width:74px;flex:none;white-space:nowrap}
.soc-row .soc{flex:1;min-width:0}
"""

VISUAL = True       # panel gráfico "Vista rápida" (semáforo, línea de tiempo, baterías y yield); False lo quita


def _kwh(x, n=1):
    return "—" if x is None else dec(x, n)


def _dia(d0):
    d = fecha_bog(d0)
    return f"{DIAS[d.weekday()][:3]} {d.day} {MESES[d.month-1]}"


def _pl(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def _pill(nivel, txt):
    return f'<span class="pill {nivel}">{esc(txt)}</span>'


def generar(RS, W0, W1, ini, fin, es_lunes, dias, args, t_cons, RB=()):
    # RB: casas que solo tienen baterías (sin FV). Entran en la tabla propia, en baterías en reserva y en los
    # eventos del inversor, pero no en generación, yield, cobertura, exportación ni en los totales de cortes.
    RB = sorted(RB, key=lambda R: (ordenar_ciudad(R["sys"]["ciudad"]), num_casa(R["sys"]["casa"])))
    css = open(os.path.join(HERE, "estilos.css"), encoding="utf8").read() + EXTRA_CSS
    n_sys = len(RS)
    ciudades = sorted({R["sys"]["ciudad"] for R in RS}, key=ordenar_ciudad)
    ndias = len(dias)
    nombre_dias = [_dia(d0) for d0, _ in dias]
    # periodos de los datos: la ventana del reporte (no empieza ni termina a medianoche) y los días completos (00:00–24:00, con cierre diario del medidor)
    def _rango(a, b):
        cierra_dia = fecha_bog(b).hour == 0 and fecha_bog(b).minute == 0
        return f"{hb(a)}–{'24:00' if cierra_dia else hb(b)}"
    vent_h = f"{hbd(W0)} →<br>{hbd(W1)}"
    per_dias = f"{nombre_dias[0]}<br>00:00–24:00" if ndias == 1 else f"{nombre_dias[0]} a {nombre_dias[-1]}<br>días completos"
    segs_ex = [(d0, max(d0, W0), min(d1, W1)) for d0, d1 in dias]
    if dias and W1 > dias[-1][1]:
        segs_ex.append((dias[-1][1], dias[-1][1], W1))       # hoy, hasta la hora de corte
    titulo = ("Operación fin de semana " if es_lunes else "Operación diaria ") + f"{fin.day} {MESES[fin.month-1]}"
    h_ini = f"{DIAS[ini.weekday()]} {ini.day} {MESES[ini.month-1]} {ini.strftime('%H:%M')}"
    h_fin = f"{DIAS[fin.weekday()]} {fin.day} {MESES[fin.month-1]} {fin.strftime('%H:%M')}"
    horas = (W1 - W0) / 3600000

    # ------------------------------------------------ eventos de red
    EV = eventos_de_red(RS)
    n_por_ciudad = {c: sum(1 for R in RS if R["sys"]["ciudad"] == c) for c in ciudades}
    con_cortes = [R for R in RS if R["cortes"]]
    en_curso = [R for R in RS if R["en_curso"]]
    total_cortes = sum(len(R["cortes"]) for R in RS)

    # ------------------------------------------------ generación FV
    cap_ok = lambda R: R["sys"]["cap"] and R["sys"]["cap"] > 0
    for R in RS:
        s = R["sys"]; vs = [v for v in R["pv"].values() if v is not None]
        R["pv_tot"] = sum(vs) if vs else None
        R["sy_anual"] = (R["pv_tot"] / ndias / s["cap"] * 365) if (R["pv_tot"] is not None and cap_ok(R)) else None
        # frente al yield patrón de su región (Cali / costa), definido por el usuario: yield anual proyectado del sistema ÷ patrón
        R["patron"] = patron_yield(s["ciudad"])
        R["ratio"] = (R["sy_anual"] / R["patron"]) if (R["sy_anual"] is not None and R["patron"]) else None
        # bajo consumo: el consumo del cliente (demanda del medidor solar) en los días evaluados cayó por debajo de CONSUMO_BAJO del habitual de la casa
        # (mediana de sus días previos, mínimo 3 días con dato)
        dem_v = list(R["dem"].values()); prev = [v for v in R.get("dem_hist", {}).values() if v]
        R["bajo_consumo"] = bool(dem_v and all(v is not None for v in dem_v) and len(prev) >= 3 and sum(dem_v) / ndias < CONSUMO_BAJO * st.median(prev))
        # producción limitada: sin exportación, con la batería llena el inversor limita la producción FV al consumo de la casa.
        # Batería llena antes de LLENO_ANTES_H (en al menos la mitad de los días evaluados) = "producción limitada";
        # entre LLENO_ANTES_H y LLENO_TARDE_H = "producción limitada en la tarde" (solo se pierde parte de la tarde).
        n_ll = len(R.get("lleno", {}))
        manana = [t for t in R.get("lleno", {}).values() if t is not None and fecha_bog(t).hour < LLENO_ANTES_H]
        tarde = [t for t in R.get("lleno", {}).values() if t is not None and LLENO_ANTES_H <= fecha_bog(t).hour < LLENO_TARDE_H]
        R["limitada"] = None
        if manana and len(manana) * 2 >= n_ll:
            R["limitada"] = ("", min(manana) if ndias == 1 else None, f"antes de las {LLENO_ANTES_H}:00")
        elif tarde and (len(manana) + len(tarde)) * 2 >= n_ll:
            R["limitada"] = (" en la tarde", min(tarde) if ndias == 1 else None, f"entre las {LLENO_ANTES_H}:00 y las {LLENO_TARDE_H}:00")
        flag = None
        if R["pv_tot"] is None:
            flag = ("off", "sin cierre diario del medidor")
        elif R["pv_tot"] == 0:
            flag = ("crit", "sin producción")
        elif R["ratio"] is not None and R["ratio"] < 0.75:
            causas = []
            if R["bajo_consumo"]:
                causas.append("bajo consumo")
            if R["limitada"]:
                suf, t_ll, rango = R["limitada"]
                causas.append(f"producción limitada{suf} (batería llena {hb(t_ll) if t_ll else rango})")
            flag = ("warn", "baja vs patrón" + "".join(", " + c for c in causas))
        R["flag"] = flag
    pv_total = sum(R["pv_tot"] for R in RS if R["pv_tot"] is not None)
    # patrón del portafolio Sunny: media de la generación total de los días previos con la misma lista de sistemas
    prev_tot = []
    keys_prev = sorted({k for R in RS for k in R["pv_hist"]})
    for k in keys_prev:
        v = [R["pv_hist"][k] for R in RS if R["pv_hist"].get(k) is not None]
        if len(v) >= max(5, n_sys // 2):
            prev_tot.append(sum(v))
    pv_pat = st.median(prev_tot) * ndias if len(prev_tot) >= 3 else None

    # ------------------------------------------------ exportación
    exp_tot = sum(R["exp"]["total"] for R in RS if R["exp"].get("total") is not None)
    imp_tot = sum(R["imp"]["total"] for R in RS if R["imp"].get("total") is not None)
    for R in RS:
        g_ = R["pv_tot"]; dd_ = [v for v in R["dem"].values()]
        R["cons_cli"] = sum(dd_) if (dd_ and all(v is not None for v in dd_)) else None
        R["cob_sol"] = (100 * g_ / R["cons_cli"]) if (R["cons_cli"] and R["cons_cli"] > 0) else None
    _ok = [R for R in RS if R["cons_cli"] and R["cons_cli"] > 0 and R["pv_tot"] is not None]
    cob_flota = (100 * sum(R["pv_tot"] for R in _ok) / sum(R["cons_cli"] for R in _ok)) if _ok else None
    _cy = [R for R in RS if R["pv_tot"] is not None and cap_ok(R)]
    yield_flota = (sum(R["pv_tot"] for R in _cy) / ndias / sum(R["sys"]["cap"] for R in _cy) * 365) if _cy else None
    sin_exp = [R for R in RS if R["exp"].get("total") is not None and R["exp"]["total"] < 0.05]

    # ------------------------------------------------ comunicación (último dato de cada dispositivo)
    stale = []
    for R in RS:
        for k, nom in (("inv", "inversor"), ("red", "medidor de red"), ("solar", "medidor solar")):
            t = R["ult"].get(k)
            if t is None:
                continue
            if W1 - t > 2 * 3600000:
                stale.append((R, nom, t))
        if R["gw"] and R["gw"][1] == "offline":
            stale.append((R, "gateway (offline)", R["gw"][0]))
    sin_datos_inv = [R for R in RS if R["ult"]["inv"] is None or W1 - R["ult"]["inv"] > 2 * 3600000]

    # ------------------------------------------------ puntos relevantes
    P = []
    if en_curso:
        nombres = ", ".join(R["sys"]["casa"] for R in en_curso[:12]) + ("…" if len(en_curso) > 12 else "")
        bajos = [R for R in en_curso if R["soc_ult"] and R["soc_ult"][1] <= 35]
        txt = f"{_pl(len(en_curso), 'sistema sigue', 'sistemas siguen')} sin red al corte del reporte ({nombres})."
        if bajos:
            txt += " Con batería de 35 % o menos: " + ", ".join(f"{R['sys']['casa']} ({R['soc_ult'][1]:.0f} %)" for R in bajos) + "."
        P.append(("crit", "En curso", txt))
    ais = [R for R in RS if R["aislado"]]
    if ais:
        P.append(("crit", "Inversor aislado", f"{_pl(len(ais), 'inversor', 'inversores')} sin entrada de red (menos de 5 V) mientras su medidor de red marca tensión: " + ", ".join(f"{R['sys']['casa']} ({R['soc_ult'][1]:.0f} % de batería)" if R['soc_ult'] else R['sys']['casa'] for R in ais) + ". No es un corte de red; hay que revisar el inversor o su breaker de entrada."))
    if EV:
        sig = [e for e in EV if e["n"] >= 3 or (e["dur"] or 0) >= 60 or e["fin"] is None]
        micro = [e for e in EV if e not in sig]
        resumen = []
        for e in sig[:6]:
            dur = "en curso" if e["fin"] is None else fmt(e["dur"] or 0)
            resumen.append(f"{e['ciudad'].title()} {hbd(e['ini'])} ({e['n']} de {n_por_ciudad.get(e['ciudad'], 0)} sistemas, {dur})")
        txt = f"{len(con_cortes)} de {n_sys} sistemas tuvieron cortes de red: {_pl(total_cortes, 'corte', 'cortes')} en {_pl(len(EV), 'evento', 'eventos')}."
        if resumen:
            txt += " Principales: " + "; ".join(resumen) + ("." if len(sig) <= 6 else f"; y {len(sig)-6} más.")
        if micro:
            ns = len(set(id(R) for e in micro for R, c in e["m"]))
            txt += f" Además, {_pl(len(micro), 'microcorte', 'microcortes')} de menos de 1 min en {_pl(ns, 'sistema', 'sistemas')}."
        P.append(("warn" if sig else "ok", "Interrupciones", txt))
    else:
        P.append(("ok", "Interrupciones", f"Ningún sistema registró cortes de red en la ventana ({fmt((W1-W0)/1000)})."))
    # respaldo
    cs = [c for R in RS for c in R["cortes"] if c.get("dur")]
    if cs:
        tot_dur = sum(c["dur"] for c in cs); tot_perc = sum(min(c["perc"], c["dur"]) for c in cs)
        cob = 100 * (1 - tot_perc / tot_dur) if tot_dur else None
        sinhueco = sum(1 for c in cs if c["perc"] == 0)
        largos = sorted(((c["perc"], R, c) for R in RS for c in R["cortes"] if c.get("dur") and c["perc"] >= 300), key=lambda x: -x[0])
        txt = f"La casa mantuvo tensión en {dec(cob, 1)} % del tiempo de corte; {sinhueco} de {len(cs)} cortes no dejaron ningún hueco."
        if largos:
            txt += f" Huecos de 5 min o más en {len(set(id(R) for _, R, _ in largos))} sistemas; el mayor, {largos[0][1]['sys']['casa']} con {fmt(largos[0][0])}."
        P.append(("warn" if largos else "ok", "Respaldo", txt))
    fuera = [(R, h) for R in RS for h in R["huecos_fuera"] if h["d"] >= 10]
    if fuera:
        P.append(("warn", "Respaldo", f"{_pl(len(fuera), 'hueco', 'huecos')} de tensión de 10 s o más en {_pl(len(set(id(R) for R, _ in fuera)), 'casa', 'casas')} sin un corte de red asociado en los medidores de red (el mayor, {fmt(max(h['d'] for R, h in fuera))})."))
    # baterías
    TODOS = list(RS) + list(RB)
    agot = [(R, c) for R in TODOS for c in R["cortes"] if c.get("socmin") is not None and c["socmin"] <= RESERVA]
    if agot:
        P.append(("crit", "Baterías", f"{len(set(id(R) for R, _ in agot))} sistemas llegaron a la reserva (SOC de {RESERVA:.0f} % o menos) durante un corte: " + ", ".join(sorted({R['sys']['casa'] for R, _ in agot}, key=num_casa)) + "."))
    # baterías en reserva al último dato (tengan o no corte); la hora se muestra solo si el dato tiene más de 30 min
    en_reserva = sorted((R for R in TODOS if R["soc_ult"] and R["soc_ult"][1] <= RESERVA), key=lambda R: num_casa(R["sys"]["casa"]))
    if en_reserva:
        def _res(R):
            t, v = R["soc_ult"]
            return f"{R['sys']['casa']} ({v:.0f} %" + (f", {hb(t)}" if W1 - t > 30 * 60000 else "") + ")"
        P.append(("warn", "Baterías en reserva", f"Con batería en reserva al corte del reporte, {hb(W1)} (SOC de {RESERVA:.0f} % o menos): " + ", ".join(_res(R) for R in en_reserva) + "."))
    # inversores
    fallas = [(R, t, v) for R in TODOS for t, v in R["est"] if v in ("fault", "alarm")]
    cods = [(R, t, v) for R in TODOS for t, v in R["codigos"]]
    if fallas or cods:
        txt = []
        if fallas:
            txt.append(f"{len(set(id(R) for R, _, _ in fallas))} inversores reportaron estado de falla o alarma ({', '.join(sorted({R['sys']['casa'] for R, _, _ in fallas}, key=num_casa))})")
        if cods:
            from collections import Counter
            cc = Counter(v for _, _, v in cods)
            por_sys = Counter(R["sys"]["casa"] for R, _, _ in cods)
            txt.append("códigos de evento de inversor: " + ", ".join(f"{k} ×{n}" for k, n in cc.most_common(4)) + f" en {len(por_sys)} sistemas (más repetidos: " + ", ".join(f"{k} ×{n}" for k, n in por_sys.most_common(3)) + ")")
        P.append(("warn", "Inversores", "; ".join(txt) + "."))
    # rendimiento
    bajas = [R for R in RS if R["flag"] and R["flag"][0] in ("warn", "crit")]
    sinprod = [R for R in RS if R["flag"] and R["flag"][1] == "sin producción"]
    if pv_total:
        cmp_ = ""
        if pv_pat:
            cmp_ = f" ({'+' if pv_total >= pv_pat else '−'}{dec(abs(100*(pv_total/pv_pat-1)), 0)} % frente a la mediana de los días previos)"
        P.append(("ok" if not bajas else "warn", "Rendimiento", f"Generación FV del portafolio Sunny: {dec(pv_total, 0)} kWh en {ndias} {'día' if ndias == 1 else 'días'}{cmp_}. Yield proyectado a un año: {dec(yield_flota, 0) if yield_flota else '—'} kWh/kWp·año; cobertura solar: {dec(cob_flota, 0) if cob_flota is not None else '—'} %." + (f" {len(bajas)} sistemas con producción baja: " + ", ".join(f"{R['sys']['casa']} ({R['flag'][1]})" for R in sorted(bajas, key=lambda R: R['ratio'] if R['ratio'] is not None else 0)[:8]) + ("…" if len(bajas) > 8 else "") + "." if bajas else "")))
    # exportación
    if exp_tot:
        top = sorted((R for R in RS if R["exp"].get("total")), key=lambda R: -R["exp"]["total"])[:3]
        P.append(("ok", "Exportación", f"Energía activa exportada a la red: {dec(exp_tot, 1)} kWh en la ventana ({'; '.join(R['sys']['casa'] + ' ' + dec(R['exp']['total'], 1) + ' kWh' for R in top)} lideran). {len(sin_exp)} sistemas no exportaron."))
    # comunicación
    if sin_datos_inv or stale:
        P.append(("warn", "Comunicación", f"{len(sin_datos_inv)} sistemas sin datos del inversor en las últimas 2 h ({', '.join(R['sys']['casa'] for R in sin_datos_inv[:10])}{'…' if len(sin_datos_inv) > 10 else ''}); {len(stale)} dispositivos con último dato de más de 2 h."))
    else:
        P.append(("ok", "Comunicación", "Todos los inversores reportaron en las últimas 2 h."))
    _mi = cargar_exclusiones()[1]
    _bajos = sorted((R for R in RS if R["sys"]["casa"].strip().lower() in _mi and R["pv_tot"] is not None and R["pv_tot"] < 5), key=lambda R: num_casa(R["sys"]["casa"]))
    if _bajos:
        P.append(("warn", "Casas en operación plena", "Estas casas se incluyen como operando plenamente, pero el contador de su inversor marca muy poca generación en la ventana: " + "; ".join(f"{R['sys']['casa']} {dec(R['pv_tot'], 1)} kWh" for R in _bajos) + ". Reducen el yield y la cobertura del portafolio Sunny; conviene confirmar que sus paneles estén conectados al inversor."))
    orden = {"crit": 0, "warn": 1, "ok": 2}
    P.sort(key=lambda p: orden[p[0]])
    PILL = {"crit": "crit", "warn": "warn", "ok": "okp"}

    # ------------------------------------------------ HTML
    def tabla(head, rows, ancho=900, cls="dt"):
        return f'<div class="scroll"><table class="{cls}" style="min-width:{ancho}px"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'

    # KPIs
    k_sis = f'<div class="kpi {"k-crit" if en_curso else ("k-warn" if con_cortes else "k-ok")}"><div class="v">{len(con_cortes)} <small>de {n_sys}</small></div><div class="l">sistemas con cortes de red en la ventana ({total_cortes} cortes en {len(EV)} eventos).{" " + str(len(en_curso)) + " siguen sin red." if en_curso else ""}</div></div>'
    k_pv = f'<div class="kpi"><div class="v">{dec(pv_total, 0)} <small>kWh</small></div><div class="l">de generación FV del portafolio Sunny en {ndias} {"día" if ndias == 1 else "días"}{(" (patrón " + dec(pv_pat, 0) + " kWh)") if pv_pat else ""}.</div></div>'
    k_exp = f'<div class="kpi"><div class="v">{dec(exp_tot, 0)} <small>kWh</small></div><div class="l">de energía activa exportada a la red entre el {hbd(W0)} y el {hbd(W1)}; importada {dec(imp_tot, 0)} kWh en el mismo periodo.</div></div>'
    cob_txt = "—"
    if cs:
        cob_txt = dec(cob, 1) + " %"
    k_res = f'<div class="kpi {"k-warn" if cs and cob is not None and cob < 99 else ""}"><div class="v">{cob_txt}</div><div class="l">del tiempo de corte con tensión en la casa (respaldo){"" if cs else ": sin cortes largos"}.</div></div>'
    k_yield = f'<div class="kpi"><div class="v">{dec(yield_flota, 0) if yield_flota else "—"} <small>kWh/kWp·año</small></div><div class="l">de yield proyectado a un año: generación diaria real de {len(_cy)} sistemas dividida entre su potencia pico instalada en DC (suma de kWp), por 365.</div></div>'
    k_cob = f'<div class="kpi"><div class="v">{dec(cob_flota, 0) if cob_flota is not None else "—"} <small>%</small></div><div class="l">de cobertura solar del portafolio Sunny: generación FV dividida entre el consumo de los clientes. La generación es el balance de medidores y el consumo es la demanda del medidor solar.</div></div>'
    # puntos
    li = "".join(f'<li>{_pill(PILL[n], t)}<span>{esc(x)}</span></li>' for n, t, x in P)

    # eventos de red
    rows = []
    for e in EV:
        mem = e["m"]; nper = len(set(id(R) for R, c in mem if c["perc"] > 0))
        mx = max(mem, key=lambda m: m[1]["perc"])
        cobs = [c["cob"] for R, c in mem if c["cob"] is not None]
        fin_txt = "en curso" if e["fin"] is None else hbd(e["fin"])
        rows.append(f'<tr><td>{esc(e["ciudad"].title())}</td><td>{hbd(e["ini"])}</td><td>{fin_txt}</td><td class="n">{e["n"]} de {n_por_ciudad.get(e["ciudad"], 0)}</td><td class="n">{fmt(e["dur"]) if e["dur"] else "—"}</td><td class="n">{nper} de {e["n"]}</td><td class="n">{fmt(mx[1]["perc"]) if mx[1]["perc"] else "—"}<small>{esc(mx[0]["sys"]["casa"]) if mx[1]["perc"] else ""}</small></td><td class="n">{(dec(st.median(cobs), 1) + " %") if cobs else "—"}</td></tr>')
    ev_head = '<th>Ciudad</th><th>Inicio</th><th>Fin</th><th class="n">Sistemas<br>afectados</th><th class="n">Duración<br>típica</th><th class="n">Casas con<br>hueco</th><th class="n">Mayor tiempo<br>sin tensión</th><th class="n">Respaldo<br>mediano</th>'
    sec_ev = tabla(ev_head, rows, 820) if rows else '<p class="note">Sin cortes de red en la ventana.</p>'

    # interrupciones y respaldo por sistema
    rows = []
    def soc_uno(x):
        return "—" if x is None else f"{x:.0f} %"
    def soc_txt(c):
        a, m, b = c.get("soc0"), c.get("socmin"), c.get("soc1")
        f = lambda x: "—" if x is None else f"{x:.0f}"
        return f"{f(a)} → {f(m)} → {f(b)} %"
    orden_sys = sorted(con_cortes, key=lambda R: (0 if R["en_curso"] else 1, -sum(c["dur"] or 0 for c in R["cortes"])))
    # una columna por corte: el último corte registrado de cada casa va completo; los anteriores (del más reciente al más antiguo, hasta MAX_PREV)
    # solo con la leyenda de su % de respaldo; los demás quedan en el desplegable de detalle
    MAX_PREV = 4
    n_prev = min(MAX_PREV, max((len(R["cortes"]) for R in con_cortes), default=1) - 1)
    def _pct(c):
        return "—" if c["cob"] is None else dec(c["cob"], 1) + " %"
    def _fin(c):
        if c["b"] is None:
            return "en curso"
        return hb(c["b"]) if fecha_bog(c["b"]).date() == fecha_bog(c["a"]).date() else hbd(c["b"])
    def _hora(c):
        """Hora de inicio del corte; con fecha si no es del día del reporte."""
        return (hb(c["a"]) if fecha_bog(c["a"]).date() == fin.date() else hbd(c["a"])) + ("≈" if c.get("estimado") else "")
    for R in orden_sys:
        s = R["sys"]; cc = sorted(R["cortes"], key=lambda c: c["a"])
        ultimo, previos = cc[-1], cc[-2::-1]       # previos: del más reciente al más antiguo
        ocultos = max(0, len(previos) - n_prev)
        tot = sum(c["dur"] or 0 for c in cc); perc = sum(c["perc"] for c in cc)
        estado = _pill("crit", "sin red") if R["en_curso"] else ""
        cls = "r0" if R["en_curso"] else ("r1" if perc >= 300 else "")
        cpeor = ultimo                      # el veredicto y su detalle son los del último corte, el mismo de la columna "Último corte"
        vr = cpeor.get("veredicto") or ""
        niv = {"Caída durante el respaldo": "crit", "Sin respaldo": "crit", "Retardo de transferencia": "warn", "Respaldo total con transferencia": "okp", "Respaldo total": "okp"}.get(vr, "off")
        vio = ("tiempo que vio la casa: " + (fmt(cpeor["perc"]) if cpeor.get("perc") else "0 s, sin hueco")) if cpeor.get("perc") is not None else ""
        vr_det = " · ".join(x for x in (vio, "alimenta: " + cpeor["fuente"] if cpeor.get("fuente") else "", cpeor.get("causa") or "") if x)
        celda_resp = _pill(niv, vr) + (f"<small>{esc(vr_det)}</small>" if vr_det else "") + ("<small>provisional: el corte sigue abierto</small>" if cpeor.get("abierto") else "")
        celdas_prev = "".join(
            (f'<td class="n"><small title="{esc(hbd(previos[i]["a"]) + ("≈" if previos[i].get("estimado") else "") + " · " + fmt(previos[i]["dur"] or 0))}">{_pct(previos[i])}</small><small>{_hora(previos[i])}</small><small>sin red: {fmt(previos[i]["dur"] or 0)}</small><small>vio: {fmt(previos[i]["perc"]) if previos[i].get("perc") else "0 s"}</small></td>' if i < len(previos) else "<td></td>")
            for i in range(n_prev))
        soc_i = lambda x: "—" if x is None else f"{x:.0f}"
        celda_ult = (f'<td style="white-space:nowrap"><b>{hbd(ultimo["a"])}{"≈" if ultimo.get("estimado") else ""} → {_fin(ultimo)}</b>'
                     f'<small>{fmt(ultimo["dur"] or 0)}</small><small>SOC {soc_i(ultimo.get("soc0"))} → {soc_i(ultimo.get("soc1"))} %</small><small>respaldo {_pct(ultimo)}</small></td>')
        rows.append(f'<tr class="{cls}"><td><b>{esc(s["casa"])}</b><small>{esc(s["ciudad"].title())} · {esc(s["marca"].title())} {esc(s["modelo"])}</small></td><td class="n">{len(cc)}{f"<small>{ocultos} más en el detalle</small>" if ocultos else ""}</td><td class="n">{fmt(tot)}</td><td class="n">{fmt(perc) if perc else "—"}</td>{celda_ult}{celdas_prev}<td>{estado}</td><td>{celda_resp}</td></tr>')
    sis_head = ('<th>Sistema</th><th class="n">Cortes</th><th class="n">Tiempo<br>sin red</th><th class="n">Tiempo que<br>vio la casa</th>'
                + '<th>Último corte<br>inicio → fin · duración<br>SOC inicio → fin · respaldo</th>'
                + "".join(f'<th class="n">Anterior {i + 1}<br>% respaldo<br>hora · sin red · vio</th>' for i in range(n_prev))
                + '<th>Ahora</th><th>Veredicto de respaldo<br>(último corte)</th>')
    sec_sis = tabla(sis_head, rows, 800 + 70 * n_prev) if rows else ""
    # casas que solo tienen baterías (sin FV): se reportan aparte
    sec_bat = ""
    tit_bat = ""
    if RB:
        rows = []
        for R in RB:
            s = R["sys"]; cc = R["cortes"]
            if cc:
                mayor = max(cc, key=lambda c: c["dur"] or 0)
                perc = sum(c["perc"] for c in cc); cobs = [c["cob"] for c in cc if c["cob"] is not None]
                celdas = [str(len(cc)), fmt(sum(c["dur"] or 0 for c in cc)), fmt(perc) if perc else "—", (dec(min(cobs), 1) + " %") if cobs else "—", soc_txt(mayor)]
            else:
                celdas = ["0", "—", "—", "—", "—"]
            soc = R["soc_ult"]
            soc_act = f"{soc[1]:.0f} %<small>{hb(soc[0])}</small>" if soc else "—"
            estado = _pill("crit", "sin red") if R["en_curso"] else ""
            rows.append(f'<tr class="{"r0" if R["en_curso"] else ""}"><td><b>{esc(s["casa"])}</b><small>{esc(s["ciudad"].title())} · {esc(s["marca"].title())} {esc(s["modelo"])}</small></td>' + "".join(f'<td class="n">{x}</td>' for x in celdas) + f'<td class="n">{soc_act}</td><td>{estado}</td></tr>')
        bat_head = '<th>Casa</th><th class="n">Cortes</th><th class="n">Tiempo<br>sin red</th><th class="n">Tiempo que<br>vio la casa</th><th class="n">Respaldo<br>(peor corte)</th><th class="n">SOC inicio → mín → fin<br>(mayor corte)</th><th class="n">SOC<br>actual</th><th>Ahora</th>'
        uno = len(RB) == 1
        sin_cortes = all(not R["cortes"] for R in RB)
        nota_bat = (f'SOC del último dato del inversor (hora debajo de cada valor). {", ".join(R["sys"]["casa"] for R in RB)} '
                    + ("solo tiene baterías instaladas" if uno else "solo tienen baterías instaladas")
                    + (": no cuenta" if uno else ": no cuentan") + " en generación, yield, cobertura ni exportación"
                    + ((", y no tuvo cortes de red" if uno else ", y no tuvieron cortes de red") if sin_cortes else "") + ".")
        tit_bat = "Casa solo con baterías (sin FV)" if uno else "Casas solo con baterías (sin FV)"
        sec_bat = tabla(bat_head, rows, 900) + f'<p class="note">{esc(nota_bat)}</p>'
    # detalle por corte
    def durante_txt(c):
        """Huecos de tensión a mitad del corte (ni al caer ni al volver la red): duración y hora de inicio de cada uno."""
        hs = [h for h in (c.get("hu") or []) if h.get("tipo") == "durante"]
        return "<br>".join(f'{fmt(h["d"])}<small>{hb(h["a"])}</small>' for h in hs) if hs else "—"
    rows = []
    for R in con_cortes:
        for c in sorted(R["cortes"], key=lambda c: c["a"]):
            fin_c = "en curso" if c["b"] is None else hbd(c["b"])
            rows.append(f'<tr><td><b>{esc(R["sys"]["casa"])}</b><small>{esc(R["sys"]["ciudad"].title())}</small></td><td>{hbd(c["a"])}{"≈" if c.get("estimado") else ""}</td><td>{fin_c}</td><td class="n">{fmt(c["dur"])}</td><td class="n">{fmt(c["caer"]) if c["caer"] else "—"}</td><td class="n">{durante_txt(c)}</td><td class="n">{fmt(c["volver"]) if c["volver"] else "—"}</td><td class="n">{fmt(c["perc"]) if c["perc"] else "—"}</td><td class="n">{(dec(c["cob"], 1) + " %") if c["cob"] is not None else "—"}</td><td class="n">{soc_txt(c)}</td></tr>')
    det_head = '<th>Sistema</th><th>Inicio</th><th>Fin</th><th class="n">Duración</th><th class="n">Hueco<br>al caer</th><th class="n">Hueco<br>durante</th><th class="n">Hueco<br>al volver</th><th class="n">Total que<br>vio la casa</th><th class="n">Respaldo</th><th class="n">SOC inicio → mín → fin</th>'
    sec_det = f'<details><summary>Detalle por corte ({len(rows)} filas)</summary><div style="margin-top:10px">{tabla(det_head, rows, 900)}</div></details>' if rows else ""

    # rendimiento
    rows = []
    for c in ciudades:
        _pt = patron_yield(c)
        rows.append(f'<tr class="ciudad"><td colspan="{5 + ndias}">{esc(c.title())}{f" · yield patrón {_pt} kWh/kWp·año" if _pt else ""}</td></tr>')
        for R in [R for R in RS if R["sys"]["ciudad"] == c]:
            s = R["sys"]
            cols = "".join(f'<td class="n">{_kwh(R["pv"].get(d0))}</td>' for d0, _ in dias)
            fl = _pill({"crit": "crit", "warn": "warn", "off": "off"}[R["flag"][0]], R["flag"][1]) if R["flag"] else ""
            rows.append(f'<tr><td><b>{esc(s["casa"])}</b><small>{esc(s["marca"].title())} {esc(s["modelo"])} · {dec(s["cap"], 2) if s["cap"] else "—"} kWp</small></td>{cols}<td class="n"><b>{_kwh(R["pv_tot"])}</b></td><td class="n">{dec(R["sy_anual"], 0) if R["sy_anual"] is not None else "—"}</td><td class="n">{(dec(100*R["ratio"], 0) + " %") if R["ratio"] is not None else "—"}</td><td>{fl}</td></tr>')
    pv_head = '<th>Sistema</th>' + "".join(f'<th class="n">{esc(n)}<br>00:00–24:00<br>kWh</th>' for n in nombre_dias) + '<th class="n">Total<br>kWh</th><th class="n">Yield anual<br>proyectado<br>kWh/kWp·año</th><th class="n">Frente al<br>yield patrón</th><th>Alerta</th>'
    sec_pv = tabla(pv_head, rows, 760 + 60 * ndias)

    # exportación
    rows = []
    for c in ciudades:
        rows.append(f'<tr class="ciudad"><td colspan="{7 + len(segs_ex)}">{esc(c.title())}</td></tr>')
        for R in sorted([R for R in RS if R["sys"]["ciudad"] == c], key=lambda R: -(R["exp"].get("total") or 0)):
            s = R["sys"]; t = R["exp"].get("total")
            cols = "".join(f'<td class="n">{_kwh(R["exp"].get(d0), 2)}</td>' for d0, _, _ in segs_ex)
            share = (100 * t / R["pv_tot"]) if (t is not None and R["pv_tot"]) else None
            rows.append(f'<tr><td><b>{esc(s["casa"])}</b></td>{cols}<td class="n"><b>{_kwh(t, 2)}</b></td><td class="n">{_kwh(R["imp"].get("total"), 1)}</td><td class="n">{_kwh(R["cons"].get("total"), 1)}</td><td class="n">{(dec(share, 1) + " %") if share is not None else "—"}</td><td class="n">{_kwh(R["cons_cli"], 1)}</td><td class="n"><b>{(dec(R["cob_sol"], 0) + " %") if R["cob_sol"] is not None else "—"}</b></td></tr>')
    ex_head = ('<th>Sistema</th>'
               + "".join(f'<th class="n">{_dia(d0)}<br>{_rango(a, b)}<br>kWh</th>' for d0, a, b in segs_ex)
               + f'<th class="n">Exportada<br>{vent_h}<br>kWh</th><th class="n">Importada<br>{vent_h}<br>kWh</th><th class="n">Consumo lado respaldado<br>{vent_h}<br>kWh</th>'
               + f'<th class="n">Exportada / generada<br>(ventana ÷ generación<br>{per_dias})</th><th class="n">Consumo del cliente<br>{per_dias}<br>kWh</th><th class="n">Cobertura solar<br>{per_dias}</th>')
    sec_ex = tabla(ex_head, rows, 900 + 80 * len(segs_ex))

    # comunicación
    rows = []
    for R, nom, t in sorted(stale, key=lambda x: x[2]):
        rows.append(f'<tr><td><b>{esc(R["sys"]["casa"])}</b><small>{esc(R["sys"]["ciudad"].title())}</small></td><td>{nom}</td><td>{hbd(t)}</td><td class="n">{fmt((W1 - t) / 1000)}</td></tr>')
    sec_com = tabla('<th>Sistema</th><th>Dispositivo</th><th>Último dato / offline desde</th><th class="n">Hace</th>', rows, 520) if rows else '<p class="note">Todos los medidores e inversores reportaron en las últimas 2 h y ningún gateway está offline.</p>'

    # resumen por ciudad
    rows = []
    for c in ciudades:
        g = [R for R in RS if R["sys"]["ciudad"] == c]
        pvc = sum(R["pv_tot"] for R in g if R["pv_tot"] is not None)
        _gy = [R for R in g if R["pv_tot"] is not None and cap_ok(R)]
        yc = (sum(R["pv_tot"] for R in _gy) / ndias / sum(R["sys"]["cap"] for R in _gy) * 365) if _gy else None
        _g = [R for R in g if R["cons_cli"] and R["cons_cli"] > 0 and R["pv_tot"] is not None]
        cobc = (100 * sum(R["pv_tot"] for R in _g) / sum(R["cons_cli"] for R in _g)) if _g else None
        exc = sum(R["exp"]["total"] for R in g if R["exp"].get("total") is not None)
        sd = sum(1 for R in g if R["ult"]["inv"] is None or W1 - R["ult"]["inv"] > 2 * 3600000)
        cuts = sum(len(R["cortes"]) for R in g)
        rows.append(f'<tr><td><b>{esc(c.title())}</b></td><td class="n">{len(g)}</td><td class="n">{sum(1 for R in g if R["cortes"])}</td><td class="n">{cuts}</td><td class="n">{sum(1 for R in g if R["en_curso"])}</td><td class="n">{dec(pvc, 0)}</td><td class="n">{dec(yc, 0) if yc else "—"}</td><td class="n">{(dec(cobc, 0) + " %") if cobc is not None else "—"}</td><td class="n">{dec(exc, 1)}</td></tr>')
    sec_ciu = tabla('<th>Ciudad</th><th class="n">Sistemas</th><th class="n">Con<br>cortes</th><th class="n">Cortes</th><th class="n">Sin red<br>ahora</th><th class="n">Generación<br>FV kWh</th><th class="n">Yield anual proyectado<br>kWh/kWp·año</th><th class="n">Cobertura<br>solar</th><th class="n">Exportada<br>kWh</th>', rows, 760)

    # por día (lunes)
    sec_dia = ""
    if ndias > 1:
        rows = []
        for d0, d1 in dias:
            pvd = sum(R["pv"].get(d0) or 0 for R in RS); exd = sum(R["exp"].get(d0) or 0 for R in RS); imd = sum(R["imp"].get(d0) or 0 for R in RS)
            cd = [(R, c) for R in RS for c in R["cortes"] if d0 <= c["a"] < d1]
            sd = len(set(id(R) for R, c in cd))
            rows.append(f'<tr><td><b>{_dia(d0)}</b></td><td class="n">{len(cd)}</td><td class="n">{sd}</td><td class="n">{dec(pvd, 0)}</td><td class="n">{dec(exd, 0)}</td><td class="n">{dec(imd, 0)}</td></tr>')
        sec_dia = '<section><details><summary>Por día</summary><div style="margin-top:10px">' + tabla('<th>Día</th><th class="n">Cortes<br>iniciados</th><th class="n">Sistemas<br>con cortes</th><th class="n">Generación FV<br>kWh</th><th class="n">Exportada<br>kWh</th><th class="n">Importada<br>kWh</th>', rows, 620) + '<p class="note" style="margin-top:10px">El viernes cuenta desde las 07:00 en cortes, exportación e importación; la generación FV es la del día completo.</p></div></details></section>'

    # ------------------------------------------------ panel gráfico: semáforo, línea de tiempo, baterías y yield
    sec_vis = ""
    if VISUAL:
        _niv = {"Respaldo total": "g", "Respaldo total con transferencia": "g", "Retardo de transferencia": "w", "Caída durante el respaldo": "c", "Sin respaldo": "c"}
        _ico = {"g": "✓", "w": "▲", "c": "✕"}
        _orden_v = ["Respaldo total", "Respaldo total con transferencia", "Retardo de transferencia", "Caída durante el respaldo", "Sin respaldo"]
        _cs = [R for R in RS if R["cortes"]]
        _ult = {R["sys"]["casa"]: max(R["cortes"], key=lambda c: c["a"]) for R in _cs}
        _por_v = {v: sorted([k for k, c in _ult.items() if c.get("veredicto") == v], key=num_casa) for v in _orden_v}
        tarjetas = ""
        for v in _orden_v:
            casas = _por_v[v]
            niv = _niv[v]
            lista = ", ".join(casas) if casas and len(casas) <= 12 else (f"{len(casas)} casas (ver tabla)" if casas else "ninguna")
            tarjetas += f'<div class="sm-card {niv}"><div class="t"><span class="ic" aria-hidden="true">{_ico[niv]}</span>{esc(v)}</div><div class="v">{len(casas)}</div><small>{esc(lista)}</small></div>'
        # línea de tiempo por casa: una barra por corte, coloreada según su veredicto
        X0, PW, RH = 96, 880, 17
        filas = sorted(_cs, key=lambda R: (ordenar_ciudad(R["sys"]["ciudad"]), num_casa(R["sys"]["casa"])))
        span = max(1, W1 - W0)
        xt = lambda t: X0 + (min(max(t, W0), W1) - W0) / span * PW
        svg = []
        y = 26
        h_svg = 26 + len(filas) * RH + len({R["sys"]["ciudad"] for R in filas}) * 18 + 22
        # rejilla de horas cada 3 h (referida a la hora local de Bogotá)
        paso_g = 3600000 if span <= 18 * 3600000 else 3 * 3600000   # ventana corta (reporte del día): una línea por hora
        t_h = W0 - (W0 + 5 * 3600000) % paso_g + paso_g
        while t_h < W1:
            x = xt(t_h)
            svg.append(f'<line class="grid" x1="{x:.1f}" y1="16" x2="{x:.1f}" y2="{h_svg - 20}"/><text class="ax" x="{x:.1f}" y="11" text-anchor="middle">{hb(t_h)}</text>')
            t_h += paso_g
        ciu_ant = None
        for R in filas:
            s = R["sys"]
            if s["ciudad"] != ciu_ant:
                ciu_ant = s["ciudad"]
                svg.append(f'<text class="lbl" x="4" y="{y + 11}">{esc(ciu_ant.title())}</text>')
                y += 18
            svg.append(f'<text class="sm" x="{X0 - 8}" y="{y + 11}" text-anchor="end">{esc(s["casa"])}</text><line class="lane" x1="{X0}" y1="{y + RH - 1}" x2="{X0 + PW}" y2="{y + RH - 1}"/>')
            for c in R["cortes"]:
                b = c["b"] if c["b"] is not None else W1
                if b < W0 or c["a"] > W1:
                    continue
                x1, x2 = xt(c["a"]), xt(b)
                w = max(4.0, x2 - x1)
                # SOC al inicio del corte; si no hay dato, el último dato registrado de la casa (se marca con «último dato»)
                soc_i, soc_nota = c.get("soc0"), ""
                if soc_i is None:
                    prev_s = [(t_, v_) for t_, v_ in (R.get("soc") or []) if v_ is not None and t_ <= c["a"]]
                    if prev_s:
                        soc_i, soc_nota = prev_s[-1][1], f" (último dato registrado, {hb(prev_s[-1][0])})"
                    elif R.get("soc_ult"):
                        soc_i, soc_nota = R["soc_ult"][1], f" (último dato registrado, {hb(R['soc_ult'][0])})"
                soc_txt_c = f'SOC al inicio {soc_i:.0f} %{soc_nota}' if soc_i is not None else "SOC sin dato"
                tip = f'{s["casa"]} · {hb(c["a"])}–{"en curso" if c["b"] is None else hb(c["b"])} · sin red {fmt(c["dur"] or 0)} · la casa vio {fmt(c["perc"]) if c.get("perc") else "0 s"} · respaldo {dec(c["cob"], 1) + " %" if c.get("cob") is not None else "—"} · {soc_txt_c} · {c.get("veredicto") or ""}'
                etiqueta = f'<text class="soc-t" x="{x1 + 4:.1f}" y="{y + 12}">SOC {soc_i:.0f}%{"*" if soc_nota else ""}</text>' if (soc_i is not None and (c["dur"] or 0) >= 300 and w >= 52) else ""
                # barra combinada: toda la barra es el tiempo sin red (verde = respaldado); en rojo, los tramos que vio el cliente (huecos de tensión)
                rojos = ""
                for h in c.get("hu") or []:
                    hu_fin = h["b"] if h.get("b") else h["a"] + int(h["d"] * 1000)
                    if hu_fin < W0 or h["a"] > W1:
                        continue
                    hx1, hx2 = xt(h["a"]), xt(hu_fin)
                    rojos += f'<rect class="tl c" x="{hx1:.1f}" y="{y + 2}" width="{max(2.0, hx2 - hx1):.1f}" height="{RH - 5}"/>'
                svg.append(f'<g class="tg"><title>{esc(tip)}</title><rect class="tl g" x="{x1:.1f}" y="{y + 2}" width="{w:.1f}" height="{RH - 5}" rx="2"/>{rojos}{etiqueta}</g>')
            y += RH
        linea_t = f'<div class="scroll"><svg viewBox="0 0 {X0 + PW + 8} {h_svg}" role="img" aria-label="Cortes de red por casa en la ventana, coloreados por veredicto de respaldo" style="min-width:760px">{"".join(svg)}</svg></div>'
        leyenda_t = '<div class="legend"><span><i class="lg g"></i>✓ Tiempo respaldado (la casa tuvo tensión)</span><span><i class="lg c"></i>✕ Tiempo que vio el cliente (sin tensión)</span><span>la barra completa es el tiempo total sin red</span><span>SOC = carga de la batería al inicio del corte (cortes de 5 min o más; * = último dato registrado)</span></div>'
        # baterías: SOC actual de los sistemas por debajo de 50 %, con la reserva marcada
        TODOS_V = list(RS) + list(RB)
        socs = sorted(((R["sys"]["casa"], R["soc_ult"][1]) for R in TODOS_V if R["soc_ult"]), key=lambda x: x[1])
        bajos = [(k, v) for k, v in socs if v <= 50]
        filas_s = "".join(
            f'<div class="soc-row"><span class="sn">{esc(k)}</span><div class="soc"><div class="track"><i class="{"crit" if v <= RESERVA else "warn"}" style="width:{max(v, 1):.0f}%"></i><b style="left:{RESERVA:.0f}%" title="reserva {RESERVA:.0f} %"></b></div><span class="num">{v:.0f} %</span></div></div>'
            for k, v in bajos)
        n_res = sum(1 for k, v in socs if v <= RESERVA)
        bloque_soc = f'<div class="soc-grid">{filas_s}</div><div class="legend"><span><i class="lg c"></i>en reserva (≤ {RESERVA:.0f} %)</span><span><i class="lg w"></i>entre {RESERVA:.0f} y 50 %</span><span>la marca vertical es la reserva</span><span>{len(socs) - len(bajos)} sistemas por encima de 50 % no se dibujan</span></div>' if bajos else "<p class=\"note\">Todos los sistemas tienen más de 50 % de batería.</p>"
        # yield frente al patrón de su región
        pts = [(R, R["ratio"]) for R in RS if R.get("ratio") is not None]
        lan = [c for c in ciudades if any(R["sys"]["ciudad"] == c for R, _ in pts)]
        XY0, PY, LH = 96, 840, 40
        sy = []
        escx = lambda r: XY0 + min(max(r, 0), 1.6) / 1.6 * PY
        for tick in (0, .25, .5, .75, 1.0, 1.25, 1.5):
            x = escx(tick)
            cls = "pat" if tick == 1.0 else ("lim" if tick == .75 else "grid")
            sy.append(f'<line class="{cls}" x1="{x:.1f}" y1="14" x2="{x:.1f}" y2="{14 + len(lan) * LH}"/><text class="ax" x="{x:.1f}" y="{14 + len(lan) * LH + 14}" text-anchor="middle">{tick * 100:.0f} %</text>')
        for i, c in enumerate(lan):
            yy = 14 + i * LH
            sy.append(f'<text class="lbl" x="4" y="{yy + 24}">{esc(c.title())}</text><line class="lane" x1="{XY0}" y1="{yy + LH}" x2="{XY0 + PY}" y2="{yy + LH}"/>')
            grp = sorted([(R, r) for R, r in pts if R["sys"]["ciudad"] == c], key=lambda x: x[1])
            for j, (R, r) in enumerate(grp):
                niv = "w" if r < 0.75 else "ok"
                tip = f'{R["sys"]["casa"]} · yield {dec(R["sy_anual"], 0)} kWh/kWp·año · {dec(100 * r, 0)} % del patrón' + (f' · {R["flag"][1]}' if R["flag"] else "")
                sy.append(f'<circle class="yd {niv}" cx="{escx(r):.1f}" cy="{yy + 14 + (j % 3) * 8}" r="5"><title>{esc(tip)}</title></circle>')
        n_baj = sum(1 for _, r in pts if r < 0.75)
        grafico_y = f'<div class="scroll"><svg viewBox="0 0 {XY0 + PY + 20} {14 + len(lan) * LH + 22}" role="img" aria-label="Yield proyectado de cada casa frente al patrón de su región" style="min-width:720px">{"".join(sy)}</svg></div><div class="legend"><span><i class="dotl ok"></i>≥ 75 % del patrón</span><span><i class="dotl w"></i>▲ por debajo de 75 % ({n_baj} sistemas)</span><span>línea continua: 100 % del patrón de su región · punteada: 75 %</span></div>'
        # tarjetas por ciudad, con el color de la peor situación de la ciudad
        _prio = {"g": 0, "w": 1, "c": 2}
        tarj_c = ""
        for c in ciudades:
            g = [R for R in RS if R["sys"]["ciudad"] == c]
            con = [R for R in g if R["cortes"]]
            peor = "g"
            for R in con:
                v = _niv.get(_ult[R["sys"]["casa"]].get("veredicto"), "g")
                if _prio[v] > _prio[peor]:
                    peor = v
            if any(R["en_curso"] for R in g):
                peor = "c"
            gen_c = sum(R["pv_tot"] for R in g if R["pv_tot"] is not None)
            ok_c = [R for R in g if R["cons_cli"] and R["cons_cli"] > 0 and R["pv_tot"] is not None]
            cob_c = 100 * sum(R["pv_tot"] for R in ok_c) / sum(R["cons_cli"] for R in ok_c) if ok_c else None
            cy_c = [R for R in g if R["pv_tot"] is not None and cap_ok(R)]
            y_c = sum(R["pv_tot"] for R in cy_c) / ndias / sum(R["sys"]["cap"] for R in cy_c) * 365 if cy_c else None
            pat_c = patron_yield(c)
            res_c = sum(1 for R in list(g) + [Q for Q in RB if Q["sys"]["ciudad"] == c] if R["soc_ult"] and R["soc_ult"][1] <= RESERVA)
            ico = _ico[peor]
            tarj_c += (f'<div class="sm-card {peor}"><div class="t"><span class="ic" aria-hidden="true">{ico}</span>{esc(c.title())}</div>'
                       f'<div class="v">{len(con)}<span class="de"> de {len(g)}</span></div><small>sistemas con cortes</small>'
                       f'<div class="kv"><span>Generación</span><b>{dec(gen_c, 0)} kWh</b></div>'
                       f'<div class="kv"><span>Cobertura solar</span><b>{dec(cob_c, 0) + " %" if cob_c is not None else "—"}</b></div>'
                       f'<div class="kv"><span>Yield vs patrón</span><b>{dec(100 * y_c / pat_c, 0) + " %" if (y_c and pat_c) else "—"}</b></div>'
                       f'<div class="kv"><span>Baterías en reserva</span><b>{res_c}</b></div></div>')
        # generación frente a consumo del cliente, por ciudad (un solo eje: kWh)
        filas_g = []
        for c in ciudades + [None]:
            g = [R for R in RS if c is None or R["sys"]["ciudad"] == c]
            ok_c = [R for R in g if R["cons_cli"] and R["cons_cli"] > 0 and R["pv_tot"] is not None]
            if ok_c:
                filas_g.append(("Portafolio Sunny" if c is None else c.title(), sum(R["pv_tot"] for R in ok_c), sum(R["cons_cli"] for R in ok_c)))
        mx = max([max(a, b) for _, a, b in filas_g] or [1])
        GX, GW, GH = 130, 600, 50
        sg = []
        for i, (nom, a, b) in enumerate(filas_g):
            yy = 8 + i * GH
            wa, wb = a / mx * GW, b / mx * GW
            sg.append(f'<text class="lbl" x="4" y="{yy + 24}">{esc(nom)}</text>'
                      f'<rect class="gb gen" x="{GX}" y="{yy + 4}" width="{max(wa, 2):.1f}" height="16" rx="3"><title>{esc(nom)} · generación FV {dec(a, 0)} kWh</title></rect><text class="sm" x="{GX + wa + 6:.1f}" y="{yy + 17}">{dec(a, 0)} kWh</text>'
                      f'<rect class="gb con" x="{GX}" y="{yy + 24}" width="{max(wb, 2):.1f}" height="16" rx="3"><title>{esc(nom)} · consumo de los clientes {dec(b, 0)} kWh</title></rect><text class="sm" x="{GX + wb + 6:.1f}" y="{yy + 37}">{dec(b, 0)} kWh</text>'
                      f'<text class="lbl" x="{GX + GW + 150}" y="{yy + 28}" text-anchor="end">{dec(100 * a / b, 0)} %</text>')
        sg.append(f'<text class="ax" x="{GX + GW + 150}" y="{6}" text-anchor="end">cobertura</text>')
        grafico_gc = f'<div class="scroll"><svg viewBox="0 0 {GX + GW + 160} {16 + len(filas_g) * GH}" role="img" aria-label="Generación FV frente al consumo de los clientes por ciudad" style="min-width:720px">{"".join(sg)}</svg></div><div class="legend"><span><i class="lg gen"></i>Generación FV (balance de medidores)</span><span><i class="lg con"></i>Consumo de los clientes</span><span>cobertura = generación ÷ consumo</span></div>'
        # batería en el corte más largo de cada casa: SOC al inicio → al final (con el mínimo), ordenadas de menor a mayor carga inicial
        dm = []
        for R in _cs:
            cm = max(R["cortes"], key=lambda c: c["dur"] or 0)
            if (cm["dur"] or 0) < 300 or cm.get("soc0") is None or cm.get("soc1") is None:
                continue
            dm.append((R, cm))
        dm.sort(key=lambda x: (x[1]["soc0"], num_casa(x[0]["sys"]["casa"])))
        DX0, DW, DH = 90, 700, 19
        sd_ = []
        dx = lambda v: DX0 + min(max(v, 0), 100) / 100 * DW
        for v in (0, 20, 40, 60, 80, 100):
            cls = "lim" if v == RESERVA else "grid"
            sd_.append(f'<line class="{cls}" x1="{dx(v):.1f}" y1="14" x2="{dx(v):.1f}" y2="{14 + len(dm) * DH}"/><text class="ax" x="{dx(v):.1f}" y="{14 + len(dm) * DH + 14}" text-anchor="middle">{v} %</text>')
        for i, (R, cm) in enumerate(dm):
            yy = 14 + i * DH + DH / 2
            s0, s1, smin = cm["soc0"], cm["soc1"], cm.get("socmin")
            en_res = smin is not None and smin <= RESERVA
            tip = f'{R["sys"]["casa"]} · corte {hb(cm["a"])}–{"en curso" if cm["b"] is None else hb(cm["b"])} ({fmt(cm["dur"] or 0)}) · SOC al inicio {s0:.0f} % · mínimo {smin:.0f} % · al final {s1:.0f} %' if smin is not None else f'{R["sys"]["casa"]} · SOC al inicio {s0:.0f} % · al final {s1:.0f} %'
            sd_.append(f'<g class="dm"><title>{esc(tip)}</title><text class="sm" x="{DX0 - 8}" y="{yy + 4:.1f}" text-anchor="end">{esc(R["sys"]["casa"])}</text>'
                       f'<rect class="hit" x="0" y="{yy - DH / 2:.1f}" width="{DX0 + DW + 120}" height="{DH}"/>'
                       f'<line class="dl2{" r" if en_res else ""}" x1="{dx(s0):.1f}" y1="{yy:.1f}" x2="{dx(s1):.1f}" y2="{yy:.1f}"/>'
                       + (f'<line class="mn{" r" if en_res else ""}" x1="{dx(smin):.1f}" y1="{yy - 5:.1f}" x2="{dx(smin):.1f}" y2="{yy + 5:.1f}"/>' if smin is not None else "")
                       + f'<circle class="d0" cx="{dx(s0):.1f}" cy="{yy:.1f}" r="4.5"/><circle class="d1{" r" if en_res else ""}" cx="{dx(s1):.1f}" cy="{yy:.1f}" r="4.5"/>'
                       f'<text class="soc-n" x="{DX0 + DW + 12}" y="{yy + 4:.1f}">{s0:.0f} → {s1:.0f} %</text></g>')
        n_baja = sum(1 for R, cm in dm if cm.get("socmin") is not None and cm["socmin"] <= RESERVA)
        n_baja_txt = _pl(n_baja, "casa", "casas")
        grafico_soc = f'<div class="scroll"><svg viewBox="0 0 {DX0 + DW + 110} {14 + len(dm) * DH + 22}" role="img" aria-label="Carga de la batería al inicio y al final del corte más largo de cada casa" style="min-width:720px">{"".join(sd_)}</svg></div><div class="legend"><span><i class="dotl hueco"></i>SOC al inicio del corte</span><span><i class="dotl ok"></i>SOC al final</span><span><i class="lg marca"></i>mínimo durante el corte</span><span><i class="lg c"></i>llegó a la reserva ({n_baja_txt})</span><span>línea punteada: reserva {RESERVA:.0f} %</span></div><p class="note">Se dibuja el corte más largo de cada casa entre los de 5 min o más ({len(dm)} casas), ordenadas de menor a mayor carga al inicio. Pasa el cursor sobre una fila para ver el detalle.</p>'
        # cuánto vio la casa en cada corte
        from collections import Counter as _Ctr
        todos_cc = [(R["sys"]["casa"], c) for R in _cs for c in R["cortes"]]
        todos_c = [c for _, c in todos_cc]
        bins = [("Sin hueco", lambda p: not p), ("Menos de 30 s", lambda p: 0 < p < 30), ("30 s a 2 min", lambda p: 30 <= p < 120), ("2 a 5 min", lambda p: 120 <= p < 300), ("5 min o más", lambda p: p >= 300)]
        cnt = [sum(1 for c in todos_c if f(c.get("perc") or 0)) for _, f in bins]
        casas_b = []
        for _, f in bins:
            ct = _Ctr(k for k, c in todos_cc if f(c.get("perc") or 0))
            casas_b.append(", ".join(f"{k}" + (f" ×{n}" if n > 1 else "") for k, n in sorted(ct.items(), key=lambda kv: num_casa(kv[0]))))
        mc = max(cnt or [1]) or 1
        sh = []
        for i, ((nom, _), n) in enumerate(zip(bins, cnt)):
            yy = 6 + i * 28
            niv = "g" if i == 0 else ("a" if i < 3 else ("w" if i == 3 else "c"))
            tip_b = f"{nom}: {n} cortes · " + (casas_b[i] if casas_b[i] else "ninguna casa")
            sh.append(f'<g class="hg"><title>{esc(tip_b)}</title><rect class="hitb" x="0" y="{yy}" width="780" height="24"/><text class="sm" x="4" y="{yy + 15}">{nom}</text><rect class="hb {niv}" x="110" y="{yy + 2}" width="{max(n / mc * 640, 2):.1f}" height="18" rx="3"/><text class="lbl" x="{110 + max(n / mc * 640, 2) + 8:.1f}" y="{yy + 16}">{n}</text></g>')
        grafico_h = f'<div class="scroll"><svg viewBox="0 0 800 {12 + len(bins) * 28}" role="img" aria-label="Cantidad de cortes según el tiempo que la casa vio la interrupción" style="min-width:560px">{"".join(sh)}</svg></div><p class="note">Cada corte cuenta una vez ({len(todos_c)} en total); pasa el cursor sobre una barra para ver qué casas son. «Tiempo que vio la casa» = suma de los huecos de tensión del medidor solar en ese corte.</p>'
        # ---- cortes por hora del día: cuántas casas perdieron la red en cada hora de la ventana
        n_h = int(round((W1 - W0) / 3600000))
        por_hora = [[] for _ in range(n_h)]
        for R in _cs:
            vistos_h = set()
            for c in R["cortes"]:
                i_h = int((c["a"] - W0) // 3600000)
                if 0 <= i_h < n_h and i_h not in vistos_h:
                    vistos_h.add(i_h)
                    por_hora[i_h].append(R["sys"]["casa"])
        mx_h = max([len(x) for x in por_hora] or [1]) or 1
        HX0, HW, HH = 30, 840, 130
        bw = HW / max(n_h, 1)
        sph = []
        for k in (0, mx_h // 2, mx_h):
            yk = 10 + HH - k / mx_h * HH
            sph.append(f'<line class="grid" x1="{HX0}" y1="{yk:.1f}" x2="{HX0 + HW}" y2="{yk:.1f}"/><text class="ax" x="{HX0 - 6}" y="{yk + 4:.1f}" text-anchor="end">{k}</text>')
        for i_h, casas_h in enumerate(por_hora):
            t_i = W0 + i_h * 3600000
            x = HX0 + i_h * bw
            alto = len(casas_h) / mx_h * HH
            lista_h = ", ".join(sorted(casas_h, key=num_casa)) if casas_h else "ninguna"
            niv_h = "c" if len(casas_h) >= 10 else ("w" if len(casas_h) >= 3 else "a")
            sph.append(f'<g class="hg"><title>{hb(t_i)}–{hb(t_i + 3600000)} · {_pl(len(casas_h), "casa", "casas")} · {esc(lista_h)}</title><rect class="hitb" x="{x:.1f}" y="10" width="{bw:.1f}" height="{HH + 18}"/>'
                       + (f'<rect class="hb {niv_h}" x="{x + 2:.1f}" y="{10 + HH - alto:.1f}" width="{max(bw - 4, 2):.1f}" height="{max(alto, 0):.1f}" rx="2"/><text class="lbl" x="{x + bw / 2:.1f}" y="{10 + HH - alto - 4:.1f}" text-anchor="middle">{len(casas_h)}</text>' if casas_h else "")
                       + (f'<text class="ax" x="{x + bw / 2:.1f}" y="{HH + 26}" text-anchor="middle">{hb(t_i)[:2]}</text>' if True else "") + '</g>')
        grafico_ph = f'<div class="scroll"><svg viewBox="0 0 {HX0 + HW + 10} {HH + 50}" role="img" aria-label="Casas que perdieron la red en cada hora de la ventana" style="min-width:720px"><g transform="translate(0,14)">{"".join(sph)}</g></svg></div><div class="legend"><span><i class="lg c"></i>10 casas o más</span><span><i class="lg w"></i>3 a 9 casas</span><span><i class="lg a"></i>1 o 2 casas</span><span>eje horizontal: hora local de inicio del corte; pasa el cursor para ver las casas</span></div>'
        # ---- mapa de calor: casas × eventos de red (% de respaldo del corte de la casa en cada evento)
        evs = sorted([e for e in EV if e["n"] >= 3], key=lambda e: e["ini"])
        casas_hm = sorted({id(R): R for e in evs for R, _ in e["m"]}.values(), key=lambda R: (ordenar_ciudad(R["sys"]["ciudad"]), num_casa(R["sys"]["casa"])))
        grafico_hm = ""
        if evs and casas_hm:
            CWc, CHc, LX, TY = 62, 19, 92, 40
            shm = []
            for j, e in enumerate(evs):
                x = LX + j * CWc
                shm.append(f'<text class="ax" x="{x + CWc / 2:.1f}" y="14" text-anchor="middle">{esc("B/quilla" if e["ciudad"].upper().startswith("BARRANQ") else e["ciudad"].title()[:9])}</text><text class="ax" x="{x + CWc / 2:.1f}" y="27" text-anchor="middle">{hb(e["ini"])}</text>')
            for i, R in enumerate(casas_hm):
                yy = TY + i * CHc
                shm.append(f'<text class="sm" x="{LX - 8}" y="{yy + 14}" text-anchor="end">{esc(R["sys"]["casa"])}</text>')
                for j, e in enumerate(evs):
                    mis = [c for Rm, c in e["m"] if Rm is R]
                    x = LX + j * CWc
                    if not mis:
                        shm.append(f'<rect class="hm n" x="{x + 1}" y="{yy + 1}" width="{CWc - 2}" height="{CHc - 2}" rx="2"/>')
                        continue
                    cobs_ = [c["cob"] for c in mis if c.get("cob") is not None]
                    v = min(cobs_) if cobs_ else None
                    niv = "n" if v is None else ("g" if v >= 99 else ("w" if v >= 90 else "c"))
                    vio_ = sum(c.get("perc") or 0 for c in mis)
                    tip = f'{R["sys"]["casa"]} · {e["ciudad"].title()} {hb(e["ini"])} · respaldo {dec(v, 1) + " %" if v is not None else "sin dato"} · la casa vio {fmt(vio_) if vio_ else "0 s"}'
                    shm.append(f'<g><title>{esc(tip)}</title><rect class="hm {niv}" x="{x + 1}" y="{yy + 1}" width="{CWc - 2}" height="{CHc - 2}" rx="2"/><text class="hmt {niv}" x="{x + CWc / 2:.1f}" y="{yy + 14}" text-anchor="middle">{(dec(v, 1) if 97 <= v < 100 else dec(v, 0)) if v is not None else "—"}</text></g>')
            grafico_hm = f'<div class="scroll"><svg viewBox="0 0 {LX + len(evs) * CWc + 8} {TY + len(casas_hm) * CHc + 6}" role="img" aria-label="Porcentaje de respaldo de cada casa en cada evento de red" style="width:{LX + len(evs) * CWc + 8}px;max-width:none">{"".join(shm)}</svg></div><div class="legend"><span><i class="lg g"></i>✓ 99 % o más</span><span><i class="lg w"></i>▲ 90 a 99 %</span><span><i class="lg c"></i>✕ menos de 90 %</span><span><i class="lg vacia"></i>la casa no tuvo ese corte</span><span>cada celda es el % de respaldo del corte; solo eventos con 3 casas o más</span></div>'
        # ---- hora en que la batería llegó a 99 % (producción limitada)
        d_ult = dias[-1][0]
        pts5 = sorted(((R, R["lleno"].get(d_ult)) for R in RS if R.get("lleno") and R["lleno"].get(d_ult) is not None), key=lambda x: x[1])
        n_no_llena = len(RS) - len(pts5)
        LXX, LW5, LH5 = 92, 760, 17
        hrs0, hrs1 = 6, 18
        xh = lambda t: LXX + (min(max((fecha_bog(t).hour + fecha_bog(t).minute / 60) - hrs0, 0), hrs1 - hrs0)) / (hrs1 - hrs0) * LW5
        s5 = []
        for h_ in range(hrs0, hrs1 + 1, 2):
            xg = LXX + (h_ - hrs0) / (hrs1 - hrs0) * LW5
            s5.append(f'<line class="grid" x1="{xg:.1f}" y1="14" x2="{xg:.1f}" y2="{14 + len(pts5) * LH5}"/><text class="ax" x="{xg:.1f}" y="{14 + len(pts5) * LH5 + 14}" text-anchor="middle">{h_:02d}:00</text>')
        xl = LXX + (LLENO_ANTES_H - hrs0) / (hrs1 - hrs0) * LW5
        s5.append(f'<line class="lim" x1="{xl:.1f}" y1="14" x2="{xl:.1f}" y2="{14 + len(pts5) * LH5}"/>')
        for i, (R, t) in enumerate(pts5):
            yy = 14 + i * LH5 + LH5 / 2
            hh_ = fecha_bog(t).hour
            niv = "w" if hh_ < LLENO_ANTES_H else ("t" if hh_ < LLENO_TARDE_H else "ok")
            tip = f'{R["sys"]["casa"]} · batería a {BATERIA_LLENA_SOC} % a las {hb(t)}' + (" · producción limitada" if niv == "w" else (" · producción limitada en la tarde" if niv == "t" else ""))
            s5.append(f'<g class="dm"><title>{esc(tip)}</title><text class="sm" x="{LXX - 8}" y="{yy + 4:.1f}" text-anchor="end">{esc(R["sys"]["casa"])}</text><line class="lane" x1="{LXX}" y1="{yy + LH5 / 2:.1f}" x2="{LXX + LW5}" y2="{yy + LH5 / 2:.1f}"/><circle class="yd {niv}" cx="{xh(t):.1f}" cy="{yy:.1f}" r="5"/><text class="soc-n" x="{xh(t) + 9:.1f}" y="{yy + 4:.1f}">{hb(t)}</text></g>')
        grafico_ll = f'<div class="scroll"><svg viewBox="0 0 {LXX + LW5 + 10} {14 + len(pts5) * LH5 + 22}" role="img" aria-label="Hora en que la batería de cada casa llegó a carga completa" style="min-width:720px">{"".join(s5)}</svg></div><div class="legend"><span><i class="dotl w"></i>▲ antes de las {LLENO_ANTES_H}:00 (pierde producción)</span><span><i class="dotl t"></i>entre las {LLENO_ANTES_H}:00 y las {LLENO_TARDE_H}:00</span><span><i class="dotl ok"></i>después de las {LLENO_TARDE_H}:00</span><span>línea punteada: las {LLENO_ANTES_H}:00 · {_pl(n_no_llena, "sistema", "sistemas")} no llegó a {BATERIA_LLENA_SOC} %</span></div>' if pts5 else ""
        # ---- dispersión: generación del día frente a potencia instalada (kWp), con las líneas del yield patrón
        p4 = [R for R in RS if cap_ok(R) and R["pv_tot"] is not None]
        grafico_dp = ""
        if p4:
            SX0, SW, SH = 54, 800, 280
            mxx = max(R["sys"]["cap"] for R in p4) * 1.08
            mxy = max(max(R["pv_tot"] for R in p4), max(mxx * YIELD_PATRON["COSTA"] / 365 * ndias, 1)) * 1.05
            sx = lambda v: SX0 + v / mxx * SW
            sy_ = lambda v: 10 + SH - v / mxy * SH
            s4 = []
            for k in range(0, int(mxx) + 1, 2):
                s4.append(f'<line class="grid" x1="{sx(k):.1f}" y1="10" x2="{sx(k):.1f}" y2="{10 + SH}"/><text class="ax" x="{sx(k):.1f}" y="{SH + 26}" text-anchor="middle">{k}</text>')
            for k in range(0, int(mxy) + 1, 10):
                s4.append(f'<line class="grid" x1="{SX0}" y1="{sy_(k):.1f}" x2="{SX0 + SW}" y2="{sy_(k):.1f}"/><text class="ax" x="{SX0 - 6}" y="{sy_(k) + 4:.1f}" text-anchor="end">{k}</text>')
            for nom, pat in (("Costa", YIELD_PATRON["COSTA"]), ("Cali", YIELD_PATRON["CALI"])):
                yy2 = mxx * pat / 365 * ndias
                s4.append(f'<line class="pat" x1="{sx(0):.1f}" y1="{sy_(0):.1f}" x2="{sx(mxx):.1f}" y2="{sy_(yy2):.1f}"/><text class="lbl" x="{sx(mxx) - 4:.1f}" y="{sy_(yy2) + (-6 if nom == "Costa" else 16):.1f}" text-anchor="end">patrón {nom} ({pat})</text>')
            for R in p4:
                r_ = R.get("ratio")
                niv = "w" if (r_ is not None and r_ < 0.75) else "ok"
                tip = f'{R["sys"]["casa"]} · {dec(R["sys"]["cap"], 2)} kWp · generó {dec(R["pv_tot"], 1)} kWh · yield {dec(R["sy_anual"], 0) if R["sy_anual"] is not None else "—"} · {dec(100 * r_, 0) + " % del patrón" if r_ is not None else ""}'
                s4.append(f'<circle class="yd {niv}" cx="{sx(R["sys"]["cap"]):.1f}" cy="{sy_(R["pv_tot"]):.1f}" r="5"><title>{esc(tip)}</title></circle>')
            grafico_dp = f'<div class="scroll"><svg viewBox="0 0 {SX0 + SW + 10} {SH + 52}" role="img" aria-label="Generación del día frente a la potencia instalada de cada casa" style="min-width:720px">{"".join(s4)}<text class="ax" x="{SX0 + SW / 2:.1f}" y="{SH + 46}" text-anchor="middle">potencia instalada (kWp)</text><text class="ax" x="12" y="{10 + SH / 2:.1f}" text-anchor="middle" transform="rotate(-90 12 {10 + SH / 2:.1f})">generación del día (kWh)</text></svg></div><div class="legend"><span><i class="dotl ok"></i>≥ 75 % del patrón</span><span><i class="dotl w"></i>▲ por debajo de 75 %</span><span>las líneas son la generación esperada con el yield patrón de cada región (kWp × patrón ÷ 365)</span></div>'
        # ---- ranking de las casas por energía exportada a la red (energyAE del medidor de red, en la ventana del reporte)
        rk = sorted([R for R in RS if R["exp"].get("total") is not None], key=lambda R: (-R["exp"]["total"], num_casa(R["sys"]["casa"])))
        grafico_rk = ""
        if rk:
            KX0, KW, KH = 116, 620, 17
            mxk = max(R["exp"]["total"] for R in rk) or 0.01
            fk, uk, dk = 1, "kWh", 2      # siempre en kWh (decisión del usuario: en Wh generaba mucho ruido)
            kx = lambda v: KX0 + v / mxk * KW
            sk = []
            for fr in (0, .25, .5, .75, 1.0):
                sk.append(f'<line class="grid" x1="{kx(mxk * fr):.1f}" y1="10" x2="{kx(mxk * fr):.1f}" y2="{10 + len(rk) * KH}"/><text class="ax" x="{kx(mxk * fr):.1f}" y="{10 + len(rk) * KH + 14}" text-anchor="middle">{dec(mxk * fr * fk, dk)}</text>')
            for i, R in enumerate(rk):
                yy = 10 + i * KH
                ex_k = R["exp"]["total"]; imp_k = R["imp"].get("total")
                tip = (f'#{i + 1} {R["sys"]["casa"]} · exportada {dec(ex_k * fk, dk)} {uk} (' + dec(ex_k, 3) + ' kWh)' + (f' · importada {dec(imp_k, 1)} kWh' if imp_k is not None else "")
                       + (f' · generó {dec(R["pv_tot"], 1)} kWh · exportó el {dec(100 * ex_k / R["pv_tot"], 1)} % de lo generado' if R.get("pv_tot") else ""))
                w_k = max(ex_k / mxk * KW, 2) if ex_k > 0 else 0
                barra = f'<rect class="gb gen" x="{KX0}" y="{yy + 2}" width="{w_k:.1f}" height="{KH - 5}" rx="2"/>' if w_k else ""
                sk.append(f'<g class="dm"><title>{esc(tip)}</title><rect class="hit" x="0" y="{yy}" width="{KX0 + KW + 80}" height="{KH}"/><text class="sm" x="{KX0 - 8}" y="{yy + 12}" text-anchor="end">{i + 1}. {esc(R["sys"]["casa"])}</text>{barra}<text class="soc-n" x="{KX0 + w_k + 6:.1f}" y="{yy + 12}">{dec(ex_k * fk, dk)} {uk}</text></g>')
            n_cero = sum(1 for R in rk if R["exp"]["total"] <= 0)
            grafico_rk = f'<div class="scroll"><svg viewBox="0 0 {KX0 + KW + 80} {10 + len(rk) * KH + 22}" role="img" aria-label="Ranking de las casas por energía exportada a la red" style="min-width:720px">{"".join(sk)}</svg></div><div class="legend"><span><i class="lg gen"></i>energía activa exportada a la red en la ventana ({uk})</span><span>{_pl(n_cero, "casa", "casas")} con 0 {uk} exportados</span><span>pasa el cursor para ver importada, generación y % exportado de cada casa</span></div>'
        # ---- reporte de interrupciones: tarjetas por ciudad y línea de tiempo de eventos de red
        tarj_c_int, grafico_ev = "", ""
        if getattr(args, "solo_interrupciones", False):
            _prio = {"g": 0, "w": 1, "c": 2}
            for c in ciudades:
                g = [R for R in RS if R["sys"]["ciudad"] == c]
                con = [R for R in g if R["cortes"]]
                peor = "g"
                for R in con:
                    v = _niv.get(_ult[R["sys"]["casa"]].get("veredicto"), "g")
                    if _prio[v] > _prio[peor]:
                        peor = v
                if any(R["en_curso"] for R in g):
                    peor = "c"
                evs_c = [e for e in EV if e["ciudad"] == c]
                cobs_c = [c_["cob"] for R in con for c_ in R["cortes"] if c_.get("cob") is not None]
                mayor_c = max((e["dur"] or 0 for e in evs_c), default=0)
                res_c = sum(1 for R in list(g) + [Q for Q in RB if Q["sys"]["ciudad"] == c] if R["soc_ult"] and R["soc_ult"][1] <= RESERVA)
                tarj_c_int += (f'<div class="sm-card {peor}"><div class="t"><span class="ic" aria-hidden="true">{_ico[peor]}</span>{esc(c.title())}</div>'
                               f'<div class="v">{len(con)}<span class="de"> de {len(g)}</span></div><small>sistemas con cortes</small>'
                               f'<div class="kv"><span>Cortes · eventos</span><b>{sum(len(R["cortes"]) for R in g)} · {len(evs_c)}</b></div>'
                               f'<div class="kv"><span>Evento más largo</span><b>{fmt(mayor_c) if mayor_c else "—"}</b></div>'
                               f'<div class="kv"><span>Respaldo mediano</span><b>{dec(st.median(cobs_c), 1) + " %" if cobs_c else "—"}</b></div>'
                               f'<div class="kv"><span>Sin red ahora</span><b>{sum(1 for R in g if R["en_curso"])}</b></div>'
                               f'<div class="kv"><span>Baterías en reserva</span><b>{res_c}</b></div></div>')
            evs_g = sorted(EV, key=lambda e: (ordenar_ciudad(e["ciudad"]), e["ini"]))
            if evs_g:
                EX0, EPW, ERH, ETX = 132, 560, 28, 14
                span_e = max(1, W1 - W0)
                xe = lambda t: EX0 + (min(max(t, W0), W1) - W0) / span_e * EPW
                h_ev = 24 + len(evs_g) * ERH + 6
                se = []
                paso_e = 3600000 if span_e <= 18 * 3600000 else 3 * 3600000
                t_h = W0 - (W0 + 5 * 3600000) % paso_e + paso_e
                while t_h < W1:
                    x = xe(t_h)
                    if paso_e > 3600000 or fecha_bog(t_h).hour % 2 == 0:
                        se.append(f'<text class="ax" x="{x:.1f}" y="12" text-anchor="middle">{hb(t_h)}</text>')
                    se.append(f'<line class="grid" x1="{x:.1f}" y1="18" x2="{x:.1f}" y2="{h_ev - 6}"/>')
                    t_h += paso_e
                se.append(f'<text class="ax" x="{EX0 + EPW + ETX}" y="12">afectados · duración típica · peor respaldo</text>')
                for i, e in enumerate(evs_g):
                    yy = 24 + i * ERH
                    mem = e["m"]
                    cobs_e = [(c_["cob"], R_["sys"]["casa"]) for R_, c_ in mem if c_.get("cob") is not None]
                    peor_e = min(cobs_e, default=None)
                    niv_e = "g" if (peor_e is None or peor_e[0] >= 99) else ("w" if peor_e[0] >= 90 else "c")
                    x1, x2 = xe(e["ini"]), xe(e["fin"] if e["fin"] is not None else W1)
                    w_e = max(6.0, x2 - x1)
                    n_tot = n_por_ciudad.get(e["ciudad"], 0)
                    txt_e = f'{e["n"]} de {n_tot} · {fmt(e["dur"]) if e["dur"] else "—"}' + (f' · {dec(peor_e[0], 1)} % ({peor_e[1]})' if peor_e else "")
                    tip_e = (f'{e["ciudad"].title()} · {hbd(e["ini"])}–{"en curso" if e["fin"] is None else hbd(e["fin"])} · {e["n"]} de {n_tot} sistemas · duración típica {fmt(e["dur"]) if e["dur"] else "—"}'
                             + (f' · peor respaldo {dec(peor_e[0], 1)} % ({peor_e[1]})' if peor_e else "")
                             + f' · casas con hueco: {len({id(R_) for R_, c_ in mem if (c_.get("perc") or 0) > 0})}')
                    se.append(f'<g class="tg"><title>{esc(tip_e)}</title><text class="sm" x="{EX0 - 8}" y="{yy + 15}" text-anchor="end">{esc(e["ciudad"].title()[:11])} {hb(e["ini"])}</text>'
                              f'<line class="lane" x1="{EX0}" y1="{yy + ERH - 3}" x2="{EX0 + EPW}" y2="{yy + ERH - 3}"/>'
                              f'<rect class="tl {niv_e}" x="{x1:.1f}" y="{yy + 3}" width="{w_e:.1f}" height="{ERH - 9}" rx="3"/>'
                              f'<text class="soc-n" x="{EX0 + EPW + ETX}" y="{yy + 16}">{esc(txt_e)}</text></g>')
                grafico_ev = (f'<div class="scroll"><svg viewBox="0 0 {EX0 + EPW + ETX + 360} {h_ev}" role="img" aria-label="Eventos de red del día por ciudad y hora" style="min-width:860px">{"".join(se)}</svg></div>'
                              '<div class="legend"><span><i class="lg g"></i>✓ peor casa con 99 % de respaldo o más</span><span><i class="lg w"></i>▲ peor casa entre 90 y 99 %</span><span><i class="lg c"></i>✕ peor casa con menos de 90 %</span>'
                              '<span>cada barra es un evento (varias casas de una ciudad sin red al mismo tiempo); su largo es el tiempo desde el primer corte hasta el último regreso de la red</span></div>')
        sec_vis = f'''<section>
  <h2>Vista rápida</h2>
  <div class="card" style="display:flex;flex-direction:column;gap:18px">
    {('<h3>Semáforo del respaldo (último corte de cada casa)</h3><div class="sema">' + tarjetas + '</div>') if _cs else ''}
    <h3>Por ciudad</h3>
    <div class="sema">{tarj_c}</div>
    {('<h3>Cortes de red en la ventana, por casa</h3>' + linea_t + leyenda_t + '<p class="note">Cada barra es un corte: su largo es el tiempo total sin red, en verde lo que la casa estuvo respaldada y en rojo los tramos en que el cliente vio la interrupción (huecos de tensión del medidor solar). Pasa el cursor para ver la duración, el tiempo que vio la casa, su % de respaldo y el veredicto. Los cortes y huecos de segundos se dibujan con un ancho mínimo para que se vean.</p>') if _cs else ''}
    {('<h3>Respaldo de cada casa en los eventos de red</h3>' + grafico_hm) if grafico_hm else ''}
    {('<h3>Cuánto vio la casa en cada corte</h3>' + grafico_h) if _cs else ''}
    {('<h3>Batería durante el corte más largo de cada casa</h3>' + grafico_soc) if _cs else ''}
    <h3>Baterías por debajo de 50 % al corte del reporte, {hbd(W1)} ({n_res} en reserva)</h3>
    {bloque_soc}
    <h3>Generación frente a consumo de los clientes</h3>
    {grafico_gc}
    {('<h3>Ranking de las casas por energía exportada</h3>' + grafico_rk) if grafico_rk else ''}
    <h3>Yield frente al patrón de su región</h3>
    {grafico_y}
    {('<h3>Hora en que la batería llegó a carga completa</h3>' + grafico_ll) if grafico_ll else ''}
  </div>
</section>'''
    lim_bat = (" Las casas que solo tienen baterías instaladas (" + ", ".join(R["sys"]["casa"] for R in RB) + ") se muestran en su propia tabla y no cuentan en generación, yield, cobertura ni exportación.") if RB else ""
    estado_cls ="warn" if en_curso else ("ok" if True else "")
    estado_txt = (f"{len(en_curso)} sistemas sin red al corte del reporte" if en_curso else ("Sin cortes de red en curso" if True else ""))
    gen = fecha_bog(int(time.time() * 1000))
    pagina = f'''<title>{esc(titulo)} · {gen.strftime('%H:%M')}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
{css}
</style>
<div class="wrap">
<header>
  <div class="kick">{'Fin de semana' if es_lunes else 'Últimas 24 horas'} · {len(ciudades)} ciudades · {n_sys} sistemas</div>
  <h1>{'Operación del fin de semana' if es_lunes else 'Operación de las últimas 24 horas'} <span class="gh">· generado {gen.strftime('%H:%M')}</span></h1>
  <div class="status {estado_cls}"><i></i>{esc(estado_txt)}</div>
  <div class="meta"><span>{esc(h_ini)} a {esc(h_fin)} (UTC−5)</span><span>{horas:.0f} h de operación</span><span>Fuente: telemetría cruda de Metrum</span><span>Generado {gen.strftime('%H:%M')}</span></div>
</header>

<div class="kpis">
  {k_sis}
  {k_res}
  {k_pv}
  {k_yield}
  {k_cob}
  {k_exp}
</div>

{sec_vis}

<section>
  <details><summary>Puntos más relevantes ({len(P)})</summary><div style="margin-top:10px"><ul class="pts">{li}</ul></div></details>
</section>

<section>
  <details><summary>Por ciudad</summary><div style="margin-top:10px">{sec_ciu}</div></details>
</section>

{sec_dia}

<section>
  <h2>Interrupciones y respaldo</h2>
  <div class="card" style="display:flex;flex-direction:column;gap:14px">
    <details><summary>Eventos de red</summary><div style="margin-top:10px">{sec_ev}</div></details>
    {('<details><summary>Por sistema</summary><div style="margin-top:10px">' + sec_sis + '</div></details>') if sec_sis else ''}
    {('<details><summary>' + tit_bat + '</summary><div style="margin-top:10px">' + sec_bat + '</div></details>') if sec_bat else ''}
    {sec_det}
    <p class="note">Corte = intervalo entre los eventos <code>po</code> y <code>pr</code> del medidor de red. «Tiempo que vio la casa» = suma de los huecos de tensión del medidor solar (lado respaldado) asociados al corte, incluidos los del cambio al caer y al volver la red. «Respaldo» = (tiempo sin red del medidor de red − tiempo sin tensión del medidor solar) ÷ tiempo sin red del medidor de red; se calcula en todos los cortes, incluidos los de pocos segundos, y no baja de 0 %. Sin hueco, por criterio del equipo, el cliente no percibió el corte. En «Por sistema» se muestra completo el último corte registrado de cada casa, con su veredicto de respaldo; los anteriores (del más reciente al más antiguo) van solo con su % de respaldo y la hora de inicio, y la duración sale al pasar el cursor. El detalle de todos los cortes está en el desplegable.</p>
  </div>
</section>

<section>
  <details><summary>Rendimiento de los sistemas</summary><div style="margin-top:10px">
    {sec_pv}
    <p class="note" style="margin-top:10px">Generación = balance de medidores con los cierres diarios: demanda del medidor solar (<code>CenergyAI</code>) − importada + exportada del medidor de red. No se usa el contador del inversor. «Yield anual proyectado» es la generación real del día dividida entre la potencia instalada, por 365; en el portafolio Sunny y en cada ciudad, la suma de generación entre la suma de potencia. La potencia instalada es la potencia pico en DC (kWp) del archivo de sistemas, no la del inversor, y no se corrige estacionalidad ni clima. «Frente al yield patrón» es el yield anual proyectado del sistema dividido entre el yield patrón de su región, definido por el equipo: {YIELD_PATRON["CALI"]} kWh/kWp·año en Cali y {YIELD_PATRON["COSTA"]} kWh/kWp·año en la costa (Turbaco, Barranquilla y Cartagena). La alerta «baja vs patrón» aparece por debajo del 75 % del patrón y se completa con «bajo consumo» cuando el consumo del cliente en el día evaluado (demanda del medidor solar) fue menor al {CONSUMO_BAJO * 100:.0f} % del habitual de esa casa, medido como la mediana de sus días previos; en ese caso la baja generación puede deberse a que la casa consumió menos. Se añade «producción limitada» cuando la batería llegó a {BATERIA_LLENA_SOC} % antes de las {LLENO_ANTES_H}:00, y «producción limitada en la tarde» cuando llegó entre las {LLENO_ANTES_H}:00 y las {LLENO_TARDE_H}:00, porque entonces solo se limita parte de la tarde (se indica la hora): en sistemas sin exportación, con la batería llena el inversor limita la producción FV al consumo de la casa, así que el yield mide la energía solar consumida y no la que el sistema podría producir.</p>
  </div></details>
</section>

<section>
  <details><summary>Exportación de energía activa</summary><div style="margin-top:10px">
    {sec_ex}
    <p class="note" style="margin-top:10px">Exportada e importada, del medidor de red (<code>energyAE</code> y <code>energyAI</code>). Consumo del cliente = demanda del día calendario en el medidor solar; cobertura solar = generación / consumo del cliente. La generación es el balance de medidores, así que incluye pérdidas y la energía que pasa por la batería. Cada encabezado indica el periodo de su dato: las columnas por día suman la ventana completa (exportada, importada y consumo del lado respaldado, que se miden entre la hora de inicio y la de corte del reporte), mientras que consumo del cliente, generación y cobertura son de días completos, de 00:00 a 24:00, porque dependen de los cierres diarios de los medidores.</p>
  </div></details>
</section>

<section>
  <details><summary>Comunicación y equipos</summary><div style="margin-top:10px">{sec_com}</div></details>
</section>

<section>
  <h2>Límites del análisis</h2>
  <div class="limits">
    <p>Los medidores de red sin tensión envían sus eventos guardados solo cuando vuelve la red. Un corte en curso se detecta con el inversor (entrada de red por debajo de 5 V) y su hora de inicio es aproximada (≈) hasta que vuelva la red.</p>
    <p>Los relojes de los medidores difieren hasta unos 40 s entre sí. Cada hueco cuenta en un solo corte: el que empieza hasta 75 s de su inicio, si no el que lo contiene, si no el último que terminó hasta 10 min antes.</p>
    <p>Los inversores se muestrean cada 15 min. El SOC de inicio y fin de cada corte es el de la muestra más cercana y la reserva se toma como {RESERVA:.0f} % para todos.</p>
    <p>El lunes, la ventana va desde el viernes a las 07:00 hasta el lunes a las 07:00, para no dejar horas sin cubrir entre reportes.</p>
    <p>Cada sistema es una casa (medidor de red, medidor solar, inversor y gateway). Si una casa tiene dos inversores se usa el que reportó más recientemente.</p>
    <p>Si a un medidor aún no le llegó el cierre diario de las 00:00 (hoy, Casa 9G y Casa 108), su generación del día queda sin calcular y no se reemplaza por otro dato. La generación de todos los sistemas se calcula con el balance de medidores.{lim_bat}</p>
  </div>
</section>
<footer>Cálculo propio sobre telemetría cruda de Metrum. Datos consultados en {time.time() - t_cons:.0f} s.</footer>
</div>
'''
    if getattr(args, "solo_interrupciones", False):
        # reporte exclusivo de interrupciones: desde las 00:00 del día hasta la hora de corte; solo lo relacionado con los cortes de red
        titulo = f"Interrupciones hoy {fin.day} {MESES[fin.month-1]}"
        P_int = [p for p in P if p[1] in ("En curso", "Inversor aislado", "Interrupciones", "Respaldo", "Baterías")]
        li_int = "".join(f'<li>{_pill(PILL[n], t)}<span>{esc(x)}</span></li>' for n, t, x in P_int)
        ult = {id(R): max(R["cortes"], key=lambda c: c["a"]) for R in con_cortes}
        n_ret = sum(1 for R in con_cortes if ult[id(R)].get("veredicto") == "Retardo de transferencia")
        n_caida = sum(1 for R in con_cortes if ult[id(R)].get("veredicto") == "Caída durante el respaldo")
        n_sin = sum(1 for R in con_cortes if ult[id(R)].get("veredicto") == "Sin respaldo")
        n_mal = n_ret + n_caida + n_sin
        k_mal = f'<div class="kpi {"k-warn" if n_mal else "k-ok"}"><div class="v">{n_mal} <small>de {len(con_cortes)}</small></div><div class="l">sistemas con falla de respaldo en su último corte: {n_ret} con retardo de transferencia, {n_caida} con caída durante el respaldo y {n_sin} sin respaldo.</div></div>' if con_cortes else ""
        _mx = max(((R, c) for R in con_cortes for c in R["cortes"] if c.get("perc")), key=lambda x: x[1]["perc"], default=None)
        k_mx = f'<div class="kpi"><div class="v">{fmt(_mx[1]["perc"])}</div><div class="l">fue el mayor tiempo sin tensión que vio una casa en un corte ({esc(_mx[0]["sys"]["casa"])}, corte de las {hb(_mx[1]["a"])}).</div></div>' if _mx else ""
        vis_int = f'''<section>
  <h2>Vista rápida</h2>
  <div class="card" style="display:flex;flex-direction:column;gap:18px">
    {('<h3>Semáforo del respaldo (último corte de cada casa)</h3><div class="sema">' + tarjetas + '</div>') if _cs else ''}
    <h3>Por ciudad</h3>
    <div class="sema">{tarj_c_int}</div>
    {('<h3>Eventos de red del día</h3>' + grafico_ev) if grafico_ev else ''}
    {('<h3>Cortes de red de hoy, por casa</h3>' + linea_t + leyenda_t + '<p class="note">Cada barra es un corte: su largo es el tiempo total sin red, en verde lo que la casa estuvo respaldada y en rojo los tramos en que el cliente vio la interrupción (huecos de tensión del medidor solar). Pasa el cursor para ver la duración, el tiempo que vio la casa, su % de respaldo y el veredicto. Los cortes y huecos de segundos se dibujan con un ancho mínimo para que se vean.</p>') if _cs else ''}
    {('<h3>Respaldo de cada casa en los eventos de red</h3>' + grafico_hm) if grafico_hm else ''}
    {('<h3>Cuánto vio la casa en cada corte</h3>' + grafico_h) if _cs else ''}
    {('<h3>Batería durante el corte más largo de cada casa</h3>' + grafico_soc) if _cs else ''}
    <h3>Baterías por debajo de 50 % al corte del reporte, {hbd(W1)} ({n_res} en reserva)</h3>
    {bloque_soc}
  </div>
</section>''' if VISUAL else ""
        pagina = f'''<title>{esc(titulo)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
{css}
</style>
<div class="wrap">
<header>
  <div class="kick">Hoy, hasta las {fin.strftime('%H:%M')} · {len(ciudades)} ciudades · {n_sys} sistemas</div>
  <h1>Interrupciones de hoy</h1>
  <div class="status {estado_cls}"><i></i>{esc(estado_txt)}</div>
  <div class="meta"><span>{esc(h_ini)} a {esc(h_fin)} (UTC−5)</span><span>Fuente: telemetría cruda de Metrum</span><span>Generado {gen.strftime('%H:%M')}</span></div>
</header>

<div class="kpis">
  {k_sis}
  {k_res}
  {k_mal}
  {k_mx}
</div>

{vis_int}

<section>
  <details><summary>Puntos más relevantes ({len(P_int)})</summary><div style="margin-top:10px"><ul class="pts">{li_int}</ul></div></details>
</section>

<section>
  <h2>Interrupciones y respaldo</h2>
  <div class="card" style="display:flex;flex-direction:column;gap:14px">
    <details><summary>Eventos de red</summary><div style="margin-top:10px">{sec_ev}</div></details>
    {('<details><summary>Por sistema</summary><div style="margin-top:10px">' + sec_sis + '</div></details>') if sec_sis else ''}
    {('<details><summary>' + tit_bat + '</summary><div style="margin-top:10px">' + sec_bat + '</div></details>') if sec_bat else ''}
    {sec_det}
    <p class="note">Corte = intervalo entre los eventos <code>po</code> y <code>pr</code> del medidor de red. «Tiempo que vio la casa» = suma de los huecos de tensión del medidor solar (lado respaldado) asociados al corte, incluidos los del cambio al caer y al volver la red. «Respaldo» = (tiempo sin red del medidor de red − tiempo sin tensión del medidor solar) ÷ tiempo sin red del medidor de red; se calcula en todos los cortes, incluidos los de pocos segundos, y no baja de 0 %. Sin hueco, por criterio del equipo, el cliente no percibió el corte. En «Por sistema» se muestra completo el último corte registrado de cada casa, con su veredicto de respaldo; los anteriores (del más reciente al más antiguo) van solo con su % de respaldo y la hora de inicio, y la duración sale al pasar el cursor. El detalle de todos los cortes está en el desplegable.</p>
  </div>
</section>

<section>
  <h2>Límites del análisis</h2>
  <div class="limits">
    <p>El reporte cubre desde las 00:00 de hoy hasta la hora de corte; no incluye cortes anteriores. Un corte que empezó antes de las 00:00 se cuenta solo desde esa hora.</p>
    <p>Los medidores de red sin tensión envían sus eventos guardados solo cuando vuelve la red. Un corte en curso se detecta con el inversor (entrada de red por debajo de 5 V) y su hora de inicio es aproximada (≈) hasta que vuelva la red.</p>
    <p>Los relojes de los medidores difieren hasta unos 40 s entre sí. Cada hueco cuenta en un solo corte: el que empieza hasta 75 s de su inicio, si no el que lo contiene, si no el último que terminó hasta 10 min antes.</p>
    <p>Los inversores se muestrean cada 15 min. El SOC de inicio y fin de cada corte es el de la muestra más cercana y la reserva se toma como {RESERVA:.0f} % para todos.</p>
    <p>Cada sistema es una casa (medidor de red, medidor solar, inversor y gateway). Si una casa tiene dos inversores se usa el que reportó más recientemente.{lim_bat}</p>
  </div>
</section>
<footer>Cálculo propio sobre telemetría cruda de Metrum. Datos consultados en {time.time() - t_cons:.0f} s.</footer>
</div>
'''
    with open(args.salida, "w", encoding="utf8") as f:
        f.write(pagina)
    resumen = dict(titulo=titulo, ventana=[h_ini, h_fin], es_lunes=es_lunes, sistemas=n_sys, excluidos=[f"{c} · {k}: {m}" for c, k, m in EXCLUIDOS], solo_baterias=[R["sys"]["casa"] for R in RB], con_cortes=len(con_cortes), cortes=total_cortes, eventos=len(EV), en_curso=[R["sys"]["casa"] for R in en_curso],
                   pv_kwh=round(pv_total), yield_anual=round(yield_flota) if yield_flota else None, cobertura_pct=round(cob_flota, 1) if cob_flota is not None else None, exp_kwh=round(exp_tot), imp_kwh=round(imp_tot), puntos=[f"{t}: {x}" for n, t, x in P])
    with open(args.json, "w", encoding="utf8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print(f"escrito {args.salida} ({len(pagina)} caracteres) y {args.json}")
