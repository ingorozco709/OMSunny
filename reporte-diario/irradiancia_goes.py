"""Irradiancia en superficie observada por satélite en las coordenadas de cada sistema (NOAA GOES-19, producto ABI-L2-DSRF: radiación de onda corta
descendente, disco completo, un escaneo cada 10 min, píxeles de ~2 km). Lee solo los píxeles necesarios con peticiones HTTP por rangos al bucket público
noaa-goes19 (no baja los archivos de ~40 MB). Solo lectura de internet y de Metrum.

Regla del equipo (4-nov, a pedido del usuario): la irradiancia de un sistema sale de **sus coordenadas** (atributos `latDev` y `lonDev` del gateway de la casa en Metrum), no de
un punto por ciudad escrito a mano. Hasta el 4-nov el análisis de curtailment usaba cuatro puntos fijos (Cali, Turbaco, Barranquilla y Cartagena); con las coordenadas de los 49 sistemas
salen 9 píxeles distintos y los puntos de Barranquilla y Cartagena estaban a 4 y 14 km de los sistemas (ver `om-agency/references/reglas-aprendidas.md`). Las coordenadas son
ubicaciones de viviendas de clientes: los archivos de salida van fuera del repositorio y no se publican.

Requiere `pip install h5py requests numpy` (no hacen falta para el reporte diario). Uso:
    python3 reporte-diario/irradiancia_goes.py --desde 2026-10-01 --hasta 2026-10-20 --salida /ruta/irr_sistemas          # sitios: los sistemas del reporte, con sus coordenadas de Metrum
    python3 reporte-diario/irradiancia_goes.py --desde 2026-10-01 --hasta 2026-10-01 --sitios sitios.json --salida ...    # sitios a mano: {"nombre": [lat, lon], ...}
Escribe `pixeles.json` (píxel de cada sitio) y un `goes_AAAA-MM-DD.json` por día, reanudable: una lista de escaneos {ini, fin, v: {sitio: [W/m², píxeles válidos]}}, con la media de una
ventana de 3 × 3 píxeles (~6 km) alrededor del píxel del sitio, como en el análisis de curtailment. `irradiacion_diaria()` los pasa a kWh/m² por día.
Los escaneos se piden de 10:00 a 23:59 UTC (05:00 a 18:59 hora de Bogotá). En un reporte, ver `s["lat"]` y `s["lon"]` de cada sistema."""
import os, sys, io, re, math, json, time, argparse, threading, datetime as dt, concurrent.futures as cf

BUCKET = "https://noaa-goes19.s3.amazonaws.com/"
PRODUCTO = "ABI-L2-DSRF"
HERE = os.path.dirname(os.path.abspath(__file__))
_S = threading.local()
_GEO = {}


def _libs():
    try:
        import requests, h5py, numpy
    except ImportError as e:
        sys.exit(f"falta una librería ({e.name}): pip install h5py requests numpy")
    return requests, h5py, numpy


def _sesion():
    requests, _, _ = _libs()
    if not hasattr(_S, "s"):
        _S.s = requests.Session()
    return _S.s


def listar(prefijo):
    """[(clave, tamaño)] de los archivos del bucket con ese prefijo (p. ej. 'ABI-L2-DSRF/2026/274/17/')."""
    requests, _, _ = _libs()
    out, tok = [], None
    while True:
        u = BUCKET + "?list-type=2&prefix=" + prefijo + (("&continuation-token=" + requests.utils.quote(tok, safe="")) if tok else "")
        r = _sesion().get(u, timeout=60)
        r.raise_for_status()
        out += [(k, int(s)) for k, s in re.findall(r"<Key>([^<]+)</Key>.*?<Size>(\d+)</Size>", r.text)]
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", r.text)
        if not m:
            return out
        tok = m.group(1)


class ArchivoHttp(io.RawIOBase):
    """Archivo remoto de solo lectura con caché de bloques (h5py lee solo lo que necesita)."""
    BLOQUE = 1 << 18

    def __init__(self, clave, tam):
        self.url, self.tam, self.pos, self.cache, self.bytes_leidos = BUCKET + clave, tam, 0, {}, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.tam + off)
        return self.pos

    def _bloque(self, i):
        if i not in self.cache:
            a, b = i * self.BLOQUE, min(self.tam, (i + 1) * self.BLOQUE) - 1
            for intento in range(4):
                try:
                    r = _sesion().get(self.url, headers={"Range": f"bytes={a}-{b}"}, timeout=90)
                    if r.status_code in (200, 206):
                        break
                except Exception:
                    pass
                time.sleep(1.5 * (intento + 1))
            else:
                raise IOError("no se pudo leer el rango de " + self.url)
            self.cache[i] = r.content if r.status_code == 206 else r.content[a:b + 1]
            self.bytes_leidos += len(self.cache[i])
        return self.cache[i]

    def readinto(self, buf):
        n = len(buf)
        fin = min(self.tam, self.pos + n)
        if self.pos >= fin:
            return 0
        out = bytearray()
        for i in range(self.pos // self.BLOQUE, (fin - 1) // self.BLOQUE + 1):
            blq = self._bloque(i)
            out += blq[max(self.pos, i * self.BLOQUE) - i * self.BLOQUE: min(fin, (i + 1) * self.BLOQUE) - i * self.BLOQUE]
        buf[:len(out)] = out
        self.pos += len(out)
        return len(out)


def _a(x):
    import numpy as np
    return float(np.asarray(x).ravel()[0])      # los atributos de netCDF llegan como arreglos de un elemento


def _pixel(f, lat, lon):
    """(fila, columna) del píxel de la rejilla fija de GOES-R más cercano a (lat, lon). Fórmulas de la guía del usuario GOES-R (PUG)."""
    import numpy as np
    p = f["goes_imager_projection"].attrs
    req, rpol, H0, lo0 = _a(p["semi_major_axis"]), _a(p["semi_minor_axis"]), _a(p["perspective_point_height"]), math.radians(_a(p["longitude_of_projection_origin"]))
    H = H0 + req
    phi, lam = math.radians(lat), math.radians(lon)
    e2 = (req ** 2 - rpol ** 2) / req ** 2
    phic = math.atan((rpol ** 2 / req ** 2) * math.tan(phi))
    rc = rpol / math.sqrt(1 - e2 * math.cos(phic) ** 2)
    sx = H - rc * math.cos(phic) * math.cos(lam - lo0)
    sy = -rc * math.cos(phic) * math.sin(lam - lo0)
    sz = rc * math.sin(phic)
    y = math.atan(sz / sx)
    x = math.asin(-sy / math.sqrt(sx ** 2 + sy ** 2 + sz ** 2))
    xs = f["x"][:].astype("float64") * _a(f["x"].attrs["scale_factor"]) + _a(f["x"].attrs["add_offset"])
    ys = f["y"][:].astype("float64") * _a(f["y"].attrs["scale_factor"]) + _a(f["y"].attrs["add_offset"])
    return int(np.argmin(np.abs(ys - y))), int(np.argmin(np.abs(xs - x)))


def extraer(clave, tam, sitios, radio=1):
    """{sitio: (media de DSR en W/m² de la ventana de (2·radio+1)² píxeles o None, píxeles válidos)} de un escaneo. La rejilla es fija: el píxel de cada sitio se calcula una vez."""
    _, h5py, np = _libs()
    af = ArchivoHttp(clave, tam)
    with h5py.File(af, "r") as f:
        if not _GEO:
            for s, (la, lo) in sitios.items():
                _GEO[s] = _pixel(f, la, lo)
        d = f["DSR"]
        q = f["DQF"] if "DQF" in f else None
        esc, off, fill = _a(d.attrs.get("scale_factor", 1.0)), _a(d.attrs.get("add_offset", 0.0)), d.attrs.get("_FillValue", None)
        out = {}
        for s, (i, j) in _GEO.items():
            raw = np.array(d[i - radio:i + radio + 1, j - radio:j + radio + 1], dtype="float64")
            ok = np.ones(raw.shape, bool) if fill is None else (raw != _a(fill))
            if np.issubdtype(d.dtype, np.floating):
                ok &= np.isfinite(raw)
            val = raw * esc + off
            ok &= (val >= 0) & (val < 1500)
            if q is not None:
                ok &= (np.array(q[i - radio:i + radio + 1, j - radio:j + radio + 1]) == 0)
            out[s] = (float(val[ok].mean()) if ok.any() else None, int(ok.sum()))
    return out


def _t(clave, marca="s"):
    a, doy, h, mi, s, dec = (int(x) for x in re.search(r"_" + marca + r"(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})(\d)_", clave).groups())
    return dt.datetime(a, 1, 1) + dt.timedelta(days=doy - 1, hours=h, minutes=mi, seconds=s + dec / 10)


def descargar(desde, hasta, sitios, salida, horas_utc=(10, 23), hilos=8):
    """Un JSON por día en `salida` (se salta los que ya existen). `sitios` = {nombre: (lat, lon)}."""
    os.makedirs(salida, exist_ok=True)

    def uno(arg):
        clave, tam = arg
        err = ""
        for _ in range(3):
            try:
                r = extraer(clave, tam, sitios)
                return dict(ini=_t(clave).isoformat(), fin=_t(clave, "e").isoformat(), v={s: [round(x[0], 1) if x[0] is not None else None, x[1]] for s, x in r.items()})
            except Exception as ex:
                err = str(ex)[:120]
                time.sleep(2)
        return dict(ini=_t(clave).isoformat(), fin=_t(clave, "e").isoformat(), error=err)

    d = desde
    while d <= hasta:
        sal = os.path.join(salida, f"goes_{d.isoformat()}.json")
        if not os.path.exists(sal):
            archivos = []
            for hh in range(horas_utc[0], horas_utc[1] + 1):
                archivos += listar(f"{PRODUCTO}/{d.year}/{d.timetuple().tm_yday:03d}/{hh:02d}/")
            if not _GEO:                                    # el píxel de cada sitio sale del primer archivo
                extraer(*archivos[0], sitios)
                json.dump({k: list(v) for k, v in _GEO.items()}, open(os.path.join(salida, "pixeles.json"), "w"))
            with cf.ThreadPoolExecutor(hilos) as ex:
                res = sorted(ex.map(uno, archivos), key=lambda r: r["ini"])
            json.dump(res, open(sal, "w"))
            print(d.isoformat(), "escaneos", len(res), "con error", sum(1 for r in res if "error" in r), flush=True)
        d += dt.timedelta(days=1)


def irradiacion_diaria(salida, sitio):
    """{fecha: kWh/m²} de un sitio con los escaneos de la carpeta de salida (cada escaneo vale 10 min; solo cuentan las horas pedidas: 05:00 a 18:59 de Bogotá)."""
    out = {}
    for nombre in sorted(os.listdir(salida)):
        m = re.match(r"goes_(\d{4}-\d{2}-\d{2})\.json$", nombre)
        if not m:
            continue
        esc = json.load(open(os.path.join(salida, nombre)))
        out[m.group(1)] = sum(e["v"][sitio][0] for e in esc if "v" in e and e["v"].get(sitio, [None])[0] is not None) / 6 / 1000
    return out


def sitios_del_reporte():
    """{casa: (lat, lon)} de los sistemas del reporte, con las coordenadas del gateway en Metrum (requiere METRUM_API_URL, METRUM_USERNAME y METRUM_PASSWORD)."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import reporte_diario as rd
    devs = rd.listar_dispositivos()
    with cf.ThreadPoolExecutor(8) as ex:
        attrs = {dv["id"]["id"]: a for dv, a in ex.map(rd.atributos, devs)}
    kwp = json.load(open(os.path.join(HERE, "potencia_instalada.json")))
    return {s["casa"]: (s["lat"], s["lon"]) for s in rd.construir_sistemas(devs, attrs).values() if s["lat"] is not None and s["casa"].strip().lower() in kwp}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta", required=True)
    ap.add_argument("--salida", required=True, help="carpeta fuera del repositorio (las coordenadas son de viviendas de clientes)")
    ap.add_argument("--sitios", help="JSON {nombre: [lat, lon]}; si falta, los sistemas del reporte con sus coordenadas de Metrum")
    ap.add_argument("--hilos", type=int, default=8)
    a = ap.parse_args()
    if os.path.exists("/root/.ccr/ca-bundle.crt"):
        os.environ.setdefault("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
    sitios = {k: tuple(v) for k, v in json.load(open(a.sitios)).items()} if a.sitios else sitios_del_reporte()
    descargar(dt.date.fromisoformat(a.desde), dt.date.fromisoformat(a.hasta), sitios, a.salida, hilos=a.hilos)
