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

## 2026-10-05 — Alcance de los reportes de estado: sin pilotos, solo datos de hoy, casas por nombre

**Aplica a:** Monitor de Salud de Flota, Analista de Disponibilidad y Reportes, Generador
de Reportes Operativos Periódicos y Líder de Diagnóstico de Fallas (cuando entregue un
reporte).

**1. Excluir siempre los sistemas piloto de todo reporte.** Un sistema es piloto si el
nombre de su gateway o su atributo `spcus` (nombre de la casa/cliente) contiene "piloto"
(sin distinguir mayúsculas). Se excluyen el gateway y todos los inversores y medidores
que lo tienen en su atributo `gateway`: no se consultan, no se listan y no cuentan en
ningún total (sitios, dispositivos, disponibilidad, generación). Hoy son dos sitios de la
zona OFICINA PROMIGAS (Barranquilla), 8 dispositivos en total: el gateway `Piloto` y el
gateway `IN42420373` (`spcus` = "Piloto Promigas"), con los inversores
`HV2150024762` y `HP315K2HWC290014` y los medidores `2220231041`, `2223005621`,
`2223005627` y `2223005649`. Esta exclusión es una instrucción del usuario, distinta de
la lista de dispositivos fantasma: no se reincluye aunque un piloto muestre telemetría
nueva. Si no está claro si un sistema es piloto, preguntar antes de incluirlo.

**2. Reporte de estado de operación: solo datos de hoy.** El rango es desde las 00:00
hora Bogotá del día del reporte hasta la hora de corte. Estado actual con consulta de
último valor (sin rango); interrupciones, eventos, voltajes, corrientes y disponibilidad
con ventanas de hoy. No consultar histórico de 7 o 30 días para este reporte. Un equipo
sin datos hoy se reporta como "sin datos hoy" con la hora de su último valor (consulta de
último valor, no un barrido de histórico). Esta regla acota la verificación del
2026-09-25 ("pedir el histórico de varios días"): en el reporte de estado, "sostenido" se
evalúa dentro del día. Si el usuario pide tendencias o un periodo, se consulta ese rango.

**3. Identificar las casas por su nombre.** El nombre de la casa está en el atributo
`spcus` del gateway (ej. "Casa 24"); los inversores y medidores lo heredan por su
atributo `gateway`. En cada reporte, ese nombre va como identificador principal junto con
el conjunto o zona, y el serial del equipo solo como dato secundario. Mapa de Barranquilla
al 2026-10-05: gateway 1023 = Casa 24, 1026 = Casa 155 y 1030 = Casa 287 (Terra by Kaia);
1039 = Casa 9G (Gerona Club House); IN42420393 = Casa 121 CR (Castellana Real). Leer
`spcus` en vivo en cada reporte, porque el mapa puede cambiar. El operador de red
(`spdno`) de esta zona es Air-e.

**Aclaración (2026-10-05, mismo día):** el usuario confirmó que los sistemas de Oficina
Promigas son los pilotos y que deben excluirse de todos los reportes, sin mencionarlos
ni siquiera como nota. Los reportes solo dicen, en general, que los sistemas piloto están
excluidos. Además, el reporte de estado de operación de una zona sigue el formato del
reporte de interrupciones de Cali (titular con la conclusión, KPIs, "Qué pasó", tabla por
casa con el tiempo sin tensión en cada evento, línea de tiempo, batería durante el corte,
pendientes y límites del análisis), pero solo con datos de hoy: sin comparar con ayer ni
citar fechas de días anteriores.

## 2026-10-05 — Permisos: solo lectura en Metrum

**Aplica a:** todos los especialistas.

**Regla:** el agente solo tiene permiso para consultar datos y generar los reportes que se
le pidan. No da de baja, edita ni escribe nada en Metrum (dispositivos, atributos o
comandos) y no envía comandos a los equipos. Cuando un reporte detecte algo que pida un
cambio en Metrum (por ejemplo, inversores retirados que siguen registrados), lo deja como
tarea del equipo, redactada para que la haga una persona, y no ofrece ejecutarlo ni
pregunta si debe hacerlo.
