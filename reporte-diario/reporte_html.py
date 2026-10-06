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
"""


def _kwh(x, n=1):
    return "—" if x is None else dec(x, n)


def _dia(d0):
    d = fecha_bog(d0)
    return f"{DIAS[d.weekday()][:3]} {d.day} {MESES[d.month-1]}"


def _pl(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def _pill(nivel, txt):
    return f'<span class="pill {nivel}">{esc(txt)}</span>'


def generar(RS, W0, W1, ini, fin, es_lunes, dias, args, t_cons):
    css = open(os.path.join(HERE, "estilos.css"), encoding="utf8").read() + EXTRA_CSS
    n_sys = len(RS)
    ciudades = sorted({R["sys"]["ciudad"] for R in RS}, key=ordenar_ciudad)
    ndias = len(dias)
    nombre_dias = [_dia(d0) for d0, _ in dias]
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
    sy = {}      # (ciudad, d0) -> lista de kWh/kW
    for R in RS:
        s = R["sys"]
        if not cap_ok(R):
            continue
        for d0, v in list(R["pv"].items()) + list(R["pv_hist"].items()):
            if v and v > 0:
                sy.setdefault((s["ciudad"], d0), []).append(v / s["cap"])
    med = {k: st.median(v) for k, v in sy.items() if len(v) >= 3}
    for R in RS:
        s = R["sys"]; vs = [v for v in R["pv"].values() if v is not None]
        R["pv_tot"] = sum(vs) if vs else None
        idx = []
        for d0, v in R["pv"].items():
            m = med.get((s["ciudad"], d0))
            if v is not None and cap_ok(R) and m:
                idx.append((v / s["cap"]) / m)
        R["idx"] = st.mean(idx) if idx else None
        hist = []
        for d0, v in R["pv_hist"].items():
            m = med.get((s["ciudad"], d0))
            if v and cap_ok(R) and m:
                hist.append((v / s["cap"]) / m)
        R["idx_base"] = st.median(hist) if len(hist) >= 3 else None
        R["sy"] = (R["pv_tot"] / ndias / s["cap"]) if (R["pv_tot"] is not None and cap_ok(R)) else None
        dd = [v for v in list(R["pv"].values()) + list(R["pv_hist"].values()) if v is not None]
        R["gen_dia_med"] = st.mean(dd) if dd else None
        R["sy_anual"] = (R["pv_tot"] / ndias / s["cap"] * 365) if (R["pv_tot"] is not None and cap_ok(R)) else None
        R["ratio"] = (R["idx"] / R["idx_base"]) if (R["idx"] is not None and R["idx_base"]) else None
        flag = None
        if R["pv_tot"] is None:
            flag = ("off", "sin cierre diario del medidor")
        elif R["pv_tot"] == 0:
            flag = ("crit", "sin producción")
        elif R["ratio"] is not None and R["ratio"] < 0.75:
            flag = ("warn", "baja vs su patrón" + (", con corte" if sum(c["dur"] or 0 for c in R["cortes"]) >= 1800 else ""))
        elif R["idx"] is not None and R["idx"] < 0.5 and (R["idx_base"] or 1) < 0.5:
            flag = ("warn", "baja de forma sostenida")
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
    agot = [(R, c) for R in RS for c in R["cortes"] if c.get("socmin") is not None and c["socmin"] <= RESERVA]
    if agot:
        P.append(("crit", "Baterías", f"{len(set(id(R) for R, _ in agot))} sistemas llegaron a la reserva (SOC de {RESERVA:.0f} % o menos) durante un corte: " + ", ".join(sorted({R['sys']['casa'] for R, _ in agot}, key=num_casa)) + "."))
    # inversores
    fallas = [(R, t, v) for R in RS for t, v in R["est"] if v in ("fault", "alarm")]
    cods = [(R, t, v) for R in RS for t, v in R["codigos"]]
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
    k_exp = f'<div class="kpi"><div class="v">{dec(exp_tot, 0)} <small>kWh</small></div><div class="l">de energía activa exportada a la red; importada {dec(imp_tot, 0)} kWh.</div></div>'
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
    for R in orden_sys:
        s = R["sys"]; cc = R["cortes"]; mayor = max(cc, key=lambda c: c["dur"] or 0)
        tot = sum(c["dur"] or 0 for c in cc); perc = sum(c["perc"] for c in cc)
        cobs = [c["cob"] for c in cc if c["cob"] is not None]
        estado = _pill("crit", "sin red") if R["en_curso"] else ""
        cls = "r0" if R["en_curso"] else ("r1" if perc >= 300 else "")
        _g = {"Caída durante el respaldo": 3, "Sin respaldo": 2, "Respaldo total con transferencia": 1, "Respaldo total": 0}
        cpeor = max(cc, key=lambda c: (_g.get(c.get("veredicto"), 0), c["dur"] or 0))
        vr = cpeor.get("veredicto") or ""
        niv = {"Caída durante el respaldo": "crit", "Sin respaldo": "crit", "Respaldo total con transferencia": "okp", "Respaldo total": "okp"}.get(vr, "off")
        vr_det = " · ".join(x for x in ("alimenta: " + cpeor["fuente"] if cpeor.get("fuente") else "", cpeor.get("causa") or "") if x)
        celda_resp = _pill(niv, vr) + (f"<small>{esc(vr_det)}</small>" if vr_det else "") + ("<small>provisional: el corte sigue abierto</small>" if cpeor.get("abierto") else "")
        rows.append(f'<tr class="{cls}"><td><b>{esc(s["casa"])}</b><small>{esc(s["ciudad"].title())} · {esc(s["marca"].title())} {esc(s["modelo"])}</small></td><td class="n">{len(cc)}</td><td class="n">{fmt(tot)}</td><td class="n">{fmt(mayor["dur"] or 0)}<small>{hbd(mayor["a"])}</small></td><td class="n">{fmt(perc) if perc else "—"}</td><td class="n">{(dec(min(cobs), 1) + " %") if cobs else "—"}</td><td class="n">{soc_uno(mayor.get("soc0"))}</td><td class="n">{soc_uno(mayor.get("soc1"))}</td><td>{estado}</td><td>{celda_resp}</td></tr>')
    sis_head = '<th>Sistema</th><th class="n">Cortes</th><th class="n">Tiempo<br>sin red</th><th class="n">Mayor corte</th><th class="n">Tiempo que<br>vio la casa</th><th class="n">Respaldo<br>peor corte</th><th class="n">SOC al inicio<br>mayor corte</th><th class="n">SOC al final<br>mayor corte</th><th>Ahora</th><th>Veredicto<br>de respaldo</th>'
    sec_sis = tabla(sis_head, rows, 900) if rows else ""
    # detalle por corte
    rows = []
    for R in con_cortes:
        for c in sorted(R["cortes"], key=lambda c: c["a"]):
            fin_c = "en curso" if c["b"] is None else hbd(c["b"])
            rows.append(f'<tr><td><b>{esc(R["sys"]["casa"])}</b><small>{esc(R["sys"]["ciudad"].title())}</small></td><td>{hbd(c["a"])}{"≈" if c.get("estimado") else ""}</td><td>{fin_c}</td><td class="n">{fmt(c["dur"])}</td><td class="n">{fmt(c["caer"]) if c["caer"] else "—"}</td><td class="n">{fmt(c["volver"]) if c["volver"] else "—"}</td><td class="n">{fmt(c["perc"]) if c["perc"] else "—"}</td><td class="n">{(dec(c["cob"], 1) + " %") if c["cob"] is not None else "—"}</td><td class="n">{soc_txt(c)}</td></tr>')
    det_head = '<th>Sistema</th><th>Inicio</th><th>Fin</th><th class="n">Duración</th><th class="n">Hueco<br>al caer</th><th class="n">Hueco<br>al volver</th><th class="n">Total que<br>vio la casa</th><th class="n">Respaldo</th><th class="n">SOC inicio → mín → fin</th>'
    sec_det = f'<details><summary>Detalle por corte ({len(rows)} filas)</summary><div style="margin-top:10px">{tabla(det_head, rows, 900)}</div></details>' if rows else ""

    # rendimiento
    rows = []
    mx_pv = max([R["pv_tot"] for R in RS if R["pv_tot"]] or [1])
    for c in ciudades:
        rows.append(f'<tr class="ciudad"><td colspan="{5 + ndias}">{esc(c.title())}</td></tr>')
        for R in [R for R in RS if R["sys"]["ciudad"] == c]:
            s = R["sys"]
            cols = "".join(f'<td class="n">{_kwh(R["pv"].get(d0))}</td>' for d0, _ in dias)
            fl = _pill({"crit": "crit", "warn": "warn", "off": "off"}[R["flag"][0]], R["flag"][1]) if R["flag"] else ""
            bar = f'<span class="bar {"crit" if R["flag"] and R["flag"][0] == "crit" else ("warn" if R["flag"] and R["flag"][0] == "warn" else "")}" style="width:{max(2, 120 * (R["pv_tot"] or 0) / mx_pv):.0f}px"></span>'
            rows.append(f'<tr><td><b>{esc(s["casa"])}</b><small>{esc(s["marca"].title())} {esc(s["modelo"])} · {dec(s["cap"], 2) if s["cap"] else "—"} kWp</small></td>{cols}<td class="n"><b>{_kwh(R["pv_tot"])}</b></td><td class="n">{dec(R["sy_anual"], 0) if R["sy_anual"] is not None else "—"}</td><td class="n">{(dec(100*R["ratio"], 0) + " %") if R["ratio"] is not None else "—"}</td><td>{fl}{bar if not fl else ""}</td></tr>')
    pv_head = '<th>Sistema</th>' + "".join(f'<th class="n">{esc(n)}<br>kWh</th>' for n in nombre_dias) + '<th class="n">Total<br>kWh</th><th class="n">Yield anual<br>proyectado<br>kWh/kWp·año</th><th class="n">Frente a su<br>patrón</th><th></th>'
    sec_pv = tabla(pv_head, rows, 760 + 60 * ndias)

    # exportación
    rows = []
    ex_max = max([R["exp"]["total"] for R in RS if R["exp"].get("total")] or [1])
    for c in ciudades:
        rows.append(f'<tr class="ciudad"><td colspan="{8 + ndias}">{esc(c.title())}</td></tr>')
        for R in sorted([R for R in RS if R["sys"]["ciudad"] == c], key=lambda R: -(R["exp"].get("total") or 0)):
            s = R["sys"]; t = R["exp"].get("total")
            cols = "".join(f'<td class="n">{_kwh(R["exp"].get(d0), 2)}</td>' for d0, _ in dias)
            share = (100 * t / R["pv_tot"]) if (t is not None and R["pv_tot"]) else None
            rows.append(f'<tr><td><b>{esc(s["casa"])}</b></td>{cols}<td class="n"><b>{_kwh(t, 2)}</b></td><td class="n">{_kwh(R["imp"].get("total"), 1)}</td><td class="n">{_kwh(R["cons"].get("total"), 1)}</td><td class="n">{(dec(share, 1) + " %") if share is not None else "—"}</td><td class="n">{_kwh(R["cons_cli"], 1)}</td><td class="n"><b>{(dec(R["cob_sol"], 0) + " %") if R["cob_sol"] is not None else "—"}</b></td><td><span class="bar" style="width:{max(2, 120 * (t or 0) / ex_max):.0f}px"></span></td></tr>')
    ex_head = '<th>Sistema</th>' + "".join(f'<th class="n">{esc(n)}<br>kWh</th>' for n in nombre_dias) + '<th class="n">Exportada<br>kWh</th><th class="n">Importada<br>kWh</th><th class="n">Consumo lado<br>respaldado kWh</th><th class="n">Exportada /<br>generada</th><th class="n">Consumo del cliente<br>kWh</th><th class="n">Cobertura<br>solar</th><th></th>'
    sec_ex = tabla(ex_head, rows, 760 + 60 * ndias)

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
        sec_dia = '<section><h2>Por día</h2><div class="card">' + tabla('<th>Día</th><th class="n">Cortes<br>iniciados</th><th class="n">Sistemas<br>con cortes</th><th class="n">Generación FV<br>kWh</th><th class="n">Exportada<br>kWh</th><th class="n">Importada<br>kWh</th>', rows, 620) + '<p class="note" style="margin-top:10px">El viernes cuenta desde las 07:00 en cortes, exportación e importación; la generación FV es la del día completo.</p></div></section>'

    estado_cls = "warn" if en_curso else ("ok" if True else "")
    estado_txt = (f"{len(en_curso)} sistemas sin red al corte del reporte" if en_curso else ("Sin cortes de red en curso" if True else ""))
    gen = fecha_bog(int(time.time() * 1000))
    pagina = f'''<title>{esc(titulo)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
{css}
</style>
<div class="wrap">
<header>
  <div class="kick">{'Fin de semana' if es_lunes else 'Últimas 24 horas'} · {len(ciudades)} ciudades · {n_sys} sistemas</div>
  <h1>{'Operación del fin de semana' if es_lunes else 'Operación de las últimas 24 horas'}</h1>
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

<section>
  <h2>Puntos más relevantes</h2>
  <div class="card"><ul class="pts">{li}</ul></div>
</section>

<section>
  <h2>Por ciudad</h2>
  <div class="card">{sec_ciu}</div>
</section>

{sec_dia}

<section>
  <h2>Interrupciones y respaldo</h2>
  <div class="card" style="display:flex;flex-direction:column;gap:14px">
    <h3>Eventos de red</h3>
    {sec_ev}
    {('<h3>Por sistema</h3>' + sec_sis) if sec_sis else ''}
    {sec_det}
    <p class="note">Corte = intervalo entre los eventos <code>po</code> y <code>pr</code> del medidor de red. «Tiempo que vio la casa» = suma de los huecos de tensión del medidor solar (lado respaldado) asociados al corte, incluidos los del cambio al caer y al volver la red. «Respaldo» = (tiempo sin red del medidor de red − tiempo sin tensión del medidor solar) ÷ tiempo sin red del medidor de red; se calcula en todos los cortes, incluidos los de pocos segundos, y no baja de 0 %. Sin hueco, por criterio del equipo, el cliente no percibió el corte.</p>
  </div>
</section>

<section>
  <h2>Rendimiento de los sistemas</h2>
  <div class="card">
    {sec_pv}
    <p class="note" style="margin-top:10px">Generación = balance de medidores con los cierres diarios: demanda del medidor solar (<code>CenergyAI</code>) − importada + exportada del medidor de red. No se usa el contador del inversor. «Yield anual proyectado» es la generación real del día dividida entre la potencia instalada, por 365; en el portafolio Sunny y en cada ciudad, la suma de generación entre la suma de potencia. La potencia instalada es la potencia pico en DC (kWp) del archivo de sistemas, no la del inversor, y no se corrige estacionalidad ni clima. «Frente a su patrón» compara el índice del sistema (su kWh por kW sobre la mediana de su ciudad ese día) con su mediana de los 9 días anteriores; así se descuenta el efecto del clima.</p>
  </div>
</section>

<section>
  <h2>Exportación de energía activa</h2>
  <div class="card">
    {sec_ex}
    <p class="note" style="margin-top:10px">Exportada e importada, del medidor de red (<code>energyAE</code> y <code>energyAI</code>). Consumo del cliente = demanda del día calendario en el medidor solar; cobertura solar = generación / consumo del cliente. La generación es el balance de medidores, así que incluye pérdidas y la energía que pasa por la batería. Importada y exportada de la tabla son las de la ventana de 24 h.</p>
  </div>
</section>

<section>
  <h2>Comunicación y equipos</h2>
  <div class="card">{sec_com}</div>
</section>

<section>
  <h2>Límites del análisis</h2>
  <div class="limits">
    <p>Los medidores de red sin tensión envían sus eventos guardados solo cuando vuelve la red. Un corte en curso se detecta con el inversor (entrada de red por debajo de 5 V) y su hora de inicio es aproximada (≈) hasta que vuelva la red.</p>
    <p>Los relojes de los medidores difieren hasta unos 40 s entre sí. Cada hueco se asocia al corte de red más cercano en el tiempo (hasta 75 s) y los posteriores hasta 10 min después del regreso de la red.</p>
    <p>Los inversores se muestrean cada 15 min. El SOC de inicio y fin de cada corte es el de la muestra más cercana y la reserva se toma como {RESERVA:.0f} % para todos.</p>
    <p>El lunes, la ventana va desde el viernes a las 07:00 hasta el lunes a las 07:00, para no dejar horas sin cubrir entre reportes.</p>
    <p>Cada sistema es una casa (medidor de red, medidor solar, inversor y gateway). Si una casa tiene dos inversores se usa el que reportó más recientemente.</p>
    <p>Si a un medidor aún no le llegó el cierre diario de las 00:00 (hoy, Casa 9G y Casa 108), su generación del día queda sin calcular y no se reemplaza por otro dato. La generación de todos los sistemas se calcula con el balance de medidores. Queda fuera la casa que solo tiene baterías instaladas, Casa 447p ({len([x for x in EXCLUIDOS if x[2] != 'piloto'])} casa fuera del reporte).</p>
  </div>
</section>
<footer>Cálculo propio sobre telemetría cruda de Metrum. Datos consultados en {time.time() - t_cons:.0f} s.</footer>
</div>
'''
    with open(args.salida, "w", encoding="utf8") as f:
        f.write(pagina)
    resumen = dict(titulo=titulo, ventana=[h_ini, h_fin], es_lunes=es_lunes, sistemas=n_sys, excluidos=[f"{c} · {k}: {m}" for c, k, m in EXCLUIDOS], con_cortes=len(con_cortes), cortes=total_cortes, eventos=len(EV), en_curso=[R["sys"]["casa"] for R in en_curso],
                   pv_kwh=round(pv_total), yield_anual=round(yield_flota) if yield_flota else None, cobertura_pct=round(cob_flota, 1) if cob_flota is not None else None, exp_kwh=round(exp_tot), imp_kwh=round(imp_tot), puntos=[f"{t}: {x}" for n, t, x in P])
    with open(args.json, "w", encoding="utf8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print(f"escrito {args.salida} ({len(pagina)} caracteres) y {args.json}")
