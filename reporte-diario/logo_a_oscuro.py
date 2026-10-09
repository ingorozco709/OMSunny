"""Convierte logo_sunny_original.png (fondo claro, texto oscuro) en logo_sunny.png: fondo transparente y textos aclarados
para que se lea sobre el fondo oscuro del reporte. Solo biblioteca estándar. Uso: python3 -I logo_a_oscuro.py [original.png] [salida.png]"""
import sys, os, struct, zlib, colorsys

def leer_png(ruta):
    d = open(ruta, "rb").read(); pos = 8; idat = b""
    while pos < len(d):
        ln, = struct.unpack(">I", d[pos:pos + 4]); tipo = d[pos + 4:pos + 8]; cuerpo = d[pos + 8:pos + 8 + ln]
        if tipo == b"IHDR": w, h, bd, ct, _, _, il = struct.unpack(">IIBBBBB", cuerpo)
        if tipo == b"IDAT": idat += cuerpo
        pos += 12 + ln
    assert bd == 8 and ct == 6 and il == 0, "se espera PNG RGBA de 8 bits sin entrelazado"
    raw = zlib.decompress(idat); bpp = 4; stride = w * bpp; filas = []; prev = bytearray(stride); p = 0
    for _ in range(h):
        f = raw[p]; linea = bytearray(raw[p + 1:p + 1 + stride]); p += 1 + stride
        for i in range(stride):
            a = linea[i - bpp] if i >= bpp else 0; b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
            if f == 1: linea[i] = (linea[i] + a) & 255
            elif f == 2: linea[i] = (linea[i] + b) & 255
            elif f == 3: linea[i] = (linea[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                pa = abs(b - c); pb = abs(a - c); pc = abs(a + b - 2 * c)
                linea[i] = (linea[i] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 255
        filas.append(linea); prev = linea
    return w, h, filas

def escribir_png(ruta, w, h, filas):
    raw = b"".join(b"\x00" + bytes(f) for f in filas)
    def trozo(t, b): return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xffffffff)
    open(ruta, "wb").write(b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + trozo(b"IDAT", zlib.compress(raw, 9)) + trozo(b"IEND", b""))

def main(entrada, salida):
    w, h, filas = leer_png(entrada)
    px = [[tuple(f[4 * x:4 * x + 3]) for x in range(w)] for f in filas]
    bg = px[0][0]
    dist = lambda c: max(abs(c[0] - bg[0]), abs(c[1] - bg[1]), abs(c[2] - bg[2]))
    out = [[(0, 0, 0, 0)] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            c = px[y][x]; d = dist(c)
            if d < 8: continue
            # color real del trazo: el vecino (3x3) más alejado del fondo; la opacidad es la fracción de mezcla con el fondo
            fg = max((px[j][i] for j in range(max(0, y - 1), min(h, y + 2)) for i in range(max(0, x - 1), min(w, x + 2))), key=dist)
            a = min(1.0, d / max(dist(fg), 1)); col = c if a >= 0.98 else fg
            hh, s, v = colorsys.rgb_to_hsv(col[0] / 255, col[1] / 255, col[2] / 255)
            if s < 0.25 and v < 0.85:                      # texto gris "Powered by PROMIGAS" -> gris claro
                r, g, b = 224, 231, 236
            elif 0.40 < hh < 0.62 and s >= 0.25:            # texto turquesa "Sunny" -> turquesa más claro, conserva el degradado
                r, g, b = (int(round(255 * k)) for k in colorsys.hsv_to_rgb(hh, min(1.0, s * 0.62), min(1.0, 0.50 + v * 0.72)))
            else:                                           # sol naranja: sin cambios
                r, g, b = col
            out[y][x] = (r, g, b, int(round(255 * a)))
    xs = [x for row in out for x, p in enumerate(row) if p[3] > 20]; ys = [y for y, row in enumerate(out) for p in row if p[3] > 20]
    x0, x1, y0, y1 = max(0, min(xs) - 2), min(w - 1, max(xs) + 2), max(0, min(ys) - 2), min(h - 1, max(ys) + 2)
    filas_out = [bytearray(b for p in out[y][x0:x1 + 1] for b in p) for y in range(y0, y1 + 1)]
    escribir_png(salida, x1 - x0 + 1, y1 - y0 + 1, filas_out)
    print("logo", x1 - x0 + 1, "x", y1 - y0 + 1, "->", salida)

if __name__ == "__main__":
    aqui = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(aqui, "logo_sunny_original.png"),
         sys.argv[2] if len(sys.argv) > 2 else os.path.join(aqui, "logo_sunny.png"))
