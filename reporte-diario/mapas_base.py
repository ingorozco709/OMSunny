"""Mapas base del mapa de sistemas: baja de OpenStreetMap lo que se ve en cada recuadro y lo guarda en `mapas_base/<recuadro>.json`.

Datos © colaboradores de OpenStreetMap (ODbL, https://www.openstreetmap.org/copyright): calles, edificios, piscinas, agua y zonas verdes, como vectores simplificados. El reporte los dibuja
debajo de los puntos (`mapa_sistemas.py`) sin pedir nada a internet; si falta el archivo de un recuadro, ese recuadro sale con rejilla en vez de mapa base.

Se corre una vez y de nuevo solo cuando cambia la lista de recuadros (una casa en un conjunto nuevo, un conjunto que pasa de 2 a 3 casas) o si se quiere refrescar el mapa:
    python3 reporte-diario/mapas_base.py [--salida reporte-diario/mapas_base] [--solo cali-reservas-de-pance]
Lee de Metrum las coordenadas de los gateways (METRUM_API_URL, METRUM_USERNAME y METRUM_PASSWORD) y hace unas pocas peticiones a la API de OpenStreetMap (una por recuadro; se parte la
caja si tiene demasiados nodos). Uso moderado, como pide la política de OpenStreetMap: no se descarga nada al generar el reporte diario.
Los archivos no traen las casas ni sus coordenadas: solo el entorno de cada recuadro."""
import os, sys, json, time, argparse, datetime as dt, urllib.request, urllib.error

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


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--salida", default=os.path.join(HERE, "mapas_base"))
    ap.add_argument("--solo", help="clave de un recuadro (p. ej. cali-reservas-de-pance); por defecto, todos")
    a = ap.parse_args()
    if os.path.exists("/root/.ccr/ca-bundle.crt"):
        os.environ.setdefault("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt")
    os.makedirs(a.salida, exist_ok=True)
    for g in M.grupos_de_mapa(items_del_reporte()):
        if a.solo and g["clave"] != a.solo:
            continue
        bb, esc = M.region_visible(g)
        capas = M.capas_para(esc)
        els = descargar(bb)
        datos = a_capas(els, capas)
        sal = os.path.join(a.salida, g["clave"] + ".json")
        with open(sal, "w", encoding="utf-8") as f:
            json.dump({"clave": g["clave"], "fuente": "OpenStreetMap", "licencia": "ODbL", "fecha": dt.date.today().isoformat(), "bbox": [round(x, 6) for x in bb], "capas": datos}, f, separators=(",", ":"))
        print(f'{g["clave"]}: {len(g["items"])} sistemas | {esc:.2f} px/m | capas {"".join(c + ":" + str(len(v)) + " " for c, v in datos.items())}| {os.path.getsize(sal) // 1024} KB', flush=True)
        time.sleep(1)
