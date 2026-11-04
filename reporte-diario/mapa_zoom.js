/* Mapa único con zoom de los sistemas: canvas 2D, sin librerías ni teselas (los vectores de OpenStreetMap vienen en el elemento script de clase mz-datos que arma mapa_zoom.py).
   Proyección Web Mercator con el centro y el zoom (fraccional) de la vista; a cada nivel de zoom se dibujan las capas que se distinguen; los puntos que se tocan se agrupan. */
(function () {
  'use strict';
  var bloque = document.querySelector('.mz-bloque');
  if (!bloque) return;
  var lienzo = bloque.querySelector('.mz-lienzo'), cv = lienzo.querySelector('canvas'), cx = cv.getContext('2d');
  var tipEl = lienzo.querySelector('.mz-tip'), avisoEl = lienzo.querySelector('.mz-aviso');
  var D;
  try { D = JSON.parse(bloque.querySelector('.mz-datos').textContent); } catch (err) { return; }

  var PI = Math.PI, TAU = 2 * PI, ZMIN = 5.5, ZMAX = 20.4, M_EC = 40075016.686;
  var reducir = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  /* colores del tema: el reporte define los tokens en :root */
  var cs = getComputedStyle(bloque);
  function tok(n, d) { var v = cs.getPropertyValue(n).trim(); return v || d; }
  var C = { bg: tok('--bg', '#0f1317'), sup: tok('--surface', '#161b20'), ink: tok('--ink', '#e7edf1'), ink2: tok('--ink2', '#b0bcc5'), mut: tok('--muted', '#93a1ac'),
            lin: tok('--line', '#29323a'), acc: tok('--accent', '#78b8e3'), bien: tok('--good', '#38b838'), ser: tok('--ser', '#ec835a') };
  var EST = { c: tok('--crit', '#d03b3b'), s: C.ser, w: tok('--warn', '#fab219'), o: tok('--off-ink', '#b6c1ca'), g: C.bien };
  var FM = tok('--f-m', 'monospace'), FB = tok('--f-b', 'sans-serif');
  var NIV = ['c', 's', 'w', 'o', 'g'];                                          // de más a menos grave

  /* ---------- proyección y datos ---------- */
  function pu(lon) { return (lon + 180) / 360; }
  function pv(lat) { var s = Math.sin(lat * PI / 180); return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * PI); }
  function latDe(v) { return Math.atan(Math.sinh(PI * (1 - 2 * v))) * 180 / PI; }
  function decodificar(plano) {                                                  // [lat0, lon0, dlat, dlon, ...] en millonésimas de grado -> unidades del mundo
    var n = plano.length >> 1, p = new Float64Array(n * 2), la = 0, lo = 0, u0 = 2, v0 = 2, u1 = -1, v1 = -1;
    for (var k = 0; k < n; k++) {
      la += plano[2 * k]; lo += plano[2 * k + 1];
      var u = pu(lo / 1e6), v = pv(la / 1e6);
      p[2 * k] = u; p[2 * k + 1] = v;
      if (u < u0) u0 = u; if (u > u1) u1 = u; if (v < v0) v0 = v; if (v > v1) v1 = v;
    }
    return { p: p, b: [u0, v0, u1, v1] };
  }
  var CAPAS = {};
  Object.keys(D.capas || {}).forEach(function (k) { CAPAS[k] = D.capas[k].map(decodificar); });
  var TIERRA = (D.tierra || []).map(decodificar);
  var LUGARES = (D.lugares || []).map(function (l) { return { n: l[0], u: pu(l[2]), v: pv(l[1]) }; });
  var VIST = D.v.map(function (x) { return x[0]; }), vi = 0;
  var CASAS = D.casas.map(function (c, i) {
    return { i: i, c: c.c, k: c.k, l: c.l, lg: !!c.lg, z: c.z, ci: c.ci, u: pu(c.lo), v: pv(c.la), n: c.n, t: c.t, sb: !!c.sb, rs: !!c.rs };
  });
  function nivel(c) { return c.n.charAt(vi); }

  /* ---------- vista ---------- */
  var V = { u: 0.5, v: 0.5, z: 7 }, W = 0, H = 0, dpr = 1, sucio = false, anim = null, dib = [], sel = null;
  function esc() { return 256 * Math.pow(2, V.z); }
  function acotar() { V.z = Math.max(ZMIN, Math.min(ZMAX, V.z)); V.u = Math.max(0, Math.min(1, V.u)); V.v = Math.max(0.02, Math.min(0.98, V.v)); }
  function cajaDe(lista) {
    var u0 = 2, v0 = 2, u1 = -1, v1 = -1;
    lista.forEach(function (c) { u0 = Math.min(u0, c.u); u1 = Math.max(u1, c.u); v0 = Math.min(v0, c.v); v1 = Math.max(v1, c.v); });
    return { u0: u0, v0: v0, u1: u1, v1: v1 };
  }
  function ajustar(caja, pad, minM) {                                            // vista que deja la caja completa en el lienzo (con al menos minM metros de ancho)
    var lat = latDe((caja.v0 + caja.v1) / 2), minU = (minM || 260) / (M_EC * Math.cos(lat * PI / 180));
    var w = Math.max(caja.u1 - caja.u0, minU), h = Math.max(caja.v1 - caja.v0, minU);
    var zx = Math.log((W - 2 * pad) / (256 * w)) / Math.LN2, zy = Math.log((H - 2 * pad) / (256 * h)) / Math.LN2;
    return { u: (caja.u0 + caja.u1) / 2, v: (caja.v0 + caja.v1) / 2, z: Math.max(ZMIN, Math.min(ZMAX, Math.min(zx, zy))) };
  }
  function zoomEn(px, py, dz) {                                                  // el punto bajo (px, py) se queda quieto
    var z1 = Math.max(ZMIN, Math.min(ZMAX, V.z + dz)), S0 = esc(), S1 = 256 * Math.pow(2, z1);
    var u = V.u + (px - W / 2) / S0, v = V.v + (py - H / 2) / S0;
    V.z = z1; V.u = u - (px - W / 2) / S1; V.v = v - (py - H / 2) / S1; acotar();
  }
  function pedir() { if (!sucio) { sucio = true; requestAnimationFrame(cuadro); } }
  function cuadro(ahora) {
    sucio = false;
    if (anim) {
      var t = Math.max(0, Math.min(1, (ahora - anim.t0) / anim.ms)), e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      V.u = anim.a.u + (anim.b.u - anim.a.u) * e; V.v = anim.a.v + (anim.b.v - anim.a.v) * e; V.z = anim.a.z + (anim.b.z - anim.a.z) * e;
      if (t >= 1) anim = null;
    }
    dibujar();
    if (anim) pedir();
  }
  function ir(dest, ms) {
    ocultarTip();
    if (reducir || !ms) { V.u = dest.u; V.v = dest.v; V.z = dest.z; acotar(); anim = null; pedir(); return; }
    anim = { a: { u: V.u, v: V.v, z: V.z }, b: dest, t0: performance.now(), ms: ms }; pedir();
  }

  /* ---------- dibujo ---------- */
  function trazar(lista, cerrada, S, minPx) {                                    // un solo camino con todas las geometrías visibles de la capa
    var W2 = W / 2, H2 = H / 2, uc = V.u, vc = V.v, n = 0;
    cx.beginPath();
    for (var i = 0; i < lista.length; i++) {
      var it = lista[i], b = it.b, bx0 = W2 + (b[0] - uc) * S, bx1 = W2 + (b[2] - uc) * S, by0 = H2 + (b[1] - vc) * S, by1 = H2 + (b[3] - vc) * S;
      if (bx1 < -30 || bx0 > W + 30 || by1 < -30 || by0 > H + 30) continue;
      if (bx1 - bx0 < minPx && by1 - by0 < minPx) continue;
      var p = it.p, m = p.length, lx = W2 + (p[0] - uc) * S, ly = H2 + (p[1] - vc) * S;
      cx.moveTo(lx, ly);
      for (var k = 2; k < m; k += 2) {
        var x = W2 + (p[k] - uc) * S, y = H2 + (p[k + 1] - vc) * S;
        if (Math.abs(x - lx) + Math.abs(y - ly) < 0.8 && k < m - 2) continue;
        cx.lineTo(x, y); lx = x; ly = y;
      }
      if (cerrada) cx.closePath();
      n++;
    }
    return n;
  }
  /* [capa, aparece en el zoom, opacidad plena en el zoom, cerrada, tamaño mínimo en px] de abajo hacia arriba */
  var CAP = [['u', 15.2, 16.2, true, 2], ['v', 11.2, 12.2, true, 2], ['w', 10.8, 11.8, true, 2], ['wl', 11.2, 12.2, false, 4], ['p', 16.3, 17.2, true, 1], ['e', 15.4, 16.4, true, 1],
             ['f', 17, 17.8, false, 2], ['s', 14.8, 15.8, false, 4], ['r', 12.6, 13.6, false, 4], ['a', 10.8, 12, false, 4]];
  function capasBase(S, z) {
    var t = Math.max(0, Math.min(1, (z - 13) / 5));
    CAP.forEach(function (c) {
      var cod = c[0], lista = CAPAS[cod];
      if (!lista || z < c[1]) return;
      var a = Math.min(1, (z - c[1]) / (c[2] - c[1]));
      if (!trazar(lista, c[3], S, c[4])) return;
      switch (cod) {
        case 'u': cx.fillStyle = C.ink; cx.globalAlpha = 0.04 * a; cx.fill(); break;
        case 'v': cx.fillStyle = C.bien; cx.globalAlpha = 0.12 * a; cx.fill(); break;
        case 'w': cx.fillStyle = C.acc; cx.globalAlpha = 0.22 * a; cx.fill(); break;
        case 'p': cx.fillStyle = C.acc; cx.globalAlpha = 0.4 * a; cx.fill(); break;
        case 'e': cx.fillStyle = C.ink2; cx.globalAlpha = 0.22 * a; cx.fill(); cx.strokeStyle = C.mut; cx.lineWidth = 0.3 + 0.5 * t; cx.globalAlpha = 0.35 * a; cx.stroke(); break;
        case 'wl': cx.strokeStyle = C.acc; cx.lineWidth = 0.9 + 1.4 * t; cx.globalAlpha = 0.4 * a; cx.stroke(); break;
        case 'a': cx.strokeStyle = C.mut; cx.lineWidth = 1 + 3.2 * t; cx.globalAlpha = 0.5 * a; cx.stroke(); break;
        case 'r': cx.strokeStyle = C.mut; cx.lineWidth = 0.7 + 2.3 * t; cx.globalAlpha = 0.42 * a; cx.stroke(); break;
        case 's': cx.strokeStyle = C.mut; cx.lineWidth = 0.5 + 1.5 * t; cx.globalAlpha = 0.32 * a; cx.stroke(); break;
        case 'f': cx.strokeStyle = C.mut; cx.lineWidth = 0.8 + 0.4 * t; cx.globalAlpha = 0.34 * a; cx.setLineDash([2, 2.2]); cx.stroke(); cx.setLineDash([]); break;
      }
    });
    cx.globalAlpha = 1;
  }
  function texto(t, x, y, anc, fuente, col) {                                    // texto con contorno del color del fondo para que se lea sobre el mapa
    cx.font = fuente; cx.textAlign = anc; cx.lineJoin = 'round'; cx.lineWidth = 3.2; cx.strokeStyle = C.bg; cx.strokeText(t, x, y); cx.fillStyle = col; cx.fillText(t, x, y);
  }

  /* agrupa los puntos cuyos círculos se tocarían a este zoom: se van uniendo de a dos (el círculo de un grupo es la rosca) hasta que no quede ninguno encimado.
     Quién va con quién solo depende del zoom y no de dónde está el mapa, así que se calcula una vez por zoom. */
  var memo = { z: -1, P: [] };
  function radio() { return 6.5 + 2.2 * Math.max(0, Math.min(1, (V.z - 16) / 3)); }
  function radioGrupo(n) { return Math.min(30, 12 + 3.2 * Math.sqrt(n)); }
  function pertenencia(S) {
    var P = CASAS.map(function (c) { return { m: [c], x: c.u * S, y: c.v * S, r: radio() + 1 }; }), a, b, hubo = true;
    while (hubo) {
      hubo = false;
      for (a = 0; a < P.length && !hubo; a++) {
        for (b = a + 1; b < P.length; b++) {
          var dx = P[a].x - P[b].x, dy = P[a].y - P[b].y, lim = P[a].r + P[b].r + 2;
          if (dx * dx + dy * dy < lim * lim) {
            var na = P[a].m.length, nb = P[b].m.length, n = na + nb;
            P[a] = { m: P[a].m.concat(P[b].m), x: (P[a].x * na + P[b].x * nb) / n, y: (P[a].y * na + P[b].y * nb) / n, r: radioGrupo(n) };
            P.splice(b, 1); hubo = true; break;
          }
        }
      }
    }
    return P;
  }
  function agrupar(S) {
    if (memo.z !== V.z) { memo = { z: V.z, P: pertenencia(S) }; }
    return memo.P.map(function (p) {
      var cu = { c: 0, s: 0, w: 0, o: 0, g: 0 }, rs = 0, peor = 4, su = 0, sv = 0;
      p.m.forEach(function (c) { var k = nivel(c); cu[k]++; peor = Math.min(peor, NIV.indexOf(k)); if (c.rs) rs++; su += c.u; sv += c.v; });
      var n = p.m.length, u = su / n, v = sv / n;
      return { m: p.m, n: n, x: W / 2 + (u - V.u) * S, y: H / 2 + (v - V.v) * S, cu: cu, rs: rs, peor: peor };
    });
  }
  function nombreGrupo(m) {                                                      // pocas casas: sus números; muchas: el conjunto o la ciudad
    if (m.length <= 3) return m.map(function (c) { return c.k; }).join(' · ');
    var zs = {}, cs2 = {}, nz = 0;
    m.forEach(function (c) { if (!zs[c.z]) { zs[c.z] = 1; nz++; } cs2[c.ci] = 1; });
    if (nz === 1 && m[0].z) return m[0].z;
    return Object.keys(cs2).join(' y ');
  }

  function dibujarPunto(g, marca) {
    var c = g.m[0], k = nivel(c), R = radio(), x = g.x, y = g.y;
    if (c.rs && VIST[vi] === 'e') { cx.beginPath(); cx.arc(x, y, R + 3.4, 0, TAU); cx.strokeStyle = C.ser; cx.lineWidth = 2.4; cx.stroke(); }
    if (c.sb) {                                                                  // casa que solo tiene baterías: rombo
      cx.save(); cx.translate(x, y); cx.rotate(PI / 4); cx.beginPath(); cx.rect(-R * 0.85, -R * 0.85, R * 1.7, R * 1.7);
      cx.fillStyle = EST[k]; cx.fill(); cx.strokeStyle = C.ink2; cx.lineWidth = 1.6; cx.stroke(); cx.restore();
    } else {
      cx.beginPath(); cx.arc(x, y, R, 0, TAU); cx.fillStyle = EST[k]; cx.fill(); cx.strokeStyle = C.sup; cx.lineWidth = 2; cx.stroke();
    }
    if (marca) { cx.beginPath(); cx.arc(x, y, R + 6, 0, TAU); cx.strokeStyle = C.acc; cx.lineWidth = 2; cx.stroke(); }
    return R + (c.rs && VIST[vi] === 'e' ? 3.4 : 0);
  }
  function dibujarGrupo(g, marca) {                                              // rosca con la composición por estado y el número de sistemas
    var R = radioGrupo(g.n), th = Math.max(5, R * 0.27), a0 = -PI / 2, x = g.x, y = g.y;
    cx.lineWidth = th;
    NIV.forEach(function (k) {
      var c = g.cu[k]; if (!c) return;
      var a1 = a0 + TAU * c / g.n;
      cx.beginPath(); cx.arc(x, y, R - th / 2, a0, a1); cx.strokeStyle = EST[k]; cx.stroke(); a0 = a1;
    });
    cx.beginPath(); cx.arc(x, y, R - th, 0, TAU); cx.fillStyle = C.bg; cx.fill();
    cx.beginPath(); cx.arc(x, y, R, 0, TAU); cx.lineWidth = 1.6; cx.strokeStyle = C.sup; cx.stroke();
    cx.font = '600 ' + (R > 22 ? 14 : 12) + 'px ' + FM; cx.textAlign = 'center'; cx.textBaseline = 'middle'; cx.fillStyle = C.ink; cx.fillText(String(g.n), x, y + 0.5); cx.textBaseline = 'alphabetic';
    if (marca) { cx.beginPath(); cx.arc(x, y, R + 4, 0, TAU); cx.strokeStyle = C.acc; cx.lineWidth = 2; cx.stroke(); }
    return R;
  }

  function dibujar() {
    var S = esc(), z = V.z, i;
    cx.setTransform(dpr, 0, 0, dpr, 0, 0); cx.globalAlpha = 1; cx.fillStyle = C.bg; cx.fillRect(0, 0, W, H); cx.lineCap = 'round'; cx.lineJoin = 'round';
    var aT = Math.max(0, Math.min(1, (10.8 - z) / 1.3));                         // contorno de los países, solo de lejos
    if (aT > 0 && TIERRA.length) {
      trazar(TIERRA, true, S, 0);
      cx.globalAlpha = aT; cx.fillStyle = C.sup; cx.fill(); cx.strokeStyle = C.lin; cx.lineWidth = 1; cx.stroke(); cx.globalAlpha = 1;
    }
    capasBase(S, z);
    var G = agrupar(S).filter(function (g) { var q = (g.n > 1 ? radioGrupo(g.n) : 12) + 40; return g.x > -q && g.x < W + q && g.y > -q && g.y < H + q; });
    G.sort(function (a, b) { return b.peor - a.peor; });                         // las más graves se dibujan encima
    var aL = Math.max(0, Math.min(1, 10.4 - z));                                 // ciudades de contexto, de lejos y lejos de los grupos
    if (aL > 0) {
      LUGARES.forEach(function (l) {
        var x = W / 2 + (l.u - V.u) * S, y = H / 2 + (l.v - V.v) * S;
        if (x < 4 || x > W - 60 || y < 14 || y > H - 8) return;
        if (G.some(function (g) { return Math.abs(g.x - x) < 70 && Math.abs(g.y - y) < 34; })) return;
        cx.globalAlpha = aL * 0.9; cx.beginPath(); cx.arc(x, y, 2.2, 0, TAU); cx.fillStyle = C.mut; cx.fill();
        texto(l.n, x + 6, y + 3.5, 'left', '11px ' + FB, C.mut); cx.globalAlpha = 1;
      });
    }
    dib = []; var ocu = [[8, 8, 48, 124]];                                       // zona de los botones de zoom
    var rects = [], grandes = [], etiquetas = [];
    G.forEach(function (g) {
      var marca = sel === g.m[0].i + ':' + g.n, R = g.n > 1 ? dibujarGrupo(g, marca) : dibujarPunto(g, marca);
      dib.push({ x: g.x, y: g.y, r: R, g: g }); ocu.push([g.x - R - 1, g.y - R - 1, g.x + R + 1, g.y + R + 1]);
      if (g.n > 1) grandes.push(g); else rects.push(g);
    });
    var cho = function (a, b) { return !(a[2] <= b[0] || b[2] <= a[0] || a[3] <= b[1] || b[3] <= a[1]); };
    var solape = function (a, b) { return Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) * Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1])); };
    /* nombre de cada grupo: debajo, encima, a la derecha o a la izquierda, donde no tape a otro (primero los más grandes) */
    grandes.sort(function (a, b) { return b.n - a.n; });
    grandes.forEach(function (g) {
      var R = radioGrupo(g.n), nom = nombreGrupo(g.m), x = g.x, y = g.y; cx.font = '600 11.5px ' + FB; var w = cx.measureText(nom).width;
      var cand = [['center', x, y + R + 14, [x - w / 2 - 2, y + R + 3, x + w / 2 + 2, y + R + 18]], ['center', x, y - R - 7, [x - w / 2 - 2, y - R - 20, x + w / 2 + 2, y - R - 4]],
                  ['left', x + R + 7, y + 4, [x + R + 5, y - 9, x + R + 9 + w, y + 9]], ['right', x - R - 7, y + 4, [x - R - 9 - w, y - 9, x - R - 5, y + 9]]];
      var dentro = cand.filter(function (q) { return !(q[3][0] < 2 || q[3][2] > W - 2 || q[3][1] < 2 || q[3][3] > H - 2); }); if (!dentro.length) dentro = cand;
      var puesto = dentro.filter(function (q) { return !ocu.some(function (o) { return cho(q[3], o); }); })[0] || dentro[0];
      ocu.push(puesto[3]); texto(nom, puesto[1], puesto[2], puesto[0], '600 11.5px ' + FB, C.ink);
    });
    /* rótulos de las casas sueltas sin encimarse: primero las que tienen algo que mirar */
    rects.sort(function (a, b) { return (NIV.indexOf(nivel(a.m[0])) - NIV.indexOf(nivel(b.m[0]))) || ((b.m[0].rs ? 1 : 0) - (a.m[0].rs ? 1 : 0)) || (a.m[0].i - b.m[0].i); });
    rects.forEach(function (g) {
      var c = g.m[0], x = g.x, y = g.y, rr = radio() + (c.rs && VIST[vi] === 'e' ? 3.4 : 0) + 1;
      var esp = nivel(c) !== 'g' || c.rs, txt = (c.lg && z >= 11) ? c.l : c.k;
      if (c.lg === false && z < 14.8 && !esp) return;                            // en un conjunto grande, los números solo cuando ya se ven separados
      cx.font = (esp ? '600 ' : '') + '10.5px ' + FM; var w = cx.measureText(txt).width, k = rr * 0.7 + 2;
      var cand = [['left', x + rr + 3, y + 3.5, [x + rr + 3, y - 8, x + rr + 3 + w, y + 4]], ['right', x - rr - 3, y + 3.5, [x - rr - 3 - w, y - 8, x - rr - 3, y + 4]],
                  ['center', x, y - rr - 4, [x - w / 2, y - rr - 15, x + w / 2, y - rr - 3.5]], ['center', x, y + rr + 12, [x - w / 2, y + rr + 2, x + w / 2, y + rr + 12]],
                  ['left', x + k, y - rr - 3, [x + k, y - rr - 14, x + k + w, y - rr - 3]], ['right', x - k, y - rr - 3, [x - k - w, y - rr - 14, x - k, y - rr - 3]],
                  ['left', x + k, y + rr + 12, [x + k, y + rr + 2, x + k + w, y + rr + 12]], ['right', x - k, y + rr + 12, [x - k - w, y + rr + 2, x - k, y + rr + 12]]];
      var dentro = cand.filter(function (q) { return !(q[3][0] < 2 || q[3][2] > W - 2 || q[3][1] < 2 || q[3][3] > H - 2); }); if (!dentro.length) dentro = cand;
      var puesto = null;
      for (var j = 0; j < dentro.length && !puesto; j++) { if (!ocu.some(function (o) { return cho(dentro[j][3], o); })) puesto = dentro[j]; }
      if (!puesto && (esp || c.lg)) {
        var mejor = 1e18; dentro.forEach(function (q) { var s = 0; ocu.forEach(function (o) { s += solape(q[3], o); }); if (s < mejor) { mejor = s; puesto = q; } });
      }
      if (puesto) { ocu.push(puesto[3]); etiquetas.push([txt, puesto, esp]); }
    });
    etiquetas.forEach(function (e) { texto(e[0], e[1][1], e[1][2], e[1][0], (e[2] ? '600 ' : '') + '10.5px ' + FM, e[2] ? C.ink : C.ink2); });
    escala(); norte();
  }
  function escala() {
    var mpp = M_EC * Math.cos(latDe(V.v) * PI / 180) / esc(), obj = mpp * 110, e = Math.pow(10, Math.floor(Math.log(obj) / Math.LN10));
    var f = [5, 2, 1].filter(function (q) { return q * e <= obj; })[0] || 1, L = f * e, px = L / mpp, x = 14, y = H - 14;
    cx.beginPath(); cx.moveTo(x, y - 5); cx.lineTo(x, y); cx.lineTo(x + px, y); cx.lineTo(x + px, y - 5); cx.strokeStyle = C.ink2; cx.lineWidth = 2; cx.stroke();
    texto(L >= 1000 ? (L / 1000) + ' km' : L + ' m', x + px + 7, y + 1, 'left', '10.5px ' + FM, C.ink2);
  }
  function norte() {
    var x = W - 20, y = 12; cx.beginPath(); cx.moveTo(x, y); cx.lineTo(x + 5, y + 13); cx.lineTo(x, y + 9.5); cx.lineTo(x - 5, y + 13); cx.closePath(); cx.fillStyle = C.ink2; cx.fill();
    texto('N', x, y + 27, 'center', '10.5px ' + FM, C.ink2);
  }

  /* ---------- tooltip y avisos ---------- */
  function textoGrupo(g) {
    var l = [nombreGrupo(g.m) + ' · ' + g.n + ' sistemas'];
    (D.ley[VIST[vi]] || []).forEach(function (p) { if (g.cu[p[0]]) l.push(p[1] + ': ' + g.cu[p[0]]); });
    if (VIST[vi] === 'e' && g.rs) l.push(D.res + ': ' + g.rs);
    l.push('Toca o haz clic para acercar');
    return l.join('\n');
  }
  function mostrarTip(txt, px, py) {
    tipEl.textContent = txt; tipEl.hidden = false;
    var w = tipEl.offsetWidth, h = tipEl.offsetHeight, x = px + 14, y = py + 14;
    if (x + w > W - 4) x = px - w - 14; if (x < 4) x = 4;
    if (y + h > H - 4) y = py - h - 14; if (y < 4) y = 4;
    tipEl.style.left = x + 'px'; tipEl.style.top = y + 'px';
  }
  function ocultarTip() { tipEl.hidden = true; sel = null; }
  var tAviso = 0;
  function aviso(t) { avisoEl.textContent = t; avisoEl.hidden = false; clearTimeout(tAviso); tAviso = setTimeout(function () { avisoEl.hidden = true; }, 1800); }
  function bajo(px, py) {
    var mejor = null, md = 1e9;
    dib.forEach(function (d) { var q = Math.hypot(px - d.x, py - d.y); if (q <= d.r + 4 && q < md) { md = q; mejor = d; } });
    return mejor;
  }
  function textoDe(g) { return g.n === 1 ? g.m[0].t : textoGrupo(g); }
  function acercarGrupo(g) { var d = ajustar(cajaDe(g.m), 90, 30); d.z = Math.max(d.z, Math.min(V.z + 1.2, ZMAX)); ir(d, 650); }

  /* ---------- ratón (arrastrar, Ctrl + rueda, doble clic) ---------- */
  var arr = null;
  function pos(e) { var r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
  cv.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'touch' || e.button !== 0) return;
    cv.setPointerCapture(e.pointerId); anim = null; arr = { x: e.clientX, y: e.clientY, u: V.u, v: V.v, mov: false };
  });
  cv.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'touch') return;
    var p = pos(e);
    if (arr) {
      var dx = e.clientX - arr.x, dy = e.clientY - arr.y;
      if (!arr.mov && Math.abs(dx) + Math.abs(dy) > 4) { arr.mov = true; lienzo.classList.add('mz-arrastra'); ocultarTip(); }
      if (arr.mov) { var S = esc(); V.u = arr.u - dx / S; V.v = arr.v - dy / S; acotar(); pedir(); }
    } else {
      var h = bajo(p[0], p[1]);
      lienzo.style.cursor = h ? 'pointer' : '';
      if (h) { if (!sel) mostrarTip(textoDe(h.g), p[0], p[1]); } else if (!sel) { tipEl.hidden = true; }
    }
  });
  cv.addEventListener('pointerup', function (e) {
    if (e.pointerType === 'touch') return;
    var p = pos(e);
    if (arr && !arr.mov) { var h = bajo(p[0], p[1]); if (h && h.g.n > 1) acercarGrupo(h.g); }
    arr = null; lienzo.classList.remove('mz-arrastra');
  });
  cv.addEventListener('pointerleave', function (e) { if (e.pointerType !== 'touch' && !arr && !sel) tipEl.hidden = true; });
  cv.addEventListener('dblclick', function (e) {
    var p = pos(e); if (bajo(p[0], p[1])) return;
    anim = null; zoomEn(p[0], p[1], e.shiftKey ? -1 : 1); ocultarTip(); pedir();
  });
  cv.addEventListener('wheel', function (e) {
    if (!(e.ctrlKey || e.metaKey)) { aviso('Ctrl + rueda para hacer zoom'); return; }
    e.preventDefault(); var p = pos(e); anim = null;
    zoomEn(p[0], p[1], -e.deltaY * (e.deltaMode === 1 ? 0.05 : (Math.abs(e.deltaY) < 30 ? 0.012 : 0.0045))); ocultarTip(); pedir();
  }, { passive: false });

  /* ---------- tacto: un dedo deja pasar el scroll de la página; dos dedos mueven y acercan el mapa ---------- */
  var toq = null, ges = null;
  function iniciarGesto(e) {
    var a = e.touches[0], b = e.touches[1], r = cv.getBoundingClientRect(), mx = (a.clientX + b.clientX) / 2 - r.left, my = (a.clientY + b.clientY) / 2 - r.top, S = esc();
    ges = { d0: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) || 1, z0: V.z, u: V.u + (mx - W / 2) / S, v: V.v + (my - H / 2) / S };
    toq = null; anim = null; ocultarTip();
  }
  function moverGesto(e) {
    var a = e.touches[0], b = e.touches[1], r = cv.getBoundingClientRect(), mx = (a.clientX + b.clientX) / 2 - r.left, my = (a.clientY + b.clientY) / 2 - r.top;
    V.z = Math.max(ZMIN, Math.min(ZMAX, ges.z0 + Math.log((Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) || 1) / ges.d0) / Math.LN2));
    var S = esc(); V.u = ges.u - (mx - W / 2) / S; V.v = ges.v - (my - H / 2) / S; acotar(); pedir();
  }
  lienzo.addEventListener('touchstart', function (e) {
    if (e.touches.length >= 2) { e.preventDefault(); iniciarGesto(e); }
    else if (e.touches.length === 1 && !ges) toq = { x: e.touches[0].clientX, y: e.touches[0].clientY, t: Date.now(), mov: false };
  }, { passive: false });
  lienzo.addEventListener('touchmove', function (e) {
    if (e.touches.length >= 2) { e.preventDefault(); if (!ges) iniciarGesto(e); moverGesto(e); }
    else if (toq && !ges && Math.abs(e.touches[0].clientX - toq.x) + Math.abs(e.touches[0].clientY - toq.y) > 10) { toq.mov = true; aviso('Usa dos dedos para mover el mapa'); }
  }, { passive: false });
  lienzo.addEventListener('touchend', function (e) {
    if (e.touches.length < 2) ges = null;
    if (toq && !toq.mov && e.touches.length === 0 && Date.now() - toq.t < 600 && e.changedTouches.length) {
      var r = cv.getBoundingClientRect(), t = e.changedTouches[0], px = t.clientX - r.left, py = t.clientY - r.top, h = bajo(px, py);
      if (h && h.g.n > 1) acercarGrupo(h.g);
      else if (h) { sel = h.g.m[0].i + ':1'; mostrarTip(textoDe(h.g), px, py); pedir(); }
      else { ocultarTip(); pedir(); }
    }
    if (e.touches.length === 0) toq = null;
  });
  lienzo.addEventListener('touchcancel', function () { ges = null; toq = null; });

  /* ---------- botones, vistas y teclado ---------- */
  function vistaTodos() { return ajustar(cajaDe(CASAS), 70); }
  Array.prototype.forEach.call(bloque.querySelectorAll('.mp-ctl button[data-v]'), function (b) {
    b.addEventListener('click', function () {
      var v = b.getAttribute('data-v'); vi = Math.max(0, VIST.indexOf(v)); bloque.setAttribute('data-v', v);
      Array.prototype.forEach.call(bloque.querySelectorAll('.mp-ctl button[data-v]'), function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
      ocultarTip(); pedir();
    });
  });
  Array.prototype.forEach.call(bloque.querySelectorAll('.mz-ir button'), function (b) {
    b.addEventListener('click', function () {
      var ix = b.getAttribute('data-ir'), lista = ix === '' ? CASAS : ix.split(',').map(function (k) { return CASAS[+k]; });
      ir(ajustar(cajaDe(lista), 80), 800);
    });
  });
  Array.prototype.forEach.call(lienzo.querySelectorAll('.mz-botones button'), function (b) {
    b.addEventListener('click', function () {
      var a = b.getAttribute('data-z'), d = a === 'in' ? 1 : a === 'out' ? -1 : 0;
      if (!d) { ir(vistaTodos(), 800); return; }
      ir({ u: V.u, v: V.v, z: Math.max(ZMIN, Math.min(ZMAX, V.z + d)) }, 220);
    });
  });
  lienzo.addEventListener('keydown', function (e) {
    var k = e.key, S = esc();
    if (k === '+' || k === '=') zoomEn(W / 2, H / 2, 0.5); else if (k === '-' || k === '_') zoomEn(W / 2, H / 2, -0.5);
    else if (k === 'ArrowLeft') V.u -= 70 / S; else if (k === 'ArrowRight') V.u += 70 / S; else if (k === 'ArrowUp') V.v -= 70 / S; else if (k === 'ArrowDown') V.v += 70 / S;
    else if (k === '0' || k === 'Home') { ir(vistaTodos(), 600); e.preventDefault(); return; } else return;
    e.preventDefault(); anim = null; acotar(); ocultarTip(); pedir();
  });
  /* conteos de cada nivel junto a la leyenda */
  VIST.forEach(function (v, k) {
    var cu = {}; CASAS.forEach(function (c) { var n = c.n.charAt(k); cu[n] = (cu[n] || 0) + 1; });
    Array.prototype.forEach.call(bloque.querySelectorAll('.mp-ley-' + v + ' span[data-k]'), function (s) {
      var q = s.getAttribute('data-k'), e = s.querySelector('.mz-n'); if (e) e.textContent = '· ' + (q === 'rs' ? CASAS.filter(function (c) { return c.rs; }).length : (cu[q] || 0));
    });
  });

  /* ---------- tamaño y arranque ---------- */
  var primera = true;
  function medir() {
    var r = lienzo.getBoundingClientRect(), w = Math.round(r.width), h = Math.round(r.height);
    if (w < 50 || h < 50) return false;
    dpr = Math.min(window.devicePixelRatio || 1, 3);
    if (w !== W || h !== H || cv.width !== Math.round(w * dpr)) { W = w; H = h; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    if (primera) { var f = vistaTodos(); V.u = f.u; V.v = f.v; V.z = f.z; primera = false; }
    return true;
  }
  function arrancar() { if (medir()) { ocultarTip(); pedir(); } }
  if (window.ResizeObserver) new ResizeObserver(arrancar).observe(lienzo); else window.addEventListener('resize', arrancar);
  arrancar();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { pedir(); });
  window.__mapaZoom = { vista: V, ir: ir, ajustar: ajustar, casas: CASAS, dibujar: dibujar, grupos: function () { return dib; } };   // para pruebas
})();
