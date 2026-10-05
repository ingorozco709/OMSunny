#!/usr/bin/env python3
"""INIC 4 - Disponibilidad operativa (% de respaldo) de un mes y su Excel de soporte.

% Respaldo = (T_red - T_solar) / T_red x 100, consolidado como promedio ponderado por tiempo
(suma de T_respaldo / suma de T_red) de los eventos de red con T_red mayor a 2 minutos.

Uso:
  python3 om-agency/scripts/indicador_inic4.py --out /tmp/INIC4.xlsx            # mes anterior
  python3 om-agency/scripts/indicador_inic4.py --mes 2026-09 --out /tmp/INIC4.xlsx
Variables de entorno: METRUM_API_URL, METRUM_USERNAME, METRUM_PASSWORD (nunca se escriben en archivos).
Alcance: todos los sistemas de Metrum salvo Piloto Promigas, Piloto Huawei, Castellana Real y los de
om-agency/data/inic4_config.json (excluir_sistemas). Los sistemas que ingresaron a operar en el mes o que
estan solo con baterias cuentan con los eventos posteriores a su primer dato y se rotulan en Observacion.
"""
import argparse, datetime as dt, json, os, subprocess, sys, shutil, tempfile, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reporte_diario as R
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L

HERE = os.path.dirname(os.path.abspath(__file__))
BOG = R.BOG
ORDEN = ["Prado Verde Primavera", "Reservas de Pance", "Terra by Kaia", "Llanos de Pance", "Porton de la Rivera", "Los Abedules", "Terranova", "Gerona Club House"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def zn(z):
    return z.title().replace("Condominio ", "").replace(" De ", " de ").replace(" La ", " la ").replace(" By ", " by ")


def primer_dato(did, key):
    r = R.get(f"/api/plugins/telemetry/DEVICE/{did}/values/timeseries?keys={key}&startTs=0&endTs={int(time.time()*1000)}&limit=1&orderBy=ASC&agg=NONE")
    v = r.get(key, [])
    return v[0]["ts"] if v else None


def calcular(h, a, b):
    hoy0 = dt.datetime.now(BOG).replace(hour=0, minute=0, second=0, microsecond=0)
    r = R.procesar(h, a, b, hoy0, [hoy0])
    pd = []
    for tipo, key in (("red", "voltageA"), ("solar", "voltageA"), (None, "BattSOC")):
        ts = [primer_dato(x["id"], key) for x in h["hijos"] if x["mettype"] == tipo]
        ts = [t for t in ts if t]
        if ts:
            pd.append(min(ts))
    r["primer_dato"] = max(pd) if pd else None
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", help="AAAA-MM; por defecto el mes anterior")
    ap.add_argument("--out", default="INIC4.xlsx")
    args = ap.parse_args()
    hoy = dt.datetime.now(BOG)
    if args.mes:
        y, m = map(int, args.mes.split("-"))
    else:
        y, m = (hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12)
    ini = dt.datetime(y, m, 1, tzinfo=BOG)
    fin = dt.datetime(y + (m == 12), 1 if m == 12 else m + 1, 1, tzinfo=BOG)
    a, b = ini.timestamp() * 1000, fin.timestamp() * 1000
    cfg = json.load(open(os.path.join(HERE, "..", "data", "inic4_config.json"), encoding="utf-8"))
    excl, umbral = cfg.get("excluir_sistemas", {}), cfg.get("umbral_evento_s", 120)
    R.login()
    flota = R.cargar_flota()
    print(f"Flota: {len(flota)} sistemas; mes {y}-{m:02d}", file=sys.stderr)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda h: calcular(h, a, b), flota))
    inc = [r for r in res if r["casa"] not in excl]
    pref = {z: i for i, z in enumerate(ORDEN)}
    inc.sort(key=lambda r: (pref.get(zn(r["zona"]), 99), zn(r["zona"]), len(r["casa"]), r["casa"]))
    ev = [(r, e) for r in inc for e in r["eventos"] if e["or_s"] > umbral and e["cl_s"] is not None]
    ev.sort(key=lambda x: x[1]["ini"])

    def obs(r):
        sin = r["casa"] in R.SIN_PANELES or (r.get("gen") is not None and r["gen"] < 0)
        nuevo = r["primer_dato"] and r["primer_dato"] > a + 24 * 3600e3
        d = dt.datetime.fromtimestamp(r["primer_dato"] / 1000, BOG).strftime("%d/%m") if r["primer_dato"] else ""
        if sin and nuevo: return f"Solo con batería; datos desde el {d}"
        if sin: return "Solo con batería (sin paneles)"
        if nuevo: return f"Ingresó a operar en el mes; datos desde el {d}"
        return ""

    # ---- Excel
    A = "Arial"
    hf = Font(name=A, bold=True, color="FFFFFF", size=10); hfill = PatternFill("solid", fgColor="1F3A5F")
    nf = Font(name=A, size=10); bf = Font(name=A, size=10, bold=True); inp = Font(name=A, size=10, color="0000FF")
    thin = Side(style="thin", color="C9D1CE"); bd = Border(top=thin, bottom=thin, left=thin, right=thin)
    f = lambda t: dt.datetime.fromtimestamp(t / 1000, BOG).replace(tzinfo=None)
    wb = Workbook(); wr = wb.active; wr.title = "Resumen"; we = wb.create_sheet("Eventos"); ws = wb.create_sheet("Por sistema")
    nE, nS = len(ev) + 1, len(inc) + 1
    we.append(["#", "Sistema", "Zona", "Marca", "Inicio del corte de red", "Fin del corte de red", "Cortes agrupados", "T_red (min)", "T_solar (min)", "T_respaldo (min)", "% respaldo del evento", "SOC al inicio (%)"])
    for i, (r, e) in enumerate(ev, start=2):
        we.append([i - 1, r["casa"], zn(r["zona"]), r["marca"], f(e["ini"]), f(e["fin"]), e["n"], e["or_s"] / 60, e["cl_s"] / 60, f"=MAX(0,H{i}-I{i})", f"=J{i}/H{i}", e["soc"]])
        we.cell(i, 8).font = inp; we.cell(i, 9).font = inp
    ws.append(["Sistema", "Zona", "Marca", "Eventos > 2 min", "T_red (min)", "T_respaldo (min)", "% de respaldo", "Observación"])
    for i, r in enumerate(inc, start=2):
        ws.append([r["casa"], zn(r["zona"]), r["marca"], f"=COUNTIFS(Eventos!$B$2:$B${nE},A{i})", f"=SUMIFS(Eventos!$H$2:$H${nE},Eventos!$B$2:$B${nE},A{i})",
                   f"=SUMIFS(Eventos!$J$2:$J${nE},Eventos!$B$2:$B${nE},A{i})", f'=IF(E{i}>0,F{i}/E{i},"Sin eventos")', obs(r)])
    mes_txt = f"{MESES[m-1]} {y}"
    wr["A1"] = f"INIC 4 · Disponibilidad operativa (% de respaldo) · {mes_txt.capitalize()}"; wr["A1"].font = Font(name=A, bold=True, size=14, color="1F3A5F")
    wr["A2"] = (f"Meta: ≥ 90 % de disponibilidad operativa promedio de los sistemas. Periodo: {ini.strftime('%d/%m/%Y')} 00:00 a {(fin - dt.timedelta(minutes=1)).strftime('%d/%m/%Y %H:%M')} (hora Colombia). "
                "Alcance: todos los sistemas de Metrum excepto Piloto Promigas, Piloto Huawei, Castellana Real" + "".join(f" y {k} ({v.lower()})" if i == len(excl) - 1 and len(excl) > 0 else f", {k} ({v.lower()})" for i, (k, v) in enumerate(excl.items())) + ".")
    wr["A3"] = f"% Respaldo = (T_red − T_solar) / T_red × 100, consolidado como promedio ponderado por tiempo: suma de T_respaldo ÷ suma de T_red de todos los eventos con T_red mayor a {umbral // 60} minutos."
    for c in ("A2", "A3"): wr[c].font = nf; wr[c].alignment = Alignment(wrap_text=True, vertical="top")
    wr.merge_cells("A2:F2"); wr.merge_cells("A3:F3"); wr.row_dimensions[2].height = 48; wr.row_dimensions[3].height = 32
    def put(r, vals):
        for j, v in enumerate(vals, start=1):
            c = wr.cell(r, j, v); c.font = nf; c.border = bd; c.alignment = Alignment(vertical="center", wrap_text=True)
    blk = [("Sistemas incluidos", f"=COUNTA('Por sistema'!A2:A{nS})", "0"), ("Sistemas con eventos mayores a 2 min", f"=COUNTIF('Por sistema'!D2:D{nS},\">0\")", "0"),
           ("Eventos mayores a 2 min", f"=COUNT(Eventos!H2:H{nE})", "0"), ("T_red total (h)", f"=SUM(Eventos!H2:H{nE})/60", "#,##0.0"), ("T_solar total (h)", f"=SUM(Eventos!I2:I{nE})/60", "#,##0.0"),
           ("T_respaldo total (h)", f"=SUM(Eventos!J2:J{nE})/60", "#,##0.0"), (f"% DE RESPALDO — INIC 4 ({MESES[m-1]})", '=IF(B8>0,B10/B8,"Sin eventos")', "0.0%"), ("¿Cumple la meta ≥ 90 %?", '=IF(ISNUMBER(B11),IF(B11>=0.9,"Sí","No"),"—")', "@")]
    for k, (a_, b_, fm) in enumerate(blk):
        put(5 + k, [a_, b_]); wr.cell(5 + k, 2).number_format = fm
    for c in (1, 2): wr.cell(11, c).fill = PatternFill("solid", fgColor="E3F3E9")
    wr.cell(11, 1).font = bf; wr.cell(11, 2).font = Font(name=A, bold=True, size=13)
    r0 = 15; wr.cell(r0 - 1, 1, "Resumen por zona").font = Font(name=A, bold=True, size=12, color="1F3A5F")
    for j, h_ in enumerate(["Zona", "Sistemas", "Eventos > 2 min", "T_red (h)", "T_respaldo (h)", "% de respaldo"], start=1):
        c = wr.cell(r0, j, h_); c.font = hf; c.fill = hfill; c.border = bd; c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    zs = []
    for r in inc:
        if zn(r["zona"]) not in zs: zs.append(zn(r["zona"]))
    for k, z in enumerate(zs, start=1):
        r = r0 + k
        put(r, [z, f"=COUNTIF('Por sistema'!$B$2:$B${nS},A{r})", f"=COUNTIF(Eventos!$C$2:$C${nE},A{r})", f"=SUMIFS(Eventos!$H$2:$H${nE},Eventos!$C$2:$C${nE},A{r})/60",
                f"=SUMIFS(Eventos!$J$2:$J${nE},Eventos!$C$2:$C${nE},A{r})/60", f'=IF(D{r}>0,E{r}/D{r},"Sin eventos > 2 min")'])
        wr.cell(r, 4).number_format = "#,##0.0"; wr.cell(r, 5).number_format = "#,##0.0"; wr.cell(r, 6).number_format = "0.0%"
    rt = r0 + len(zs) + 1
    put(rt, ["Total", f"=SUM(B{r0+1}:B{rt-1})", f"=SUM(C{r0+1}:C{rt-1})", f"=SUM(D{r0+1}:D{rt-1})", f"=SUM(E{r0+1}:E{rt-1})", f'=IF(D{rt}>0,E{rt}/D{rt},"Sin eventos")'])
    for c in range(1, 7): wr.cell(rt, c).font = bf
    wr.cell(rt, 4).number_format = "#,##0.0"; wr.cell(rt, 5).number_format = "#,##0.0"; wr.cell(rt, 6).number_format = "0.0%"
    n = rt + 2
    if excl:
        wr.cell(n, 1, "Sistemas fuera del cálculo").font = bf; n += 1
        for k, v in excl.items():
            put(n, [k, v]); wr.merge_cells(start_row=n, start_column=2, end_row=n, end_column=6); n += 1
        n += 1
    wr.cell(n, 1, "Notas").font = bf; n += 1
    parc = [r["casa"] for r in inc if obs(r)]
    notas = [f"Fuente: telemetría de Metrum (eventos de pérdida y restablecimiento de tensión del medidor de red y del medidor solar), consultada el {hoy.strftime('%d/%m/%Y')}.",
             "Evento: cortes de red separados por menos de 15 min se cuentan como un solo evento. T_red = suma del tiempo sin tensión en el medidor de red dentro del evento; T_solar = tiempo sin tensión en el medidor solar entre 2 min antes y 15 min después del evento; T_respaldo = máx(0; T_red − T_solar).",
             ("Los sistemas que ingresaron a operar en el mes o están solo con batería (" + ", ".join(parc) + ") cuentan con los eventos posteriores a su primer dato; ver la columna Observación de la hoja Por sistema.") if parc else "Todos los sistemas incluidos tienen datos completos del mes.",
             "Los valores en azul de la hoja Eventos son datos medidos de Metrum; el resto son fórmulas. Las zonas sin eventos mayores a 2 minutos se muestran como tales."]
    for t in notas:
        c = wr.cell(n, 1, t); c.font = nf; c.alignment = Alignment(wrap_text=True, vertical="top"); wr.merge_cells(start_row=n, start_column=1, end_row=n, end_column=6); wr.row_dimensions[n].height = 44; n += 1
    for w in (we, ws):
        for c in w[1]: c.font = hf; c.fill = hfill; c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center"); c.border = bd
        w.row_dimensions[1].height = 36; w.freeze_panes = "B2"
    for row in we.iter_rows(min_row=2):
        for c in row:
            if c.font != inp: c.font = nf
            c.border = bd
        row[4].number_format = "dd/mm/yyyy hh:mm:ss"; row[5].number_format = "dd/mm/yyyy hh:mm:ss"
        for k in (7, 8, 9): row[k].number_format = "#,##0.00"
        row[10].number_format = "0.0%"
    for row in ws.iter_rows(min_row=2):
        for c in row: c.font = nf; c.border = bd
        row[4].number_format = "#,##0.00"; row[5].number_format = "#,##0.00"; row[6].number_format = "0.0%"
    for w, wd in ((we, [6, 12, 24, 11, 20, 20, 10, 12, 12, 13, 13, 11]), (ws, [12, 24, 11, 14, 13, 15, 14, 48]), (wr, [44, 12, 16, 12, 15, 20])):
        for i, x in enumerate(wd, start=1): w.column_dimensions[L(i)].width = x
    we.auto_filter.ref = f"A1:L{nE}"; ws.auto_filter.ref = f"A1:H{nS}"
    wb.save(args.out)
    # recalcula con LibreOffice si esta disponible (para que los valores se vean sin abrir en Excel)
    so = shutil.which("soffice")
    if so:
        try:
            tmp = tempfile.mkdtemp()
            subprocess.run([so, "--headless", "--convert-to", "xlsx", "--outdir", tmp, args.out], check=True, capture_output=True, timeout=120)
            shutil.move(os.path.join(tmp, os.path.basename(args.out)), args.out)
        except Exception as e:
            print("Aviso: no se pudo recalcular con LibreOffice:", e, file=sys.stderr)
    # resumen en consola (mismo calculo que las formulas del Excel)
    OR = sum(e["or_s"] for r, e in ev); BK = sum(max(0, e["or_s"] - e["cl_s"]) for r, e in ev)
    pct = 100 * BK / OR if OR else None
    print(f"EXCEL: {args.out}")
    print(f"MES: {mes_txt}")
    print(f"SISTEMAS: {len(inc)} incluidos ({len({r['casa'] for r, e in ev})} con eventos > {umbral//60} min); excluidos: {', '.join(excl) or 'ninguno'}")
    print(f"EVENTOS: {len(ev)}; T_red {OR/3600:.1f} h; T_respaldo {BK/3600:.1f} h")
    print(f"INDICADOR: {pct:.1f} %" if pct is not None else "INDICADOR: sin eventos")
    print("POR_ZONA:")
    for z in zs:
        o = sum(e["or_s"] for r, e in ev if zn(r["zona"]) == z); k = sum(max(0, e["or_s"] - e["cl_s"]) for r, e in ev if zn(r["zona"]) == z)
        n_s = sum(1 for r in inc if zn(r["zona"]) == z)
        print(f"  {z}: {100*k/o:.1f} % ({n_s} sistemas)" if o else f"  {z}: sin eventos > {umbral//60} min ({n_s} sistemas)")


if __name__ == "__main__":
    main()
