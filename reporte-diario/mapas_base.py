"""Mapas base del mapa de sistemas: baja de OpenStreetMap lo que se ve en cada recuadro y lo guarda en `mapas_base/<recuadro>.json`.

Datos © colaboradores de OpenStreetMap (ODbL, https://www.openstreetmap.org/copyright): calles, edificios, piscinas, agua y zonas verdes, como vectores simplificados. El reporte los dibuja
debajo de los puntos (`mapa_sistemas.py`) sin pedir nada a internet; si falta el archivo de un recuadro, ese recuadro sale con rejilla en vez de mapa base.

Se corre una vez y de nuevo solo cuando cambia la lista de recuadros (una casa en un conjunto nuevo, un conjunto que pasa de 2 a 3 casas) o si se quiere refrescar el mapa:
    python3 reporte-diario/mapas_base.py [--salida reporte-diario/mapas_base] [--solo cali-reservas-de-pance] [--zoom]
`--zoom` baja, en vez de los recuadros, lo que necesita el mapa único con zoom (`mapa_zoom.py`): el detalle (±300 m, todas las capas) alrededor de cada casa de «otros conjuntos» y el contexto de las ciudades
chicas (calles, agua y verde en ~1 km alrededor de sus casas). `--geo` baja, sin tocar Metrum, el contorno de los países y las ciudades de Natural Earth (dominio público) para el zoom lejano.
Lee de Metrum las coordenadas de los gateways (METRUM_API_URL, METRUM_USERNAME y METRUM_PASSWORD) y hace unas pocas peticiones a la API de OpenStreetMap (una por recuadro; se parte la
caja si tiene demasiados nodos). Uso moderado, como pide la política de OpenStreetMap: no se descarga nada al generar el reporte diario.
Los archivos no traen las casas ni sus coordenadas: solo el entorno de cada recuadro."""
import os, sys, json, math, time, argparse, datetime as dt, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import mapa_sistemas as M

API = "https://api.openstreetmap.org/api/0.6/map.json"
UA = "SunnyOM-reporte/1.0 (mapa base del reporte de operacion; Promigas Sunny)"
VIAS = {"a": {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"},
        "r": {"residential", "unclassified", "living_street", "pedestrian"},
        "s": {"service", "track"},
        "f": {"footway", "path", "steps", "cycleway", "bridleway", "corridor"}}
VERDE = {"grass", "forest", "meadow", "recreation_ground", "village_green", "orchard", "park", "garden", "pitch", "playground", "golf_course", "nature_reserve", "wood", "scrub", "grassland", "wetland"}


def _get(url):
    err = ""
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=120) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 509):              # demasiados nodos o caja muy grande: el que llama la parte
                return e.code, b""
            err = f"HTTP {e.code}"
        except Exception as e:
            err = str(e)[:100]
        time.sleep(3 * (i + 1))
    raise RuntimeError("no se pudo leer la API de OpenStreetMap: " + err)


def descargar(bb, prof=0):
    """Elementos de OpenStreetMap de la caja bb = (lat_min, lon_min, lat_max, lon_max); si la API dice que son demasiados, la parte en cuatro."""
    la0, lo0, la1, lo1 = bb
    c, b = (400, b"") if (la1 - la0) * (lo1 - lo0) > 0.2 else _get(f"{API}?bbox={lo0:.6f},{la0:.6f},{lo1:.6f},{la1:.6f}")
    if c == 200:
        return json.loads(b).get("elements", [])
    if prof >= 4:
        raise RuntimeError("la caja sigue siendo demasiado grande para la API de OpenStreetMap")
    lam, lom = (la0 + la1) / 2, (lo0 + lo1) / 2
    els, vistos = [], set()
    for caja in ((la0, lo0, lam, lom), (la0, lom, lam, lo1), (lam, lo0, la1, lom), (lam, lom, la1, lo1)):
        time.sleep(1)
        for e in descargar(caja, prof + 1):
            if (e["type"], e["id"]) not in vistos:
                vistos.add((e["type"], e["id"]))
                els.append(e)
    return els


def clasificar(t, cerrado):
    """Capa de un elemento según sus etiquetas: a/r/s/f = calles (principal, residencial, de servicio, sendero), e = edificio, p = piscina, w = agua, wl = cauce, v = zona verde, u = uso residencial."""
    h = t.get("highway")
    if h:
        for cod, vals in VIAS.items():
            if h in vals:
                return cod
        return None
    if t.get("waterway") in ("river", "stream", "canal"):
        return "wl"
    if not cerrado:
        return None
    if t.get("building") and t.get("building") != "no":
        return "e"
    if t.get("leisure") == "swimming_pool":
        return "p"
    if t.get("natural") == "water" or t.get("water"):
        return "w"
    if t.get("landuse") in VERDE or t.get("leisure") in VERDE or t.get("natural") in VERDE:
        return "v"
    if t.get("landuse") == "residential":
        return "u"
    return None


def a_capas(els, capas):
    """{capa: [geometría codificada]} con los caminos de OpenStreetMap que caen en las capas pedidas."""
    nodos = {e["id"]: (e["lat"], e["lon"]) for e in els if e["type"] == "node"}
    out = {c: [] for c in capas}
    for e in els:
        if e["type"] != "way":
            continue
        ids = e.get("nodes", [])
        cod = clasificar(e.get("tags") or {}, len(ids) > 3 and ids[0] == ids[-1])
        if cod not in out:
            continue
        pts = [nodos[n] for n in ids if n in nodos]
        if len(pts) >= 2:
            out[cod].append(M.codificar(pts))
    return {c: g for c, g in out.items() if g}


def items_del_reporte():
    """Sistemas del reporte con sus coordenadas, conjunto del gateway y ciudad, leídos de Metrum."""
    import concurrent.futures as cf
    import reporte_diario as rd
    devs = rd.listar_dispositivos()
    with cf.ThreadPoolExecutor(8) as ex:
        attrs = {dv["id"]["id"]: a for dv, a in ex.map(rd.atributos, devs)}
    kwp = json.load(open(os.path.join(HERE, "potencia_instalada.json")))
    SYS = rd.construir_sistemas(devs, attrs)
    return sorted(({"casa": s["casa"], "ciudad": s["ciudad"], "zona": s.get("zona_gw") or s["zona"], "lat": s["lat"], "lon": s["lon"]}
                   for s in SYS.values() if s["lat"] is not None and s["casa"].strip().lower() in kwp), key=lambda i: (rd.ordenar_ciudad(i["ciudad"]), rd.num_casa(i["casa"])))


GEO = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
PAISES = {"COL", "PAN", "VEN", "ECU", "PER", "BRA", "CRI", "NIC"}


def _rdp(p, tol):
    """Douglas-Peucker sobre [(x, y), ...] (iterativo)."""
    if len(p) < 3:
        return p
    keep = [False] * len(p)
    keep[0] = keep[-1] = True
    pila = [(0, len(p) - 1)]
    while pila:
        a, b = pila.pop()
        (ax, ay), (bx, by) = p[a], p[b]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        dmax, ik = 0.0, -1
        for k in range(a + 1, b):
            px, py = p[k]
            if l2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > dmax:
                dmax, ik = d, k
        if dmax > tol:
            keep[ik] = True
            pila += [(a, ik), (ik, b)]
    return [q for q, k in zip(p, keep) if k]


VENTANA_GEO = (-90.0, -10.0, -58.0, 16.0)             # lon_min, lat_min, lon_max, lat_max: lo que puede llegar a verse al alejar el mapa


def _recortar(anillo, x0, y0, x1, y1):
    """Recorte de un anillo [(x, y), ...] a un rectángulo (Sutherland-Hodgman)."""
    def paso(pts, dentro, cruce):
        out = []
        for k in range(len(pts)):
            a, b = pts[k - 1], pts[k]
            da, db = dentro(a), dentro(b)
            if db:
                if not da:
                    out.append(cruce(a, b))
                out.append(b)
            elif da:
                out.append(cruce(a, b))
        return out
    vx = lambda X: (lambda a, b: (X, a[1] + (X - a[0]) / (b[0] - a[0]) * (b[1] - a[1])))
    hy = lambda Y: (lambda a, b: (a[0] + (Y - a[1]) / (b[1] - a[1]) * (b[0] - a[0]), Y))
    pts = anillo[:-1] if anillo and anillo[0] == anillo[-1] else list(anillo)
    for dentro, cruce in ((lambda q: q[0] >= x0, vx(x0)), (lambda q: q[0] <= x1, vx(x1)), (lambda q: q[1] >= y0, hy(y0)), (lambda q: q[1] <= y1, hy(y1))):
        if not pts:
            break
        pts = paso(pts, dentro, cruce)
    return pts + pts[:1] if pts else []


def geo(salida):
    """Contorno simplificado de los países vecinos y ciudades de Natural Earth (dominio público) -> `_geo.json`, para el mapa con zoom cuando se aleja la vista."""
    def leer(n):
        return json.loads(_get(GEO + n)[1])
    tierra = []
    for f in leer("ne_50m_admin_0_countries.geojson")["features"]:
        cod = f["properties"].get("ADM0_A3")
        if cod not in PAISES:
            continue
        g = f["geometry"]
        for pol in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            s = _rdp(_recortar([(x, y) for x, y in pol[0]], *VENTANA_GEO), 0.02 if cod == "COL" else 0.04)
            if len(s) >= 4:
                tierra.append(M.codificar([(y, x) for x, y in s]))
    lugares = []
    for f in leer("ne_50m_populated_places_simple.geojson")["features"]:
        p = f["properties"]
        x, y = f["geometry"]["coordinates"]
        if p.get("pop_max", 0) >= (300000 if p.get("adm0name") == "Colombia" else 1000000) and p.get("adm0_a3") in PAISES and VENTANA_GEO[0] <= x <= VENTANA_GEO[2] and VENTANA_GEO[1] <= y <= VENTANA_GEO[3]:
            nombre = p.get("nameascii") or p["name"]
            lugares.append([{"Bogota": "Bogotá", "Medellin": "Medellín", "Panama City": "Ciudad de Panamá", "San Jose": "San José", "Cucuta": "Cúcuta"}.get(nombre, nombre), round(y, 4), round(x, 4), p["pop_max"]])
    lugares.append(["Turbaco", 10.3333, -75.4167, 100000])                     # no está en Natural Earth a esta escala
    sal = os.path.join(salida, "_geo.json")
    with open(sal, "w", encoding="utf-8") as f:
        json.dump({"clave": "_geo", "tipo": "geo", "fuente": "Natural Earth", "licencia": "dominio público", "fecha": dt.date.today().isoformat(), "tierra": tierra, "lugares": sorted(lugares, key=lambda l: -l[3])}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"_geo: {len(tierra)} polígonos, {sum(len(t) // 2 for t in tierra)} puntos, {len(lugares)} lugares | {os.path.getsize(sal) // 1024} KB", flush=True)


def _caja(items, margen_m):
    """(lat_min, lon_min, lat_max, lon_max) de las casas con un margen en metros."""
    la0, la1 = min(i["lat"] for i in items), max(i["lat"] for i in items)
    lo0, lo1 = min(i["lon"] for i in items), max(i["lon"] for i in items)
    dla = margen_m / M.K
    dlo = margen_m / (M.K * math.cos(math.radians((la0 + la1) / 2)))
    return (la0 - dla, lo0 - dlo, la1 + dla, lo1 + dlo)


def parches_zoom(items, margen_detalle=300, margen_contexto=1000, max_km2=30):
    """Parches extra del mapa con zoom: [(clave, tipo, caja, capas)]. Detalle (todas las capas) alrededor de cada casa de «otros conjuntos» y, en las ciudades con pocas casas juntas,
    contexto de calles, agua y verde en `margen_contexto` m alrededor de sus casas (Cali ya queda cubierta por el recuadro de «otros conjuntos»)."""
    out = []
    for g in M.grupos_de_mapa(items):
        if g["clave"].endswith("-otros"):
            for i in g["items"]:
                out.append((f"detalle-{M._slug(i['casa'])}", "detalle", _caja([i], margen_detalle), M.capas_para(2.0)))
    ciudades = []
    for i in items:
        if i["ciudad"] not in ciudades:
            ciudades.append(i["ciudad"])
    for c in ciudades:
        caja = _caja([i for i in items if i["ciudad"] == c], margen_contexto)
        km2 = (caja[2] - caja[0]) * M.K * (caja[3] - caja[1]) * M.K * math.cos(math.radians((caja[0] + caja[2]) / 2)) / 1e6
        if km2 <= max_km2:
            out.append((f"contexto-{M._slug(c)}", "contexto", caja, ("v", "w", "wl", "a", "r")))
    return out


def guardar(salida, clave, tipo, bb, capas):
    els = descargar(bb)
    datos = a_capas(els, capas)
    sal = os.path.join(salida, clave + ".json")
    with open(sal, "w", encoding="utf-8") as f:
        json.dump({"clave": clave, "tipo": tipo, "fuente": "OpenStreetMap", "licencia": "ODbL", "fecha": dt.date.today().isoformat(), "bbox": [round(x, 6) for x in bb], "capas": datos}, f, separators=(",", ":"))
    return datos, sal


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--salida", default=os.path.join(HERE, "mapas_base"))
    ap.add_argument("--solo", help="clave de un recuadro (p. ej. cali-reservas-de-pance); por defecto, todos")
    ap.add_argument("--zoom", action="store_true", help="baja solo el detalle y el contexto que usa el mapa único con zoom (no los recuadros)")
    ap.add_argument("--geo", action="store_true", help="solo baja el contorno de países y ciudades de Natural Earth (no usa Metrum)")
    a = ap.parse_args()
    if os.path.exists("/root/.ccr/ca-bundle.crt"):
        os.environ.setdefault("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt")
    os.makedirs(a.salida, exist_ok=True)
    if a.geo:
        geo(a.salida)
        sys.exit(0)
    items = items_del_reporte()
    if a.zoom:
        for clave, tipo, bb, capas in parches_zoom(items):
            if a.solo and clave != a.solo:
                continue
            datos, sal = guardar(a.salida, clave, tipo, bb, capas)
            print(f'{clave} ({tipo}): capas {"".join(c + ":" + str(len(v)) + " " for c, v in datos.items())}| {os.path.getsize(sal) // 1024} KB', flush=True)
            time.sleep(1)
    else:
        for g in M.grupos_de_mapa(items):
            if a.solo and g["clave"] != a.solo:
                continue
            bb, esc = M.region_visible(g)
            datos, sal = guardar(a.salida, g["clave"], "recuadro", bb, M.capas_para(esc))
            print(f'{g["clave"]}: {len(g["items"])} sistemas | {esc:.2f} px/m | capas {"".join(c + ":" + str(len(v)) + " " for c, v in datos.items())}| {os.path.getsize(sal) // 1024} KB', flush=True)
            time.sleep(1)
