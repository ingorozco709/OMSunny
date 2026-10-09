"""Vectoriza el logo oficial (logo_sunny_original.png, fondo claro y textos oscuros) a logo_sunny.svg para el fondo oscuro de los reportes:
sol y "Sunny" trazados como curvas suaves con su degradado (turquesa aclarado) y "Powered by PROMIGAS" como texto real. Se ve nítido en cualquier tamaño.
Requiere: pip install pillow numpy potracer. Uso: python3 logo_a_vectorial.py [original.png] [salida.svg]
Si se dispone del logo en SVG o en PNG de mayor resolución, conviene usarlo directamente (reemplazar logo_sunny.svg)."""
import sys, os, re, colorsys
for _p in ("/tmp/pylibs",):
    if os.path.isdir(_p): sys.path.insert(0, _p)
import numpy as np
from PIL import Image, ImageFilter
import potrace

ENTRADA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_sunny_original.png")
SALIDA = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_sunny.svg")
SC = 4
img = Image.open(ENTRADA).convert('RGBA')
a = np.asarray(img).astype(np.float32); H, W = a.shape[:2]
rgb = a[..., :3]; bg = rgb[0, 0]
dist = np.abs(rgb - bg).max(axis=2)
pad = np.pad(dist, 1, mode='edge'); padc = np.pad(rgb, ((1,1),(1,1),(0,0)), mode='edge')
best = dist.copy(); fg = rgb.copy()
for dy in (-1,0,1):
    for dx in (-1,0,1):
        d2 = pad[1+dy:1+dy+H, 1+dx:1+dx+W]; c2 = padc[1+dy:1+dy+H, 1+dx:1+dx+W]
        m = d2 > best; best = np.where(m, d2, best); fg = np.where(m[..., None], c2, fg)
alpha = np.clip(dist / np.maximum(best, 1), 0, 1); alpha[dist < 8] = 0
col = np.where((alpha >= 0.98)[..., None], rgb, fg)
r, g, b = col[...,0]/255, col[...,1]/255, col[...,2]/255
mx = np.maximum(np.maximum(r,g),b); mn = np.minimum(np.minimum(r,g),b); dv = mx-mn
v = mx; s = np.where(mx>0, dv/np.maximum(mx,1e-6), 0)
rc = np.where((dv>1e-6) & (mx==r), ((g-b)/np.maximum(dv,1e-6)) % 6, 0)
gc = np.where((dv>1e-6) & (mx==g) & (mx!=r), (b-r)/np.maximum(dv,1e-6)+2, 0)
bc = np.where((dv>1e-6) & (mx==b) & (mx!=r) & (mx!=g), (r-g)/np.maximum(dv,1e-6)+4, 0)
h = ((rc+gc+bc)/6.0) % 1.0
gris = (s < 0.25) & (v < 0.85); teal = (~gris) & (h > 0.40) & (h < 0.62) & (s >= 0.25); sol = ~(gris | teal)
vis = alpha > 0.05
ys, xs = np.where(vis & (alpha > 0.2)); x0, x1, y0, y1 = max(0, xs.min()-2), min(W-1, xs.max()+2), max(0, ys.min()-2), min(H-1, ys.max()+2)
cw, ch = x1-x0+1, y1-y0+1
print('crop', cw, ch)
# --- linea pequena "Powered by PROMIGAS": filas inferiores del wordmark
nonsun = (teal | gris) & vis & (alpha > 0.3)
rowsum = nonsun[:, :].sum(axis=1)
# buscar hueco de filas entre "Sunny" y la linea pequena (en la mitad derecha)
right = np.zeros_like(nonsun); right[:, 128+x0:300+x0] = nonsun[:, 128+x0:300+x0]   # columnas de "Sun" y de la linea pequena (sin el descenso de la "y")
rs = right.sum(axis=1)
rows = [y for y in range(y0, y1+1) if rs[y] > 0]
grupos = []; ini = rows[0]; prev = rows[0]
for y in rows[1:]:
    if y != prev + 1: grupos.append((ini, prev)); ini = y
    prev = y
grupos.append((ini, prev)); print('grupos de filas (abs)', grupos, 'y0', y0)
ysplit = grupos[-1][0]  # inicio de la linea pequena
small = right.copy(); small[:ysplit, :] = False
sys_, sxs_ = np.where(small); print('linea pequena bbox x', sxs_.min()-x0, sxs_.max()-x0, 'y', sys_.min()-y0, sys_.max()-y0)
# columnas ocupadas -> palabras
colsum = small.sum(axis=0); cols = [x for x in range(W) if colsum[x] > 0]
gr = []; ini = cols[0]; prev = cols[0]
for x in cols[1:]:
    if x > prev + 2: gr.append((ini-x0, prev-x0)); ini = x
    prev = x
gr.append((ini-x0, prev-x0)); print('palabras (x)', gr)
# altura de mayusculas: PROMIGAS = ultimo grupo
last0, last1 = gr[-1]
mm = small[:, last0+x0:last1+x0+1]; yy = np.where(mm.any(axis=1))[0]
print('PROMIGAS y', yy.min()-y0, yy.max()-y0)
pickle_info = dict(cw=cw, ch=ch, small=(sxs_.min()-x0, sxs_.max()-x0, sys_.min()-y0, sys_.max()-y0), words=gr, caps=(yy.min()-y0, yy.max()-y0))
# --- capas a trazar
masks = {'sol': sol & vis, 'teal': teal & vis}
masks['teal'] = masks['teal'].copy(); masks['teal'][ysplit:, :] = False
paths = {}
for name, mk in masks.items():
    al = (alpha * mk)[y0:y1+1, x0:x1+1]
    im = Image.fromarray((al*255).astype(np.uint8), 'L').resize((cw*SC, ch*SC), Image.LANCZOS).filter(ImageFilter.GaussianBlur(SC*0.55))
    bm = potrace.Bitmap(np.asarray(im) <= (135 if name == 'sol' else 118))
    plist = bm.trace(turdsize=30, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY, alphamax=1.15, opticurve=True, opttolerance=0.5)
    d = []
    f = lambda p: f'{p.x/SC:.2f} {p.y/SC:.2f}'
    for curve in plist:
        d.append(f'M{f(curve.start_point)}')
        for seg in curve.segments:
            if seg.is_corner: d.append(f'L{f(seg.c)}L{f(seg.end_point)}')
            else: d.append(f'C{f(seg.c1)} {f(seg.c2)} {f(seg.end_point)}')
        d.append('Z')
    paths[name] = ''.join(d); print(name, len(plist), 'curvas', len(paths[name]), 'bytes')
# colores degradado (originales) por extremos
def ext(mk, left):
    ys_, xs_ = np.where(mk & (alpha > 0.95)); lo, hi = xs_.min(), xs_.max(); sp = hi-lo
    sel = (xs_ <= lo+sp*0.12) if left else (xs_ >= hi-sp*0.12)
    return col[ys_[sel], xs_[sel]].mean(axis=0), lo-x0, hi-x0
grad = {}
for name in ('sol','teal'):
    cl, lo, hi = ext(masks[name], True); cr, _, _ = ext(masks[name], False); grad[name] = (cl, cr, lo, hi); print(name, cl.astype(int), cr.astype(int), lo, hi)


cw, ch = pickle_info['cw'], pickle_info['ch']
def aclarar(c):
    h, s, v = colorsys.rgb_to_hsv(c[0]/255, c[1]/255, c[2]/255)
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s*0.62), min(1.0, 0.50 + v*0.72))
    return '#%02x%02x%02x' % (round(255*r), round(255*g), round(255*b))
hexs = lambda c: '#%02x%02x%02x' % tuple(int(round(x)) for x in c)
sl, sr, sx0, sx1 = grad['sol']; tl, tr, tx0, tx1 = grad['teal']
sx0_, sx1_, sy0_, sy1_ = pickle_info['small']
cap0, cap1 = pickle_info['caps']
ancho = sx1_ - sx0_ + 1
fs = round((cap1 - cap0 + 1) / 0.70, 1)
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cw} {ch}" width="{cw}" height="{ch}" role="img" aria-label="Sunny, powered by Promigas">'
  f'<defs><linearGradient id="gs" gradientUnits="userSpaceOnUse" x1="{sx0}" y1="0" x2="{sx1}" y2="0"><stop offset="0" stop-color="{hexs(sl)}"/><stop offset="1" stop-color="{hexs(sr)}"/></linearGradient>'
  f'<linearGradient id="gt" gradientUnits="userSpaceOnUse" x1="{tx0}" y1="0" x2="{tx1}" y2="0"><stop offset="0" stop-color="{aclarar(tl)}"/><stop offset="1" stop-color="{aclarar(tr)}"/></linearGradient></defs>'
  f'<path fill="url(#gs)" fill-rule="evenodd" d="{paths["sol"]}"/>'
  f'<path fill="url(#gt)" fill-rule="evenodd" d="{paths["teal"]}"/>'
  f'<text x="{sx0_}" y="{cap1 - 0.5}" font-family="Montserrat, \'Avenir Next\', \'Segoe UI\', Helvetica, Arial, sans-serif" font-size="{fs}" textLength="{ancho}" lengthAdjust="spacingAndGlyphs" fill="#d9e1e7">'
  f'<tspan font-weight="500">Powered by </tspan><tspan font-weight="700" fill="#f1f5f7">PROMIGAS</tspan></text>'
  '</svg>')
open(SALIDA, 'w', encoding='utf-8').write(svg); print('logo vectorial', len(svg), 'bytes ->', SALIDA)
