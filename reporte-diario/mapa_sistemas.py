"""Mapa esquemático de los sistemas con su estado (SVG en línea, sin teselas ni recursos externos).

Cada sistema es un punto en la posición de su gateway (atributos `latDev` y `lonDev` de Metrum). El color depende de la vista que se elija arriba del mapa
(botones, con un script mínimo; sin él queda la vista «Estado»): «Estado» (incidentes: sin red, inversor aislado, falla, sin datos, cortes en la ventana, con un anillo
para la batería en reserva), «Rendimiento» (yield frente al patrón de su región) y «Batería» (SOC al corte del reporte).
Los conjuntos residenciales miden unos 300 m y sus casas quedan a 10-60 m entre sí; por eso cada conjunto de 3 o más casas tiene su propio recuadro, a escala de casa, y los
conjuntos de 1 o 2 casas de una ciudad se agrupan en un recuadro «otros conjuntos» a escala de ciudad. Sin mapa base: el norte va arriba, hay rejilla y barra de escala.
El texto de cada punto sale con el cursor o al tocarlo (`<title>`, el mismo mecanismo de las demás gráficas del reporte).

Entrada de `bloque_mapa`: lista de diccionarios con `casa`, `ciudad`, `zona`, `lat`, `lon`, `n` (nivel de cada vista: {"e": ..., "y": ..., "b": ...}, con c, s, w, o o g), `tip` (texto del
cursor) y, opcionalmente, `solo_bat` (True para las casas que solo tienen baterías, que se dibujan como rombo) y `reserva` (True si la batería está en reserva: anillo en la vista «Estado»)."""
import math
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
.mp-grid{column-width:440px;column-gap:14px}
.mp-tile{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:10px 12px;min-width:0;display:flex;flex-direction:column;gap:6px;break-inside:avoid;margin-bottom:14px}
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
svg .mp-esc{stroke:var(--ink2);stroke-width:2;fill:none} svg text.mp-et{font-family:var(--f-m);font-size:10px;fill:var(--ink2)}
svg .mp-norte{fill:var(--ink2)}
svg .mp{stroke:var(--surface);stroke-width:2;fill:var(--off-ink)} svg .mp.bat{stroke:var(--ink2);stroke-width:1.6} svg .mp:hover{stroke:var(--ink);stroke-width:2.4}
svg .mp-res{display:none;fill:none;stroke:var(--ser);stroke-width:2.4;pointer-events:none}
.mp-bloque[data-v=e] svg .mp-res{display:inline}
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


def _metros(items):
    """Posición local en metros (x hacia el este, y hacia el norte) respecto al centro del grupo."""
    la0 = sum(i["lat"] for i in items) / len(items)
    lo0 = sum(i["lon"] for i in items) / len(items)
    k, c = 111320.0, math.cos(math.radians(la0))
    for i in items:
        i["_x"] = (i["lon"] - lo0) * k * c
        i["_y"] = (i["lat"] - la0) * k


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


def _tile(items, ttl, sub, leyendas, w=560, h_max=360, pad=30, rotulo=None, izq=False):
    """Un recuadro: encabezado (nombre, ciudad y cuántos sistemas hay en cada nivel) y el SVG con los puntos."""
    _metros(items)
    xs, ys = [i["_x"] for i in items], [i["_y"] for i in items]
    ext_x, ext_y = max(max(xs) - min(xs), 90.0), max(max(ys) - min(ys), 90.0)
    if len(items) == 1:                                                # una sola casa: recuadro bajo, a escala de 300 m
        ext_x = ext_y = 300.0
        h_max = 150.0
    esc_ = min((w - 2 * pad) / ext_x, (h_max - 2 * pad) / ext_y)      # píxeles por metro
    alto = max(130.0 if len(items) == 1 else 170.0, min(h_max, ext_y * esc_ + 2 * pad))
    cx = min(xs) + (max(xs) - min(xs)) / 2
    cy = min(ys) + (max(ys) - min(ys)) / 2
    x0 = (pad + 34 + ext_x * esc_ / 2) if (izq and ext_x * esc_ < (w - 2 * pad) * 0.5) else w / 2     # geografía angosta: a la izquierda, con los rótulos a la derecha
    pos = lambda i: (x0 + (i["_x"] - cx) * esc_, alto / 2 - (i["_y"] - cy) * esc_)
    P = [(i, *pos(i)) for i in items]
    # radio del punto según la distancia al vecino más cercano
    nn = None
    for a in range(len(P)):
        for b in range(a + 1, len(P)):
            d = math.hypot(P[a][1] - P[b][1], P[a][2] - P[b][2])
            nn = d if nn is None else min(nn, d)
    r = 8.0 if nn is None else max(4.5, min(9.0, 0.45 * nn))
    anillo = lambda i: 3.4 if i.get("reserva") else 0.0
    s = [f'<rect class="mp-fondo" x="0" y="0" width="{w}" height="{alto:.0f}" rx="4"/>']
    # rejilla cada «paso» metros (referida al centro del grupo) y barra de escala
    paso = max(_bonito(52 / esc_), 5.0)
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
    s.append(f'<path class="mp-esc" d="M{lx},{ly - 4} V{ly} H{lx + L * esc_:.1f} V{ly - 4}"/><text class="mp-et" x="{lx + L * esc_ + 6:.1f}" y="{ly + 1:.0f}">{_txt_m(L)} · cada cuadro {_txt_m(paso)}</text>')
    s.append(f'<path class="mp-norte" d="M{w - 20},{10} l5,13 l-5,-3.5 l-5,3.5 Z"/><text class="mp-et" x="{w - 20}" y="{38}" text-anchor="middle">N</text>')
    # rótulos sin traslapes: primero las casas con algo que mirar
    ocupado = [(x - r - 1 - anillo(i), y - r - 1 - anillo(i), x + r + 1 + anillo(i), y + r + 1 + anillo(i)) for i, x, y in P]
    cho = lambda a, b: not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
    rot = {}
    for i, x, y in sorted(P, key=lambda t: (ORDEN[t[0]["n"]["e"]], 0 if t[0].get("reserva") else 1, t[0]["casa"])):
        txt = rotulo(i) if rotulo else _corto(i["casa"])
        ancho, alt = 5.7 * len(txt) + 2, 10.0
        rr = r + anillo(i)                                                          # el anillo de la batería en reserva también ocupa lugar
        cand = [("start", x + rr + 3, y + 3.4, (x + rr + 3, y - 7, x + rr + 3 + ancho, y + 4)),
                ("end", x - rr - 3, y + 3.4, (x - rr - 3 - ancho, y - 7, x - rr - 3, y + 4)),
                ("middle", x, y - rr - 3.5, (x - ancho / 2, y - rr - 3.5 - alt, x + ancho / 2, y - rr - 3.5)),
                ("middle", x, y + rr + 11, (x - ancho / 2, y + rr + 2, x + ancho / 2, y + rr + 12))]
        puesto = None
        for anc, tx, ty, caja in cand:
            if caja[0] < 2 or caja[2] > w - 2 or caja[1] < 2 or caja[3] > alto - 2:
                continue
            if any(cho(caja, o) for o in ocupado):
                continue
            puesto = (anc, tx, ty, caja)
            break
        if puesto is None and (i["n"]["e"] != "g" or i.get("reserva")):      # una casa con algo que mirar siempre lleva rótulo, aunque se pegue a otra
            puesto = cand[0]
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
            f'<div class="scroll"><svg viewBox="0 0 {w} {alto:.0f}" role="img" aria-label="{escape(aria)}">{"".join(s)}</svg></div></div>')


def bloque_mapa(items, leyendas, txt_reserva="batería en reserva"):
    """HTML del mapa: selector de vista, leyendas y un recuadro por conjunto de 3 o más casas y por ciudad para los conjuntos de 1 o 2 casas.
    `leyendas` = {"e": [(nivel, texto), ...], "y": [...], "b": [...]} en el orden en que se muestran."""
    items = [dict(i) for i in items if i.get("lat") is not None and i.get("lon") is not None]
    if not items:
        return ""
    ciudades = []
    for i in items:
        if i["ciudad"] not in ciudades:
            ciudades.append(i["ciudad"])
    tiles = []
    for c in ciudades:
        g = [i for i in items if i["ciudad"] == c]
        por_zona = {}
        for i in g:
            por_zona.setdefault(i["zona"] or "Sin conjunto", []).append(i)
        grandes = sorted(((z, m) for z, m in por_zona.items() if len(m) >= 3), key=lambda zm: -len(zm[1]))
        chicos = [i for z, m in por_zona.items() if len(m) < 3 for i in m]
        for z, m in grandes:
            tiles.append(_tile(m, titulo(z), f"{titulo(c)} · {len(m)} sistemas", leyendas, w=560, h_max=520))
        if chicos:
            zs = {i["zona"] for i in chicos}
            sub = f"{len(chicos)} {'sistema' if len(chicos) == 1 else 'sistemas'} en {len(zs)} {'conjunto' if len(zs) == 1 else 'conjuntos'}"
            if grandes:
                sub = f"{titulo(c)} · " + sub
            tiles.append(_tile(chicos, f"Otros conjuntos de {titulo(c)}" if grandes else titulo(c), sub, leyendas, w=560, h_max=300, izq=True,
                               rotulo=lambda i: f"{_corto(i['casa'])} · {titulo(i['zona'])}"))
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
    return f'<div class="mp-bloque" data-v="e"><div class="mp-ctl"><span>Ver por</span>{botones}</div>{ley}<div class="mp-grid">{"".join(tiles)}</div></div>'
