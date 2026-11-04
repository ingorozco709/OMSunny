"""Mapa único con zoom de todos los sistemas (pedido del usuario, 4-nov: «mostrar todos los sistemas en un solo mapa donde se puede hacer zoom»).

Un solo lienzo (canvas) con la proyección Web Mercator: se arrastra para moverlo, con Ctrl + rueda, los botones + y − o dos dedos se acerca, y los puntos que quedarían encimados se agrupan en una rosca
con el número de sistemas y la mezcla de estados; al acercar se separan hasta verse cada casa sobre su mapa base. Las vistas (Estado, Rendimiento y Batería) y sus colores son los del mapa por
recuadros de `mapa_sistemas.py`, que queda como respaldo si este módulo falla.

Mapa base (sin internet al generar el reporte): los vectores de OpenStreetMap guardados en `mapas_base/` por `mapas_base.py` (recuadros, detalle de las casas sueltas y contexto de las ciudades;
© colaboradores de OpenStreetMap, ODbL) y, para el zoom lejano, el contorno de los países y las ciudades de Natural Earth (dominio público, `_geo.json`). Las geometrías idénticas que están en más de
un archivo se incluyen una sola vez. El dibujo, la agrupación y los gestos están en `mapa_zoom.js`.

Entrada de `bloque_mapa_zoom`: la misma de `mapa_sistemas.bloque_mapa` (lista de diccionarios con `casa`, `ciudad`, `zona`, `lat`, `lon`, `n`, `tip`, `solo_bat`, `reserva`; leyendas por vista; texto de la
reserva; y los mapas base de `mapa_sistemas.cargar_bases`). Los datos van en un `<script type="application/json">` dentro del bloque: incluyen las coordenadas de las casas (el mapa las necesita)."""
import json, os
from html import escape
import mapa_sistemas as M

HERE = os.path.dirname(os.path.abspath(__file__))
VISTAS = M.VISTAS

CSS = """
.mz-lienzo{position:relative;height:clamp(400px,68vh,660px);background:var(--bg);border:1px solid var(--line);border-radius:6px;overflow:hidden;touch-action:pan-x pan-y;outline:none;cursor:grab;user-select:none;-webkit-user-select:none}
.mz-lienzo.mz-arrastra{cursor:grabbing}
.mz-lienzo:focus-visible{border-color:var(--accent)}
.mz-lienzo canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.mz-botones{position:absolute;top:10px;left:10px;display:flex;flex-direction:column;gap:6px;z-index:2}
.mz-botones button{width:32px;height:32px;border-radius:6px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:600 17px/1 var(--f-b);cursor:pointer;padding:0;display:flex;align-items:center;justify-content:center}
.mz-botones button:hover{border-color:var(--muted)} .mz-botones button.todo{font-size:13px}
.mz-tip{position:absolute;z-index:3;max-width:min(340px,calc(100% - 16px));background:var(--surface);color:var(--ink);border:1px solid var(--muted);border-radius:6px;padding:8px 10px;font-size:12.5px;line-height:1.4;white-space:pre-line;pointer-events:none;box-shadow:0 4px 18px rgba(0,0,0,.45)}
.mz-aviso{position:absolute;left:50%;bottom:36px;transform:translateX(-50%);z-index:3;background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:12.5px;color:var(--ink2);pointer-events:none;white-space:nowrap}
.mz-tip[hidden],.mz-aviso[hidden]{display:none}
.mz-at{position:absolute;right:8px;bottom:5px;font-family:var(--f-m);font-size:10px;color:var(--muted);opacity:.9;pointer-events:none;text-align:right}
.mz-ir{margin:2px 0 8px} .mz-ir>span{margin-right:2px}
.legend span.mz-t{display:inline} .mz-n{font-style:normal;color:var(--muted);font-family:var(--f-m);font-size:12px;margin-left:3px}
@media (max-width:760px){
  .mz-lienzo{height:clamp(380px,62vh,560px)} .mz-at{bottom:25px} .mz-aviso{bottom:52px}
  .mz-ir{flex-wrap:nowrap;overflow-x:auto;padding-bottom:6px;-webkit-overflow-scrolling:touch} .mz-ir>*{flex:0 0 auto}
  .mp-bloque .legend.mp-ley{font-size:12px;gap:4px 12px}
}
"""

with open(os.path.join(HERE, "mapa_zoom.js"), encoding="utf-8") as _f:
    JS = _f.read()


def capas_unicas(bases):
    """{capa: [geometrías codificadas]} de todos los mapas base, con cada geometría una sola vez (los archivos de recuadro, detalle y contexto se traslapan)."""
    capas, vistos = {}, set()
    for clave in sorted(bases):
        b = bases[clave]
        if not isinstance(b, dict) or b.get("tipo") == "geo":
            continue
        for cod, lista in (b.get("capas") or {}).items():
            for plano in lista:
                k = (cod, tuple(plano))
                if k not in vistos:
                    vistos.add(k)
                    capas.setdefault(cod, []).append(plano)
    return capas


def _datos(items, leyendas, txt_reserva, bases):
    grupos = M.grupos_de_mapa(items)
    suelta = {}                                                    # id(item) -> es de «otros conjuntos» (casa suelta o de a dos)
    for g in grupos:
        for i in g["items"]:
            suelta[id(i)] = g["clave"].endswith("-otros")
    casas = []
    for i in items:
        s = suelta.get(id(i), False)
        corto = M._corto(i["casa"])
        casas.append({"c": i["casa"], "k": corto, "l": f"{corto} · {M.titulo(i['zona'])}" if (s and i.get("zona")) else corto, "lg": 1 if s else 0,
                      "z": M.titulo(i["zona"]), "ci": M.titulo(i["ciudad"]), "la": round(i["lat"], 6), "lo": round(i["lon"], 6),
                      "n": "".join(i["n"][v] for v, _ in VISTAS), "t": i["tip"], "sb": 1 if i.get("solo_bat") else 0, "rs": 1 if i.get("reserva") else 0})
    ciudades = []
    for c in casas:
        if c["ci"] not in ciudades:
            ciudades.append(c["ci"])
    ir = [["Todos", ""]] + [[c, ",".join(str(k) for k, x in enumerate(casas) if x["ci"] == c)] for c in ciudades]
    ir += [[g["ttl"], ",".join(str(k) for k, i in enumerate(items) if any(i is j for j in g["items"]))] for g in grupos if not g["clave"].endswith("-otros")]
    geo = bases.get("_geo") or {}
    return {"v": [list(v) for v in VISTAS], "ley": {v: [[k, t] for k, t in leyendas[v]] for v, _ in VISTAS}, "res": txt_reserva, "casas": casas, "ir": ir,
            "capas": capas_unicas(bases), "tierra": geo.get("tierra") or [], "lugares": [[l[0], l[1], l[2]] for l in (geo.get("lugares") or [])]}


def bloque_mapa_zoom(items, leyendas, txt_reserva="batería en reserva", bases=None):
    """HTML del mapa único con zoom (selector de vista, leyendas con conteos, botones «Ir a» y el lienzo)."""
    items = [dict(i) for i in items if i.get("lat") is not None and i.get("lon") is not None]
    if not items:
        return ""
    d = _datos(items, leyendas, txt_reserva, bases or {})
    botones = "".join(f'<button type="button" data-v="{v}" aria-pressed="{"true" if v == "e" else "false"}">{escape(t)}</button>' for v, t in VISTAS)
    ley = ""
    for v, _ in VISTAS:
        sp = "".join(f'<span data-k="{k}"><i class="dotl m{k}"></i><span class="mz-t">{escape(t)}<em class="mz-n"></em></span></span>' for k, t in leyendas[v])
        if v == "e":
            if any(i.get("reserva") for i in items):
                sp += f'<span data-k="rs"><i class="dotl anillo"></i><span class="mz-t">anillo: {escape(txt_reserva)}<em class="mz-n"></em></span></span>'
            if any(i.get("solo_bat") for i in items):
                sp += '<span><i class="dotl rombo"></i>rombo: casa que solo tiene baterías</span>'
        ley += f'<div class="legend mp-ley mp-ley-{v}">{sp}</div>'
    ir = "".join(f'<button type="button" data-ir="{k}">{escape(n)}</button>' for n, k in d["ir"])
    datos = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (f'<div class="mp-bloque mz-bloque" data-v="e"><div class="mp-ctl"><span>Ver por</span>{botones}</div>{ley}'
            f'<div class="mp-ctl mz-ir"><span>Ir a</span>{ir}</div>'
            f'<div class="mz-lienzo" tabindex="0" role="application" aria-label="Mapa de los {len(items)} sistemas: arrastra para moverlo y usa los botones más y menos o Ctrl y la rueda para acercar">'
            '<canvas></canvas><div class="mz-botones"><button type="button" data-z="in" aria-label="Acercar">+</button><button type="button" data-z="out" aria-label="Alejar">−</button>'
            '<button type="button" data-z="all" class="todo" aria-label="Ver todos los sistemas" title="Ver todos">⤢</button></div>'
            '<div class="mz-tip" hidden></div><div class="mz-aviso" hidden aria-live="polite"></div>'
            '<div class="mz-at">© colaboradores de OpenStreetMap</div></div>'
            f'<script type="application/json" class="mz-datos">{datos}</script>'
            '<noscript><p class="note">El mapa con zoom necesita JavaScript; las demás secciones del reporte muestran el mismo estado por casa.</p></noscript></div>')
