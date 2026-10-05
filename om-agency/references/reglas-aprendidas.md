# Reglas aprendidas del equipo

Entradas agregadas por el Encargado de Entrenamiento y Conocimiento. No se reescribe
el archivo completo al agregar una regla nueva — solo se añade al final, conservando
las anteriores.

---

## 2026-09-25 — Detección de sistema apagado/aislado intencionalmente

**Aplica a:** Monitor de Salud de Flota, Líder de Diagnóstico de Fallas.

**Regla:** para saber si el inversor de una casa está realmente apagado o aislado de
la red (no solo con una falla de comunicación), revisar `voltGridA/B/C` (la tensión
de red que el propio inversor sensa en su entrada) — **no** el atributo `invstate`.
`invstate` puede seguir reportando `"on"` incluso cuando el equipo está efectivamente
desconectado de la red; `voltGridA/B/C = 0` sostenido (no un solo punto aislado) es
la señal confiable de que el inversor no está viendo tensión de red, ya sea porque
está apagado, aislado manualmente, o desconectado en el breaker.

**Cómo verificar que es real y no un glitch:** pedir el histórico de `voltGridA` (u
otra fase) de varios días y confirmar que el valor se mantiene en 0 de forma
sostenida (no un punto suelto) — un caso real duró 166+ horas continuas sin ningún
valor distinto de cero en medio.

**Caso confirmado:** Casa 18PR — `voltGridA/B/C` cayó a 0V el 2026-09-18 20:24 hora
Bogotá (~54 min después de la interrupción de suministro `FlagStaProf=128`
registrada por el medidor de red a las 19:30 esa misma noche — ver el diagnóstico de
fallas de esa fecha) y se ha mantenido en 0V de forma continua desde entonces (166+
horas al momento de esta nota). El mismo día se observó que el patrón de ciclado
nocturno de la batería de esa casa (bajaba cada noche a un piso de 15-45%) cambió
por completo: desde esa noche la batería quedó fija en 97-100% sin descargarse casi
nada — consistente con que el inversor dejó de operar normalmente contra la red al
mismo tiempo.

**Corrección importante (mismo día, 2026-09-25):** `latch_state`/`latch_output` del
medidor de red **son atributos que solo se actualizan cuando cambian** (no en ciclo
fijo como el timeseries) — un valor `"open"` puede estar **desactualizado** y no
reflejar el estado real actual. Caso real: Casa 48PC mostraba `latch_state="open"`
con `lastUpdateTs` del 2026-09-17, pero el medidor seguía reportando corriente real
y viva en las tres fases cada 15 minutos hasta el momento de la revisión — la casa
nunca estuvo aislada, el atributo simplemente no se había refrescado desde un evento
antiguo (posiblemente una prueba o un corte muy breve).

**Regla corregida:** nunca declarar una casa aislada solo porque `latch_state`/
`latch_output` diga `"open"`. Antes de confiar en el atributo, cruzar contra
`currentA/B/C` y/o `powerAI` del mismo medidor en la última hora (timeseries, no
atributo) — si hay corriente real distinta de cero, el relé está efectivamente
cerrado y el atributo está obsoleto; ignorarlo. Solo tratar el aislamiento por relé
como real cuando el atributo dice `"open"` **y** la corriente reciente confirma 0 en
las tres fases. La señal de `voltGridA/B/C=0` sostenido en el inversor (timeseries,
se actualiza cada muestra) sigue siendo confiable por sí sola, sin necesitar este
cruce adicional.

## 2026-09-29 — Aislamientos simultáneos en varios inversores (posible acción remota del fabricante)

**Aplica a:** Monitor de Salud de Flota, Líder de Diagnóstico de Fallas.

**Hallazgo:** el mismo día, 4 casas (Casa 10, Casa 63, Casa 70, Casa 99) aparecieron
con `voltGridA/B/C=0` sostenido **casi al mismo instante** — las 4 transiciones caen
dentro de una ventana de 7 segundos (14:24:13 a 14:24:20 hora Bogotá), confirmado
contra el histórico crudo de Casa 99 (caída limpia de ~122V a 0V a las 14:00, sin
recuperar en 2+ horas). En las 4, el **medidor de red muestra voltaje normal
(~122V) y `FlagStaProf=0`** — o sea, EMCALI está bien, el corte no es de la red.

**Regla:** cuando **más de una casa** muestre `voltGridA/B/C=0` con timestamps de
inicio casi idénticos (segundos de diferencia, no minutos/horas), **no tratarlo como
fallas independientes** — es la firma de una acción centralizada (posible comando
remoto del fabricante del inversor, actualización de firmware push, o cambio de
código de red aplicado a un lote de equipos), no de 4 problemas de sitio separados.
Revisar primero si las casas afectadas comparten marca/modelo de inversor antes de
despachar técnicos a cada una por separado — y, si el patrón se repite, preguntar
directamente al fabricante (Deye o Livoltek según la marca) si hicieron algún cambio
remoto esa fecha/hora exacta.

**Corrección de alcance (mismo día, revisión posterior):** las 4 casas de arriba eran
solo la punta del hallazgo. El chequeo de aislamiento comparaba `voltGridA/B/C === 0`
(igualdad exacta), pero una entrada realmente desconectada puede seguir leyendo unos
pocos voltios de ruido residual/inducido — confirmado en Casa 104: se mantuvo en
0.4–1.4V por 2+ horas estando genuinamente offgrid. Ese bug de igualdad exacta dejó
sin detectar **14 de 18 casas** realmente offgrid en este mismo evento. Corregido a un
umbral: `voltGridA/B/C < 5V` sostenido en las tres fases = offgrid (la red real nunca
lee tan bajo). Con el umbral corregido, el alcance real del evento del 2026-09-29 fue
**18 de 26 casas (69%) offgrid**, no 4: Casa 10, 104, 108, 11, 15, 18, 23, 29, 35, 42,
48, 56, 57, 63, 70, 76, 77, 99.

**Regla corregida:** al chequear `voltGridA/B/C` para detectar offgrid, usar siempre
un umbral (`< 5V` en las tres fases), nunca una comparación de igualdad exacta a 0 —
el ruido residual en una entrada desconectada casi nunca es exactamente cero.

**Hipótesis de marca corregida:** con las 18 casas confirmadas, la marca/modelo del
inversor **sí muestra un patrón, pero no es exclusivo de una sola marca**:
- LIVOLTEK HP3-10KL2: **11 de 12 unidades de la flota (92%) quedaron offgrid** (todas
  menos Casa 30). Es el grupo con la señal más fuerte.
- LIVOLTEK HP3-15KL2: 3 de 5 unidades (60%) — Casa 11, 15, 76 offgrid; Casa 12 y 73
  normales.
- DEYE (todos los modelos, SUN-15K-SG01HP3 y variantes HV/LV): 4 de 9 unidades (44%)
  offgrid — Casa 10, 63, 70, 99 offgrid; Casa 111, 18PR, 2, 48PC, 74 normales. Este
  reparto es casi 50/50, mucho más parecido al azar que el patrón de Livoltek.

Esto descarta la hipótesis inicial de "una sola marca" pero **no descarta un origen
del lado del fabricante**: el hecho de que el modelo Livoltek HP3-10KL2 esté afectado
casi al 100% (11/12) mientras Deye está repartido ~mitad y mitad es la señal más
fuerte disponible de que el evento tiene más probabilidad de origen Livoltek
(firmware, comando remoto, o cambio de código de red aplicado por lote/modelo) que de
ser 18 fallas de sitio independientes. Al reportar este tipo de evento, dar el
desglose real por marca **y modelo** (no solo por marca) antes de escribirle al
fabricante — el modelo específico es la variable que más discrimina, más que la marca
sola.

**Advertencia crítica (mismo día, revisión posterior — corrección importante del
equipo):** no asumir que "el medidor muestra ~122V, entonces EMCALI está bien" sigue
siendo cierto sin revisar el timestamp de ese dato. En este mismo evento, a las 18:45
UTC (13:45 Bogotá) — 4+ horas después de que los inversores se aislaron a las 14:24 —
**el medidor de red de las 18 casas offgrid dejó de enviar voltageA/B/C, currentA y
FlagStaProf, todas al segundo exacto**, mientras el inversor de esas mismas casas
siguió reportando con normalidad (voltGridA vivo cada ~12 min, solo que <5V). Las
casas normales de la flota (ej. Casa 12, 18PR, 48PC, 73) siguieron con su medidor
reportando cada 15 min sin problema en la misma ventana. O sea: el "medidor normal"
que se usó para descartar una falla de EMCALI era un dato de hace horas, no en vivo —
**siempre revisar el timestamp del último punto de `voltageA` del medidor, no solo su
valor**, antes de afirmar el estado de la red en un reporte. Un medidor puede reportar
`activityState` (heartbeat de conexión) sano mientras su telemetría real (voltaje/
corriente) lleva horas sin actualizarse — son señales independientes.

**Regla de chequeo de comunicación (agregada tras pedido explícito de revisar fallas
de comunicación en la flota, 2026-09-29):** al hacer un chequeo de salud de flota,
comparar SIEMPRE el timestamp del último dato de **cada** dispositivo (medidor e
inversor por separado, y dentro del medidor, `activityState` vs. `voltageA` por
separado) contra la hora actual — nunca asumir que "el dispositivo está activo" cubre
que sus mediciones reales estén al día. En el mismo chequeo del 2026-09-29 se
encontraron dos fallas de comunicación reales, distintas del evento de aislamiento:
Casa 111, Casa 2, Casa 30 y Casa 74 llevaban 2+ horas sin ningún dato (ni medidor ni
inversor, incluido el heartbeat) desde las 19:06 UTC; y el segundo inversor
registrado de Casa 48PC (`f1b69750-901e-11f1-ba58-6facc4996bf7`, la unidad
reemplazada) lleva 36+ días sin reportar — candidato a darse de baja en Metrum/
Supabase para no seguir apareciendo en los chequeos de flota.

**ACTUALIZACIÓN — hallazgo mucho más amplio que el original (mismo día, misma
sesión):** al extender el chequeo de `voltageA` del medidor a las 26 casas (no solo
las 18 offgrid), el corte de las 18:45 UTC resultó afectar **22 de 26 casas (85%)**,
no solo las 18 offgrid — incluye también las 4 casas de "falla de comunicación real"
(Casa 111, 2, 30, 74). Solo 4 casas de toda la flota (Casa 12, 18PR, 48PC, 73)
tuvieron dato de medidor fresco (2 min) al momento de esta revisión (21:17 UTC);
las otras 22 llevaban exactamente 152 minutos sin un solo punto de `voltageA`,
todas cortando en el mismo segundo. Esa sincronía casi perfecta entre 22 medidores
de sitios distintos, y el hecho de que **no correlaciona con el estado del
inversor** (afecta tanto a las 18 offgrid como a las 4 con falla de comunicación
total, pero no a los 4 normales), hace muy poco probable que sean 22 fallas de sitio
independientes. **Hipótesis de trabajo: es un problema del lado de la plataforma
Metrum** (pipeline de ingesta de esa telemetría específica del medidor, o un batch/
rule-chain que dejó de procesar ese subconjunto de dispositivos) — no un problema de
comunicación de cada sitio ni de EMCALI. Antes de escalar como fallas de campo,
reportarlo directamente a soporte de Metrum con la lista de los 22 `redId` afectados
y la hora exacta del corte (18:45:00 UTC, 2026-09-29).

**Consecuencia práctica importante:** cualquier afirmación de "el medidor muestra
tensión normal, por lo tanto EMCALI está bien" hecha DESPUÉS de las 13:45 Bogotá del
2026-09-29 para estas 22 casas está basada en un dato viejo, no en vivo — no se puede
confirmar el estado real de EMCALI en esos puntos hasta que la plataforma vuelva a
ingerir `voltageA` del medidor.

## 2026-10-01 — Ausencia del hogar: marcar con 🧳 en las gráficas

**Aplica a:** Monitor de Salud de Flota, Generador de Reportes Operativos Periódicos, Líder de Diagnóstico de Fallas.

**Caso confirmado:** Casa 104 (Reservas de Pance). Desde el 24/09/2026 la demanda cayó a 2–4 kWh/día y la generación cayó con ella; el usuario confirmó que la familia no estaba en la vivienda. Con cero inyección, si la casa no consume y la batería está llena, el inversor recorta: la caída de generación no es una falla.

**Regla de detección:** marcar ausencia del hogar cuando haya **2 o más días seguidos** en que se cumplan las dos condiciones:
1. Demanda diaria (medidor solar) ≤ 50% de la mediana mensual de la propia casa.
2. Generación diaria (balance de medidores), dividida por su mediana y normalizada por la del portafolio ese mismo día, ≤ 0,7 (la generación cae con el consumo y no por clima).

**Cómo reportarlo:** en todas las gráficas y tablas por vivienda, anteponer 🧳 al nombre de la casa (ej. "🧳 Casa 104") y explicar el emoji en una nota con las fechas detectadas. Antes de despachar un técnico por bajo desempeño o caída de generación, revisar primero si la casa cumple este patrón.

**Septiembre 2026:** Casa 104 (24–30 sep, confirmada), Casa 18 (28–30), Casa 74 (4–5 y 24–25), Casa 76 (14–15) y Casa 287 (1–2). La regla reencontró sola las ausencias de Casa 74 y Casa 287 que ya registraba el reporte de la primera quincena.

## 2026-10-02 — Castellana Real fuera del análisis (en estabilización)

**Aplica a:** Monitor de Salud de Flota, Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos.

**Regla:** la zona **Castellana Real** (Casa 121 CR) aún no ha sido entregada a operaciones y está en etapa de estabilización. Se excluye de todos los reportes y KPI de flota (reporte diario, reportes mensuales, dashboards) hasta que el equipo confirme su entrega. Además de los pilotos (Piloto Promigas y Piloto Huawei), que ya estaban excluidos.

**Dónde está aplicada:** `EXCLUIR_ZONAS` en `om-agency/scripts/reporte_diario.py`. Para reincorporarla, quitar `"CASTELLANA REAL"` de ese conjunto.

## 2026-10-02 — Generación negativa = sistema energizado solo con baterías (sin paneles aún)

**Aplica a:** Monitor de Salud de Flota, Líder de Diagnóstico de Fallas, Generador de Reportes Operativos Periódicos.

**Regla:** un sistema con **generación neta negativa** (consumo del medidor solar − importación + exportación < 0) **no es una falla de medición**. Es un sistema energizado con las baterías en modo respaldo y **sin paneles instalados todavía**, mientras se resuelve la cubierta. Confirmado por el equipo para Casa 412p, 415p y 447p (Prado Verde Primavera), y vale para todo sistema que muestre generación negativa.

**Cómo tratarlos:** se excluyen de generación, cobertura y rendimiento, y no se les abre caso de diagnóstico. **Sí cuentan en el respaldo** (la batería responde a los cortes del OR), y en los reportes se rotulan "sin paneles (obra)". Su SOC alto y plano (97–99 %) es normal en ese modo.

**Corrige:** el reporte mensual de septiembre atribuía esa generación negativa a un posible TC del medidor solar mal cableado (diapositivas ocultas 20–22 del PPTX). Esa hipótesis queda descartada.

**Dónde está aplicada:** `SIN_PANELES` y la detección por generación < 0 en `om-agency/scripts/reporte_diario.py`.

## 2026-10-05 — Ausencia del hogar: validar siempre el consumo del cliente y mantener el estado de cada casa

**Aplica a:** Monitor de Salud de Flota, Generador de Reportes Operativos Periódicos, Líder de Diagnóstico de Fallas.

**Regla:** para decir que una casa tiene posible ausencia (🧳) se **valida el consumo del cliente** (demanda diaria del medidor solar) frente a su nivel habitual, no solo la generación: con la batería llena y sin inyección el inversor recorta la generación al consumo, así que una generación baja sin consumo bajo no indica ausencia. Se compara con la **mediana de los últimos 30 días** (la mediana no se infla con días de carga de carro eléctrico). **2 o más días completos seguidos en 50 % o menos** → posible ausencia; **2 días seguidos en 75 % o más** → vuelve a presente.

**Estado persistente:** el estado de cada casa se guarda en `om-agency/data/estado_casas.json` y se actualiza en cada ejecución del reporte diario (estados: `posible_ausencia`, `ausente_confirmada`, `posible_regreso`, `presente`). Las ausencias **confirmadas por una persona** (ejemplo: Casa 104, confirmada el 01/10) no se borran solas: si el consumo se normaliza pasan a `posible_regreso` para validar. Antes de despachar un técnico a una casa marcada, confirmar con el cliente.

**Dónde está aplicada:** `evaluar_consumo()` y `actualizar_estados()` en `om-agency/scripts/reporte_diario.py`; sección "Estado de las casas" del reporte.

**Corrige:** la regla del 01/10 (demanda ≤ 50 % del percentil 90 de 14 días y generación ≤ 70 %), que se inflaba con días de carro eléctrico y marcaba casas con consumo normal (Casa 18PR, 10 y 99 en el reporte del 05/10).

## 2026-10-05 — Respaldo: clasificar el tiempo sin respaldo según el SOC al interrumpirse (batería sin carga vs. falla de transición)

**Aplica a:** Monitor de Salud de Flota, Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Líder de Diagnóstico de Fallas.

**Regla:** al calcular el respaldo (INIC 4, reporte diario o cualquier análisis de cortes de red) hay que **tener en cuenta el SOC de cada sistema al momento de la interrupción**, para saber si la casa se quedó sin energía porque **la batería no tenía carga (consumo del cliente)** o porque hubo **una falla o una demora en la transición a OFF-GRID**. El % de respaldo del INIC 4 no cambia (sigue siendo (T_red − T_solar) / T_red, ponderado por tiempo, eventos > 2 min); lo que se agrega es la **causa del tiempo sin respaldo**.

**Cómo se clasifica** (cada apagón de la casa durante un corte de red, medidor solar sin tensión; el SOC del inversor se lee cada 15 min):
1. SOC ≤ 21 % al apagarse la casa (o en los 15 min alrededor) → **batería sin carga**.
2. Con SOC mayor, por el momento del apagón: primeros 3 min del corte → **demora o falla en la transición a OFF-GRID**; últimos 90 s del corte (o después) → **demora en el retorno a la red**; entre ambos → **falla del inversor durante el corte**.
3. Casa ya sin energía antes del corte de red o sin lectura de SOC → **no atribuible**.
El resultado es estable al variar el umbral de SOC (20–30 %), la ventana de inicio (2–5 min) y la de retorno (1–2 min).

**Cómo reportarlo:** junto al % de respaldo, mostrar las horas y los puntos del T_red por causa y el "INIC 4 sin pérdidas por batería sin carga" **solo como referencia** (no reemplaza al indicador). Las casas con batería sin carga se atienden con reserva mínima de SOC / autonomía; las de transición, con el fabricante (Deye, Livoltek) con la hora, el SOC y el modelo.

**Septiembre 2026 (38 sistemas en operación plena):** INIC 4 94,8 %; de los 5,5 h sin respaldo, 4,5 h (81 %) fueron batería sin carga (Casa 12 4,1 h; también Casas 23, 93p, 15p y 102p) y 1,0 h falla o demora de transición (9 casas Livoltek se apagaron 2 min 35 s al inicio del corte del 29/09 con SOC 82–100 %; Casas 42 y 56 se apagaron 8 min a mitad de ese corte con SOC 100 %; apagones de 13–35 s al volver la red en 31 casas). Sin pérdidas por batería sin carga el indicador sería 99,0 %. Con los 46 sistemas del Excel de soporte: 95,1 % y 98,7 %.

**Corrige:** el conteo previo de "10 de 15 casas Livoltek con la caída de 2 min 35 s al inicio": son 9; la décima (Casa 56) tuvo una caída de 8 min a mitad del corte.

**Dónde está aplicada:** `clasificar_evento()` (y `PISO_SOC`, `T_INICIO`, `T_FIN`, `CAUSAS`) en `om-agency/scripts/reporte_diario.py`; `om-agency/scripts/indicador_inic4.py` (columnas por causa en el Excel, bloque "Tiempo sin respaldo según el SOC" y resumen por zona).
