"""Mapa esquemático de los sistemas con su estado (SVG en línea, sin teselas ni recursos externos).

Cada sistema es un punto en la posición de su gateway (atributos `latDev` y `lonDev` de Metrum). El color depende de la vista que se elija arriba del mapa
(botones, con un script mínimo; sin él queda la vista «Estado»): «Estado» (un solo estado por sistema al momento del reporte: operativo, off-grid, desconectado o falla; el reporte ya no marca
con un anillo la batería en reserva, aunque el módulo todavía lo dibuja si un punto trae `reserva`), «Rendimiento» (yield frente al patrón de su región) y «Batería» (SOC al corte del reporte).
Los conjuntos residenciales miden unos 300 m y sus casas quedan a 10-60 m entre sí; por eso cada conjunto de 3 o más casas tiene su propio recuadro, a escala de casa, y los
conjuntos de 1 o 2 casas de una ciudad se agrupan en un recuadro «otros conjuntos» a escala de ciudad. Sin mapa base: el norte va arriba, hay rejilla y barra de escala.
El texto de cada punto sale con el cursor o al tocarlo (`<title>`, el mismo mecanismo de las demás gráficas del reporte).

Mapa base (opcional): datos de OpenStreetMap (© colaboradores de OpenStreetMap, ODbL) guardados en `mapas_base/<recuadro>.json` por `mapas_base.py` y dibujados como vectores
(calles, edificios, agua y zonas verdes, en el tema oscuro del reporte) debajo de los puntos. No se pide nada a internet al generar el reporte; un recuadro sin archivo de mapa base se dibuja con rejilla.

Entrada de `bloque_mapa`: lista de diccionarios con `casa`, `ciudad`, `zona`, `lat`, `lon`, `n` (nivel de cada vista: {"e": ..., "y": ..., "b": ...}, con c, s, w, o o g), `tip` (texto del
cursor) y, opcionalmente, `solo_bat` (True para las casas que solo tienen baterías, que se dibujan como rombo) y `reserva` (True si la batería está en reserva: anillo en la vista «Estado»)."""
import json, math, os, re, sys, unicodedata
from html import escape

VISTAS = [("e", "Estado"), ("y", "Rendimiento"), ("b", "Batería")]
ORDEN = {"c": 0, "s": 1, "w": 2, "o": 3, "g": 4}                      # gravedad: el color de arriba pesa más que el de abajo
COLOR = {"c": "var(--crit)", "s": "var(--ser)", "w": "var(--warn)", "o": "var(--off-ink)", "g": "var(--good)"}


def _css():
    c = """
.mp-ctl{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:2px 0 4px;font-size:12.5px;color:var(--muted)}
.mp-ctl button{font:inherit;color:var(--ink2);background:var(--bg);border:1px solid var(--line);border-radius:999px;padding:3px 12px;cursor:pointer}
.mp-ctl button[aria-pressed=true]{background:var(--line);color:var(--ink);border-color:var(--muted);font-weight:600}
.mp-ley{display:none;margin:2px 0 4px} .mp-ley span{white-space:normal}
.legend i.dotl.mc{background:var(--crit)} .legend i.dotl.ms{background:var(--ser)} .legend i.dotl.mw{background:var(--warn)} .legend i.dotl.mo{background:var(--off-ink)} .legend i.dotl.mg{background:var(--good)}
.legend i.dotl.rombo{border-radius:2px;transform:rotate(45deg);width:8px;height:8px;background:var(--ink2)}
.legend i.dotl.anillo{background:transparent;border:2.5px solid var(--ser);box-sizing:border-box}
.mp-grid{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start} .mp-col{flex:1 1 440px;min-width:0;display:flex;flex-direction:column;gap:14px}
.mp-tile{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:10px 12px;min-width:0;display:flex;flex-direction:column;gap:6px}
.mp-cab{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px}
.mp-cab b{font-family:var(--f-d);font-size:16px;font-weight:600}
.mp-cab .mp-sub{color:var(--muted);font-size:12.5px}
.mp-cab .mp-ch{display:none;margin-left:auto;gap:10px;font-family:var(--f-m);font-size:12px;color:var(--ink2)}
.mp-cab .mp-ch span{display:inline-flex;align-items:center;gap:4px}
.mp-cab .mp-ch i.dotl{width:9px;height:9px;border-radius:50%;display:inline-block}
.mp-cab .mp-ch i.dotl.mc{background:var(--crit)} .mp-cab .mp-ch i.dotl.ms{background:var(--ser)} .mp-cab .mp-ch i.dotl.mw{background:var(--warn)} .mp-cab .mp-ch i.dotl.mo{background:var(--off-ink)} .mp-cab .mp-ch i.dotl.mg{background:var(--good)}
.mp-cab .mp-ch i.dotl.anillo{background:transparent;border:2px solid var(--ser);box-sizing:border-box}
.mp-tile svg{display:block;width:100%;min-width:500px;height:auto}
svg .mp-fondo{fill:var(--surface)}
svg .mp-rej{stroke:var(--line2);stroke-width:1}
svg .mp-esc{stroke:var(--ink2);stroke-width:2;fill:none} svg text.mp-et{font-family:var(--f-m);font-size:10px;fill:var(--ink2);paint-order:stroke;stroke:var(--bg);stroke-width:3px;stroke-linejoin:round}
svg .mp-norte{fill:var(--ink2)}
svg .mp{stroke:var(--surface);stroke-width:2;fill:var(--off-ink)} svg .mp.bat{stroke:var(--ink2);stroke-width:1.6} svg .mp:hover{stroke:var(--ink);stroke-width:2.4}
svg .mp-res{display:none;fill:none;stroke:var(--ser);stroke-width:2.4;pointer-events:none}
.mp-bloque[data-v=e] svg .mp-res{display:inline}
svg .mb-u{fill:var(--ink);fill-opacity:.04} svg .mb-v{fill:var(--good);fill-opacity:.12} svg .mb-w{fill:var(--accent);fill-opacity:.22}
svg .mb-wl{fill:none;stroke:var(--accent);stroke-opacity:.4;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
svg .mb-e{fill:var(--ink2);fill-opacity:.22;stroke:var(--muted);stroke-opacity:.35;stroke-width:.6;stroke-linejoin:round} svg .mb-p{fill:var(--accent);fill-opacity:.4}
svg .mb-a,svg .mb-r,svg .mb-s,svg .mb-f{fill:none;stroke:var(--muted);stroke-linecap:round;stroke-linejoin:round}
svg .mb-a{stroke-opacity:.5;stroke-width:3.6} svg .mb-r{stroke-opacity:.42;stroke-width:2.6} svg .mb-s{stroke-opacity:.32;stroke-width:1.7} svg .mb-f{stroke-opacity:.34;stroke-width:1;stroke-dasharray:2 2.2}
svg .mp-fondo.base{fill:var(--bg)} svg text.mp-et.at{font-size:9px;fill:var(--muted);opacity:.85}
svg text.mp-n{font-family:var(--f-m);font-size:9.5px;fill:var(--ink2);paint-order:stroke;stroke:var(--bg);stroke-width:3px;stroke-linejoin:round;pointer-events:none}
svg text.mp-n.al{fill:var(--ink);font-weight:600}
"""
    for v, _ in VISTAS:
        c += f".mp-bloque[data-v={v}] .mp-ley-{v}{{display:flex}} .mp-bloque[data-v={v}] .mp-ch-{v}{{display:inline-flex}}\n"
        for n, col in COLOR.items():
            c += f".mp-bloque[data-v={v}] svg .mp[data-{v}={n}]{{fill:{col}}}\n"
    return c


CSS = _css()

# Cambia la vista del mapa (los puntos, la leyenda y los conteos de cada recuadro salen del atributo data-v del bloque)
JS = """(function(){
document.querySelectorAll('.mp-bloque').forEach(function(b){
  var bs=b.querySelectorAll('.mp-ctl button');
  bs.forEach(function(x){x.addEventListener('click',function(){
    b.setAttribute('data-v',x.getAttribute('data-v'));
    bs.forEach(function(y){y.setAttribute('aria-pressed',y===x?'true':'false');});
  });});
});
})();"""

_PARTICULAS = {"de", "del", "la", "y", "by", "en"}


def titulo(texto):
    """RESERVAS DE PANCE -> Reservas de Pance; TERRA BY KAIA -> Terra by Kaia."""
    pal = str(texto or "").strip().lower().split()
    return " ".join(p if (i and p in _PARTICULAS) else p.capitalize() for i, p in enumerate(pal))


def _corto(casa):
    """«Casa 104» -> «104»; «Casa 121 CR» -> «121 CR»."""
    c = str(casa).strip()
    return c[5:].strip() if c.lower().startswith("casa ") else c


K = 111320.0                                  # metros por grado de latitud


def _slug(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "sin-nombre"


def _metros(items):
    """Posición local en metros (x hacia el este, y hacia el norte) respecto al centro del grupo; devuelve (lat, lon) de ese centro."""
    la0 = sum(i["lat"] for i in items) / len(items)
    lo0 = sum(i["lon"] for i in items) / len(items)
    c = math.cos(math.radians(la0))
    for i in items:
        i["_x"] = (i["lon"] - lo0) * K * c
        i["_y"] = (i["lat"] - la0) * K
    return la0, lo0


def _geom(items, w, h_max, pad, izq):
    """Escala y posición de un recuadro; las usan el dibujo y la descarga del mapa base (`mapas_base.py`)."""
    la0, lo0 = _metros(items)
    xs, ys = [i["_x"] for i in items], [i["_y"] for i in items]
    ext_x, ext_y = max(max(xs) - min(xs), 90.0), max(max(ys) - min(ys), 90.0)
    if len(items) == 1:                                                # una sola casa: recuadro bajo, a escala de 300 m
        ext_x = ext_y = 300.0
        h_max = 150.0
    esc = min((w - 2 * pad) / ext_x, (h_max - 2 * pad) / ext_y)       # píxeles por metro
    alto = max(130.0 if len(items) == 1 else 170.0, min(h_max, ext_y * esc + 2 * pad))
    cx, cy = min(xs) + (max(xs) - min(xs)) / 2, min(ys) + (max(ys) - min(ys)) / 2
    x0 = (pad + 34 + ext_x * esc / 2) if (izq and ext_x * esc < (w - 2 * pad) * 0.5) else w / 2     # geografía angosta: a la izquierda, con los rótulos a la derecha
    return dict(esc=esc, alto=alto, cx=cx, cy=cy, x0=x0, la0=la0, lo0=lo0, w=w, pad=pad)


def grupos_de_mapa(items):
    """Los recuadros del mapa: [{clave, ttl, sub, items, w, h_max, izq, rotulo}]. Un recuadro por conjunto de 3 o más casas (a escala de casa) y uno por ciudad para
    los conjuntos de 1 o 2 casas. `clave` es el nombre del archivo de su mapa base en `mapas_base/`."""
    items = [i for i in items if i.get("lat") is not None and i.get("lon") is not None]
    ciudades = []
    for i in items:
        if i["ciudad"] not in ciudades:
            ciudades.append(i["ciudad"])
    out = []
    for c in ciudades:
        por_zona = {}
        for i in (x for x in items if x["ciudad"] == c):
            por_zona.setdefault(i["zona"] or "Sin conjunto", []).append(i)
        grandes = sorted(((z, m) for z, m in por_zona.items() if len(m) >= 3), key=lambda zm: -len(zm[1]))
        chicos = [i for z, m in por_zona.items() if len(m) < 3 for i in m]
        for z, m in grandes:
            out.append(dict(clave=f"{_slug(c)}-{_slug(z)}", ttl=titulo(z), sub=f"{titulo(c)} · {len(m)} sistemas", items=m, w=560, h_max=520, izq=False, rotulo=None))
        if chicos:
            zs = {i["zona"] for i in chicos}
            sub = f"{len(chicos)} {'sistema' if len(chicos) == 1 else 'sistemas'} en {len(zs)} {'conjunto' if len(zs) == 1 else 'conjuntos'}"
            out.append(dict(clave=f"{_slug(c)}-otros", ttl=f"Otros conjuntos de {titulo(c)}" if grandes else titulo(c), sub=(f"{titulo(c)} · " + sub) if grandes else sub,
                            items=chicos, w=560, h_max=300, izq=True, rotulo=lambda i: f"{_corto(i['casa'])} · {titulo(i['zona'])}"))
    return out


def capas_para(esc):
    """Capas del mapa base que se dibujan según la escala (píxeles por metro): a escala de casa todo; a escala de ciudad, solo calles principales, agua y zonas verdes."""
    if esc >= 0.9:
        return ("u", "v", "w", "wl", "e", "p", "a", "r", "s", "f")
    if esc >= 0.3:
        return ("u", "v", "w", "wl", "e", "a", "r", "s")
    return ("v", "w", "wl", "a", "r")


def region_visible(g, margen=0.06):
    """((lat_min, lon_min, lat_max, lon_max), píxeles por metro) de lo que se ve en el recuadro `g` de `grupos_de_mapa`, con un margen."""
    it = [dict(i) for i in g["items"]]
    G = _geom(it, g["w"], g["h_max"], 30, g["izq"])
    x_min, x_max = G["cx"] + (0 - G["x0"]) / G["esc"], G["cx"] + (G["w"] - G["x0"]) / G["esc"]
    y_min, y_max = G["cy"] - G["alto"] / 2 / G["esc"], G["cy"] + G["alto"] / 2 / G["esc"]
    dx, dy = (x_max - x_min) * margen, (y_max - y_min) * margen
    c = math.cos(math.radians(G["la0"]))
    la = lambda y: G["la0"] + y / K
    lo = lambda x: G["lo0"] + x / (K * c)
    return (la(y_min - dy), lo(x_min - dx), la(y_max + dy), lo(x_max + dx)), G["esc"]


def cargar_bases(carpeta):
    """{clave: datos} de los mapas base guardados en `carpeta` (vacío si no hay)."""
    out = {}
    try:
        nombres = sorted(os.listdir(carpeta))
    except OSError:
        return out
    for n in nombres:
        if not n.endswith(".json"):
            continue
        try:                                                                         # un archivo dañado solo deja sin mapa base a su recuadro
            with open(os.path.join(carpeta, n), encoding="utf-8") as f:
                d = json.load(f)
            out[d.get("clave") or n[:-5]] = d
        except (OSError, ValueError, AttributeError):
            pass
    return out


def decodificar(plano):
    """Lista [lat0, lon0, dlat1, dlon1, ...] en millonésimas de grado (cada punto respecto al anterior) -> [(lat, lon), ...]."""
    pts, la, lo = [], 0, 0
    for k in range(0, len(plano) - 1, 2):
        la += plano[k]
        lo += plano[k + 1]
        pts.append((la / 1e6, lo / 1e6))
    return pts


def codificar(pts):
    """[(lat, lon), ...] -> lista plana en millonésimas de grado, cada punto respecto al anterior (el primero, absoluto)."""
    out, la0, lo0 = [], 0, 0
    for la, lo in pts:
        a, b = round(la * 1e6), round(lo * 1e6)
        out += [a - la0, b - lo0]
        la0, lo0 = a, b
    return out


def _capa_base(base, G, capas):
    """SVG del mapa base (de abajo hacia arriba: usos del suelo, agua, piscinas, edificios, senderos, calles) proyectado a las coordenadas del recuadro.
    A escala de ciudad (menos de 0,3 px por metro) se pierde lo que no se distingue: puntos a menos de 1,6 px, calles de menos de 10 px y decimales."""
    c = math.cos(math.radians(G["la0"]))
    xy = lambda la, lo: (G["x0"] + ((lo - G["lo0"]) * K * c - G["cx"]) * G["esc"], G["alto"] / 2 - ((la - G["la0"]) * K - G["cy"]) * G["esc"])
    w, alto = G["w"], G["alto"]
    lejos = G["esc"] < 0.3
    paso, dec = (1.6, 0) if lejos else (0.9, 1)
    out = []
    for cod in ("u", "v", "w", "wl", "p", "e", "f", "s", "r", "a"):
        if cod not in capas:
            continue
        cerrada = cod in ("u", "v", "w", "e", "p")
        d = []
        for plano in base.get("capas", {}).get(cod, []):
            crudo = [xy(la, lo) for la, lo in decodificar(plano)]
            if len(crudo) < 2 or all(x < -40 for x, _ in crudo) or all(x > w + 40 for x, _ in crudo) or all(y < -40 for _, y in crudo) or all(y > alto + 40 for _, y in crudo):
                continue
            pts = crudo[:1]
            for q in crudo[1:-1]:
                if math.hypot(q[0] - pts[-1][0], q[1] - pts[-1][1]) >= paso:
                    pts.append(q)
            pts.append(crudo[-1])
            if len(pts) < (4 if cerrada else 2):
                continue
            if lejos and not cerrada and cod in ("r", "s") and sum(math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]) for k in range(len(pts) - 1)) < 10:
                continue
            d.append("M" + "L".join(f"{x:.{dec}f},{y:.{dec}f}" for x, y in pts) + ("Z" if cerrada else ""))
        if d:
            out.append(f'<path class="mb-{cod}" d="{"".join(d)}"/>')
    return "".join(out)


def _bonito(v):
    """Mayor número «redondo» (1, 2, 2.5, 5 × 10^n) que no pasa de v."""
    if v <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(v))
    for m in (5, 2.5, 2, 1):
        if m * e <= v:
            return m * e
    return e


def _txt_m(m):
    return f"{m / 1000:g} km" if m >= 1000 else f"{m:g} m"


def _chips(items, leyendas):
    """Conteos del encabezado de cada recuadro, uno por vista (solo se ve el de la vista activa)."""
    out = ""
    for v, _ in VISTAS:
        n = {k: 0 for k in COLOR}
        for i in items:
            n[i["n"][v]] += 1
        ch = "".join(f'<span title="{escape(t)}"><i class="dotl m{k}"></i>{n[k]}</span>' for k, t in leyendas[v] if n[k])
        if v == "e":
            nr = sum(1 for i in items if i.get("reserva"))
            ch += f'<span title="batería en reserva"><i class="dotl anillo"></i>{nr}</span>' if nr else ""
        out += f'<span class="mp-ch mp-ch-{v}">{ch}</span>'
    return out


def _tile(items, ttl, sub, leyendas, w=560, h_max=360, pad=30, rotulo=None, izq=False, base=None):
    """Un recuadro: encabezado (nombre, ciudad y cuántos sistemas hay en cada nivel) y el SVG con los puntos, sobre su mapa base si lo hay."""
    G = _geom(items, w, h_max, pad, izq)
    esc_, alto, cx, cy, x0 = G["esc"], G["alto"], G["cx"], G["cy"], G["x0"]
    capa = ""
    if base:
        try:                                                                         # OpenStreetMap casi no tiene nada mapeado ahí, o el archivo está dañado: queda la rejilla
            capa = _capa_base(base, G, capas_para(esc_)) if sum(len(v) for v in base["capas"].values()) >= 8 else ""
        except Exception:
            capa = ""
    base = base if capa else None
    pos = lambda i: (x0 + (i["_x"] - cx) * esc_, alto / 2 - (i["_y"] - cy) * esc_)
    P = [(i, *pos(i)) for i in items]
    # radio del punto según la distancia al vecino más cercano
    nn = None
    for a in range(len(P)):
        for b in range(a + 1, len(P)):
            d = math.hypot(P[a][1] - P[b][1], P[a][2] - P[b][2])
            nn = d if nn is None else min(nn, d)
    r = 8.0 if nn is None else max(4.5, min(9.0 if not base else 7.5, 0.45 * nn))
    anillo = lambda i: 3.4 if i.get("reserva") else 0.0
    s = [f'<rect class="mp-fondo{" base" if base else ""}" x="0" y="0" width="{w}" height="{alto:.0f}" rx="4"/>']
    paso = max(_bonito(52 / esc_), 5.0)
    if base:
        s.append(capa)
    else:                                                                            # sin mapa base: rejilla cada «paso» metros (referida al centro del grupo)
        gx = math.floor((cx - (x0 / esc_)) / paso) * paso
        while True:
            px = x0 + (gx - cx) * esc_
            if px > w:
                break
            if px >= 0:
                s.append(f'<line class="mp-rej" x1="{px:.1f}" y1="0" x2="{px:.1f}" y2="{alto:.0f}"/>')
            gx += paso
        gy = math.floor((cy - alto / 2 / esc_) / paso) * paso
        while True:
            py = alto / 2 - (gy - cy) * esc_
            if py < 0:
                break
            if py <= alto:
                s.append(f'<line class="mp-rej" x1="0" y1="{py:.1f}" x2="{w}" y2="{py:.1f}"/>')
            gy += paso
    L = _bonito(110 / esc_)
    lx, ly = 12, alto - 12
    s.append(f'<path class="mp-esc" d="M{lx},{ly - 4} V{ly} H{lx + L * esc_:.1f} V{ly - 4}"/><text class="mp-et" x="{lx + L * esc_ + 6:.1f}" y="{ly + 1:.0f}">{_txt_m(L)}{"" if base else " · cada cuadro " + _txt_m(paso)}</text>')
    s.append(f'<path class="mp-norte" d="M{w - 20},{10} l5,13 l-5,-3.5 l-5,3.5 Z"/><text class="mp-et" x="{w - 20}" y="{38}" text-anchor="middle">N</text>')
    if base:
        s.append(f'<text class="mp-et at" x="{w - 6}" y="{alto - 5:.0f}" text-anchor="end">© colaboradores de OpenStreetMap</text>')
    # rótulos sin traslapes: primero las casas con algo que mirar
    ocupado = [(x - r - 1 - anillo(i), y - r - 1 - anillo(i), x + r + 1 + anillo(i), y + r + 1 + anillo(i)) for i, x, y in P]
    cho = lambda a, b: not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
    solape = lambda a, b: max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    rot = {}
    for i, x, y in sorted(P, key=lambda t: (ORDEN[t[0]["n"]["e"]], 0 if t[0].get("reserva") else 1, t[0]["casa"])):
        txt = rotulo(i) if rotulo else _corto(i["casa"])
        ancho, alt = 5.7 * len(txt) + 2, 10.0
        rr = r + anillo(i)                                                          # el anillo de la batería en reserva también ocupa lugar
        cand = [("start", x + rr + 3, y + 3.4, (x + rr + 3, y - 7, x + rr + 3 + ancho, y + 4)),
                ("end", x - rr - 3, y + 3.4, (x - rr - 3 - ancho, y - 7, x - rr - 3, y + 4)),
                ("middle", x, y - rr - 3.5, (x - ancho / 2, y - rr - 3.5 - alt, x + ancho / 2, y - rr - 3.5)),
                ("middle", x, y + rr + 11, (x - ancho / 2, y + rr + 2, x + ancho / 2, y + rr + 12)),
                ("start", x + rr * 0.7 + 2, y - rr - 3, (x + rr * 0.7 + 2, y - rr - 13, x + rr * 0.7 + 2 + ancho, y - rr - 3)),          # arriba a la derecha
                ("end", x - rr * 0.7 - 2, y - rr - 3, (x - rr * 0.7 - 2 - ancho, y - rr - 13, x - rr * 0.7 - 2, y - rr - 3)),            # arriba a la izquierda
                ("start", x + rr * 0.7 + 2, y + rr + 12, (x + rr * 0.7 + 2, y + rr + 2, x + rr * 0.7 + 2 + ancho, y + rr + 12)),         # abajo a la derecha
                ("end", x - rr * 0.7 - 2, y + rr + 12, (x - rr * 0.7 - 2 - ancho, y + rr + 2, x - rr * 0.7 - 2, y + rr + 12))]           # abajo a la izquierda
        dentro = [c_ for c_ in cand if not (c_[3][0] < 2 or c_[3][2] > w - 2 or c_[3][1] < 2 or c_[3][3] > alto - 2)] or cand
        puesto = next((c_ for c_ in dentro if not any(cho(c_[3], o) for o in ocupado)), None)
        if puesto is None and (rotulo or i["n"]["e"] != "g" or i.get("reserva")):      # una casa con algo que mirar (o de un recuadro de conjuntos sueltos) siempre lleva rótulo: el lugar con menos traslape
            puesto = min(dentro, key=lambda c_: sum(solape(c_[3], o) for o in ocupado))
        if puesto:
            ocupado.append(puesto[3])
            rot[id(i)] = (txt, puesto)
    for i, x, y in sorted(P, key=lambda t: -ORDEN[t[0]["n"]["e"]]):          # las más graves se dibujan encima
        tip = escape(i["tip"])
        if i.get("reserva"):
            s.append(f'<circle class="mp-res" cx="{x:.1f}" cy="{y:.1f}" r="{r + 3.4:.1f}"/>')
        datos = " ".join(f'data-{v}="{i["n"][v]}"' for v, _ in VISTAS)
        if i.get("solo_bat"):
            s.append(f'<g class="tg"><title>{tip}</title><rect class="mp bat" {datos} x="{x - r * 0.85:.1f}" y="{y - r * 0.85:.1f}" width="{r * 1.7:.1f}" height="{r * 1.7:.1f}" rx="1.5" transform="rotate(45 {x:.1f} {y:.1f})"/></g>')
        else:
            s.append(f'<g class="tg"><title>{tip}</title><circle class="mp" {datos} cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"/></g>')
    for i, x, y in P:
        if id(i) in rot:
            txt, (anc, tx, ty, _) = rot[id(i)]
            s.append(f'<text class="mp-n{" al" if (i["n"]["e"] != "g" or i.get("reserva")) else ""}" x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anc}">{escape(txt)}</text>')
    aria = f'Mapa de {ttl}: {len(items)} {"sistema" if len(items) == 1 else "sistemas"} según su estado'
    return (f'<div class="mp-tile"><div class="mp-cab"><b>{escape(ttl)}</b><span class="mp-sub">{escape(sub)}</span>{_chips(items, leyendas)}</div>'
            f'<div class="scroll"><svg viewBox="0 0 {w} {alto:.0f}" role="img" aria-label="{escape(aria)}">{"".join(s)}</svg></div></div>', alto)


def bloque_mapa(items, leyendas, txt_reserva="batería en reserva", bases=None):
    """HTML del mapa: selector de vista, leyendas y un recuadro por conjunto de 3 o más casas y por ciudad para los conjuntos de 1 o 2 casas.
    `leyendas` = {"e": [(nivel, texto), ...], "y": [...], "b": [...]} en el orden en que se muestran; `bases` = {clave: datos} de `cargar_bases` (opcional)."""
    items = [dict(i) for i in items if i.get("lat") is not None and i.get("lon") is not None]
    if not items:
        return ""
    bases = bases or {}
    grupos = grupos_de_mapa(items)
    for g in grupos:                                                                 # ¿el mapa guardado cubre lo que hoy se ve en el recuadro? (cambia si entra una casa lejos de las demás)
        b = bases.get(g["clave"])
        try:
            if b and b.get("bbox"):
                (la0, lo0, la1, lo1), _ = region_visible(g)
                c0, d0, c1, d1 = b["bbox"]
                tol = 0.02 * max(la1 - la0, lo1 - lo0)
                if la0 < c0 - tol or lo0 < d0 - tol or la1 > c1 + tol or lo1 > d1 + tol:
                    print(f"aviso: el mapa base de «{g['clave']}» no cubre todo el recuadro (cambió la lista de casas); reconstruirlo con mapas_base.py", file=sys.stderr)
        except Exception:
            pass
    tiles = [_tile(g["items"], g["ttl"], g["sub"], leyendas, w=g["w"], h_max=g["h_max"], izq=g["izq"], rotulo=g["rotulo"], base=bases.get(g["clave"])) for g in grupos]
    # dos columnas de alto parecido (los recuadros más altos primero, cada uno en la columna más baja); dentro de cada columna se conserva el orden por ciudad
    cols, hs = [[], []], [0.0, 0.0]
    for k in sorted(range(len(tiles)), key=lambda k: -tiles[k][1]):
        c = 0 if hs[0] <= hs[1] else 1
        cols[c].append(k)
        hs[c] += tiles[k][1] + 60
    botones = "".join(f'<button type="button" data-v="{v}" aria-pressed="{"true" if v == "e" else "false"}">{escape(t)}</button>' for v, t in VISTAS)
    ley = ""
    for v, _ in VISTAS:
        sp = "".join(f'<span><i class="dotl m{k}"></i>{escape(t)}</span>' for k, t in leyendas[v])
        if v == "e":
            if any(i.get("reserva") for i in items):
                sp += f'<span><i class="dotl anillo"></i>anillo: {escape(txt_reserva)}</span>'
            if any(i.get("solo_bat") for i in items):
                sp += '<span><i class="dotl rombo"></i>rombo: casa que solo tiene baterías</span>'
        ley += f'<div class="legend mp-ley mp-ley-{v}">{sp}</div>'
    columnas = "".join('<div class="mp-col">' + "".join(tiles[k][0] for k in sorted(col)) + "</div>" for col in cols if col)
    return f'<div class="mp-bloque" data-v="e"><div class="mp-ctl"><span>Ver por</span>{botones}</div>{ley}<div class="mp-grid">{columnas}</div></div>'
