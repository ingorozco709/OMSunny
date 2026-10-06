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

## 2026-10-05 — Cálculo del tiempo y del % de respaldo

**Aplica a:** Monitor de Salud de Flota, Analista de Disponibilidad y Reportes, Generador
de Reportes Operativos Periódicos y Líder de Diagnóstico de Fallas.

**Regla (criterio del usuario):**
- Tiempo de respaldo = tiempo sin tensión del medidor de red − tiempo sin tensión del
  medidor solar.
- % de respaldo = tiempo de respaldo ÷ tiempo de la interrupción total (el que mide el
  medidor de red). Se calcula por cada interrupción y también en el total del día de cada
  casa.
- Fundamento: el medidor de red detecta las interrupciones del operador de red (OR) y el
  medidor solar detecta las interrupciones que el cliente ve realmente.

**Cómo se mide:** el tiempo sin tensión de cada medidor es la suma de los tramos entre
`po` y `pr`, con la hora al segundo de cada evento (no con las muestras de 15 min). Cada
tramo del medidor solar se asigna a la interrupción del medidor de red que lo contiene;
si cae fuera de todas, a la más cercana dentro de 3 min, porque los relojes de los
medidores no están alineados (hasta unos 40 s). Un hueco del medidor solar a mitad de una
interrupción del OR cuenta dentro de esa interrupción y no se llama "aislado". Un hueco
sin ninguna interrupción del OR cerca no entra en el %: se reporta aparte. Si la casa no
tiene datos en esa interrupción se escribe "s/d"; no se calcula ni se asume 0 %.

**Relación con reglas anteriores:** el "tiempo sin tensión" que ve la casa (suma de los
huecos del medidor solar) se sigue mostrando en los reportes de interrupciones; el
respaldo se agrega junto a él.

## 2026-10-06 — Vocabulario de los reportes: no usar "flota"

**Aplica a:** todos los especialistas, en todo texto que se entregue (reportes, resúmenes, mensajes).

**Regla (instrucción del usuario, "siempre"):** reemplazar la palabra "flota" por "conjunto de
sistemas" o "portafolio Sunny". Ejemplos: "cobertura solar del portafolio Sunny", "generación FV
del conjunto de sistemas". Los nombres de los especialistas (p. ej. "Monitor de Salud de Flota")
son nombres internos de la skill y no se muestran al usuario en los reportes.

## 2026-10-06 — Cálculo de generación, yield y cobertura de los reportes

**Aplica a:** Monitor de Salud de Flota, Analista de Disponibilidad y Reportes, Generador de
Reportes Operativos Periódicos.

**Reglas (instrucción del usuario, "siempre"):**
- Generación diaria = balance de medidores con los cierres diarios de las 00:00: demanda del
  medidor solar (`CenergyAI`) − importada + exportada del medidor de red (`CenergyAI`/`CenergyAE`).
  No se usa el contador del inversor (`energyPD`): en casas con inversores nuevos marca unas 10
  veces menos (verificado el 2026-10-05 contra la app de Deye en la Casa 86p: 13,1 kWh por
  balance frente a 1,4 kWh del inversor y 14,0 kWh en Deye).
- Cobertura solar = generación ÷ consumo del cliente (demanda del medidor solar).
- Yield proyectado anual = suma de la generación diaria real ÷ suma de la potencia instalada
  pico en DC (kWp) × 365, sin promedios. La potencia sale del archivo de sistemas del usuario
  (`Casas.xlsx`, copia en `reporte-diario/potencia_instalada.json`), no de `invcap` del inversor.
- Casa 447p solo tiene baterías instaladas y se excluye de generación, yield y cobertura.
- Si a un medidor le falta el cierre diario, la generación de esa casa queda sin calcular ("sin
  cierre diario del medidor"); no se reemplaza por otro dato.

## 2026-10-06 — Veredicto de respaldo por interrupción y cortes en curso

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Decisiones del usuario:**
- El umbral de 130 V en el medidor solar para decir "BESS respaldando" **no funciona**: no se cumple en todos los sistemas al pasar a off-grid (Casa 99 respaldó con 119–123 V). La columna "Estado de la casa" se eliminó del reporte. No volver a clasificar el respaldo por un valor de tensión puntual.
- El respaldo se decide por corte con la serie completa (ver `reporte-diario/README.md`, "Veredicto de respaldo por corte"): hueco en el medidor solar (al caer ≤ 2 min es transferencia; "durante" ≥ 2 min es caída), quién alimenta (`BattPower`: positivo batería, negativo solar cargando) y causa (SOC ≤ 12 % = batería agotada).
- Cuando todos los sistemas vieron una interrupción de la empresa de energía, se actualiza el reporte con el corte en curso: un sistema está en corte si su inversor marca `voltGrid* < 5 V` y su medidor de red no tiene dato posterior a la caída (el medidor sin tensión deja de enviar; comparar timestamps, no el último valor).
- Casos de referencia (6-oct, Cali, corte desde las 09:30): Casa 99 respaldó 30 min y cayó 20 min con SOC 10 % (hueco `po` 10:00:27, `pr` 10:20:07), luego se recuperó con el solar cargando la batería a 4 kW; Casa 35 cayó 155 s con SOC 96 % (revisar inversor).

**Dónde está el código:** `reporte-diario/` (rama `claude/loving-hawking-iwftvn`). Abrir una sesión nueva para reportes de interrupciones: leer `reporte-diario/README.md` y este archivo antes de generar.

## 2026-10-06 — Casas solo con baterías y baterías en reserva en el reporte diario

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Decisiones del usuario ("adelante" sobre la propuesta):**
- Las casas que solo tienen baterías (hoy Casa 447p) no suman en generación, yield, cobertura ni exportación, pero **sí se reportan**: tabla propia "Casa solo con baterías (sin FV)" con cortes, tiempo sin red, tiempo que vio la casa, respaldo del peor corte, SOC inicio → mín → fin del mayor corte, SOC actual y estado "Ahora". Entran todas las excluidas por `exclusiones.json` o por la regla automática de "sin generación FV"; los pilotos siguen excluidos de todo.
- Sus eventos de inversor (p. ej. `igf`) cuentan en el punto "Inversores".
- Punto "Baterías en reserva": todos los sistemas (con o sin corte, incluidos los solo-baterías) con SOC de 22 % o menos en el último dato disponible al corte del reporte. El SOC "actual" es el último dato del inversor y se muestra con su hora, no la muestra fija de las 07:00.
- `potencia_instalada.json` sale de `Casas_V2.xlsx` (2026-10-06): Casas 412p y 425p pasan de 2,975 a 5,36 kWp. El usuario confirmó que ambas tienen 9 paneles (el archivo decía 5); 9 × 0,595 = 5,355 kWp, que el archivo redondea a 5,36. La fila "Piloto Promigas" del archivo no se incluye (pilotos excluidos).

**Dónde está el código:** `reporte-diario/` (`reporte_diario.py`, `reporte_html.py`).

## 2026-10-06 — Veredicto "Transferencia lenta" (hueco al caer de más de 2 min)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Decisión del usuario ("sí, por favor", sobre la propuesta):** un hueco de tensión en el medidor solar "al caer" la red que dura **más de 2 min** ya no se etiqueta como "Respaldo total con transferencia" (esa etiqueta queda para transferencias de hasta 2 min). Se etiqueta **"Transferencia lenta"**: la casa sí quedó respaldada después, pero tardó en recuperar tensión al pasar a isla. La celda del veredicto muestra la duración del hueco.

**Caso que lo originó (6-oct, Cali, corte desde las 09:29):** Casa 57 (Livoltek HP3-10KL2) con medidor solar sin tensión de 09:29:52 a 09:38:33 (8 min 41 s; muestra de las 09:30 con 0,0 V y 0 W; batería en 99 %), confirmado con los eventos `po`/`pr` y con las muestras del propio medidor. En el mismo corte, los Livoltek HP3-10KL2 tardaron entre 2 min 35 s y 8 min 41 s; los Deye, cerca de 1 min.

**Prioridad entre veredictos de un corte:** caída durante el respaldo, sin respaldo, transferencia lenta, transferencia normal, respaldo total. Un hueco "durante" de 2 min o más sigue siendo caída, aunque también haya un hueco lento al caer.

**Dónde está el código:** `veredicto_respaldo` en `reporte-diario/reporte_diario.py`.

## 2026-10-06 — Veredicto "Retardo de transferencia" (reemplaza a "Transferencia lenta")

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Regla (instrucción del usuario):** cuando el cliente ve la interrupción más de 1 min con la batería cargada, el corte se marca como **"Retardo de transferencia"**. Reemplaza al veredicto "Transferencia lenta" de la entrada anterior (umbral de 2 min), que ya no se usa.

**Cómo se aplicó (criterios del generador, confirmables con el usuario):**
- "Ve la interrupción" = un solo hueco continuo de tensión en el medidor solar al caer la red, de más de 60 s. No se suman microhuecos separados: los Deye mostraron dos huecos de ~32 s con ~9 s de tensión en medio (Casas 10, 74, 111) y no se marcan; la Casa 63, con un solo hueco de 61 s, sí.
- "Batería cargada" = SOC al inicio del corte mayor a 22 % (el mismo umbral de reserva del reporte). Con SOC de 22 % o menos o sin dato de SOC no se marca como retardo.
- Un hueco "durante" de 2 min o más sigue siendo "Caída durante el respaldo" (batería agotada si SOC ≤ 12 %, si no revisar inversor), con prioridad sobre el retardo; "Sin respaldo" también tiene prioridad.
- La celda del veredicto muestra la duración del hueco y el SOC, p. ej. Casa 57: 8 min 41 s sin tensión al caer, SOC 97 %.

**Dónde está el código:** `veredicto_respaldo` en `reporte-diario/reporte_diario.py` (`RETARDO_MIN`).

## 2026-10-06 — Corrección del "Retardo de transferencia" y de la asignación de huecos a cortes

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Corrige la entrada anterior ("Retardo de transferencia"), en el criterio de "ve la interrupción":** contar solo el hueco más largo dejaba a la Casa 63 (un hueco de 61 s, 1 min 15 s vistos) con retardo y a la Casa 74 (dos huecos de ~31 s, 1 min 34 s vistos) sin marcar. Los Deye cortan dos veces seguidas al caer la red, con ~9 s de tensión en medio; para el cliente es una sola interrupción de ~1 min. Ahora la interrupción al caer es el primer hueco "al caer" más los que le siguen con menos de 60 s de tensión en medio; los huecos separados (a mitad del corte o al volver la red) no se suman. El resto de la regla no cambia (más de 60 s, batería cargada = SOC al inicio > 22 %, la caída durante el respaldo y "sin respaldo" tienen prioridad). La celda muestra, p. ej., "sin tensión 1 min 03 s al caer en 2 huecos · SOC 49 %".

**Corrección de asignación (cumple la regla del 2026-10-05 de que cada tramo del medidor solar va a una sola interrupción):** un hueco del medidor solar cuenta en un solo corte: el que empieza hasta 75 s de su inicio, si no el que lo contiene, si no el último que terminó hasta 10 min antes. Antes, un hueco que empezaba justo antes de un segundo corte (relojes de los medidores desfasados ~23 s) se sumaba también al corte anterior. Caso: Casas 15, 23, 42 y 77 el 6-oct, cortes de red de 12:40 (41 s) y 12:46 (1 h 41 min): el hueco de 5 min 35 s es del segundo corte, pero el primero salía como "Sin respaldo" con respaldo de 0 %.

**Dónde está el código:** `interrupcion_al_caer` y `veredicto_respaldo` (y el reparto de huecos en `analizar`) en `reporte-diario/reporte_diario.py`.

## 2026-10-06 — Tabla "Por sistema" del reporte diario: una columna por corte, con base en el último corte

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** en la tabla "Por sistema", una columna por cada corte de red. El **último corte de red registrado** de cada casa es la referencia y se muestra completo: hora (inicio → fin), duración, SOC de inicio y de fin y % de respaldo. En los cortes que ya pasaron solo se deja una leyenda pequeña con el % de respaldo, nada más.

**Cómo se aplicó:**
- Las columnas "Mayor corte", "Respaldo peor corte" y "SOC al inicio / al final del mayor corte" se reemplazaron por la columna "Último corte" y las columnas "Anterior 1…4" (del corte anterior más reciente al más antiguo). La hora y la duración de los cortes anteriores salen solo al pasar el cursor.
- Si una casa tiene más de 4 cortes anteriores, el resto no se muestra en la tabla (se avisa en su celda "Cortes") y queda en el desplegable "Detalle por corte" (Casa 73 tuvo 10 microcortes el 6-oct).
- Se mantienen "Cortes", "Tiempo sin red", "Tiempo que vio la casa" (suma de todos los cortes), "Ahora" y el veredicto, que sigue siendo el del peor corte (se indica "corte de las HH:MM" cuando no es el último). Criterio por confirmar con el usuario: si el veredicto debe ser el del último corte.

**Dónde está el código:** bloque "una columna por corte" en `reporte-diario/reporte_html.py`.

## 2026-10-06 — El veredicto de la tabla "Por sistema" es el del último corte

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario (confirmada):** en la tabla "Por sistema", el veredicto de respaldo y todo su detalle (alimenta, sin tensión, SOC) son **solo los del último corte registrado** de cada casa, el mismo que se muestra completo en la columna "Último corte". No se muestran leyendas de otros cortes dentro del veredicto: mostrar "corte de las 09:29" junto a un último corte de las 12:46 confunde. Los cortes anteriores llevan únicamente su % de respaldo.

**Reemplaza** el criterio de la entrada anterior ("el veredicto sigue siendo el del peor corte", que quedaba por confirmar). Consecuencia: una falla en un corte anterior (p. ej. caída durante el respaldo de la Casa 99 a las 09:29) ya no aparece en la etiqueta de la tabla; sigue visible en el desplegable "Detalle por corte" y en el % de respaldo de ese corte.

**Dónde está el código:** bloque "una columna por corte" en `reporte-diario/reporte_html.py`.

## 2026-10-06 — Cortes anteriores en "Por sistema": % de respaldo con su hora

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** en las columnas "Anterior 1…4" de la tabla "Por sistema", además del % de respaldo se muestra la **hora a la que fue cada corte** (hora de inicio, con fecha solo si no es del día del reporte). Ajusta la entrada anterior ("solo el % de respaldo, nada más"): la hora ahora es visible; la duración sigue saliendo solo al pasar el cursor.

**Dónde está el código:** `_hora` y `celdas_prev` en `reporte-diario/reporte_html.py`.

## 2026-10-06 — Tabla "Rendimiento": sin barras; revisión del yield alto (la potencia no se cambió)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** quitar las barras de la tabla "Rendimiento de los sistemas" (comparaban la generación de cada casa con la del mayor generador y se leían como si fueran el "Frente a su patrón"). La última columna queda como "Alerta" y solo lleva las etiquetas (baja vs su patrón, sin cierre diario, etc.). Las barras de la tabla de exportación no se tocaron.

**Criterio reafirmado por el usuario:** el yield se calcula con la generación real del último día evaluado (el último día completo con cierres diarios), no con promedios de varios días. Los 10 días solo se usaron como diagnóstico para revisar la potencia, no para calcular el yield.

**Revisión del yield alto del 5-oct (sin cambiar la potencia):**
- La potencia de `potencia_instalada.json` coincide con paneles × 0,595 kWp de `Casas_V2.xlsx` en todas las casas, salvo Casa 9G y Casa 121 CR (12,5 kWp con 22 paneles; 22 × 0,595 = 13,09: por confirmar con el usuario si usan otro módulo) y diferencias menores (Casa 48PC: 11,35 frente a 11,305).
- En las casas con yield más alto del Livoltek, el contador diario del propio inversor (`energyPD`) coincide con la generación por balance (Casa 23: 28,6 frente a 29,7 kWh; Casa 76: 33,8 frente a 30,3 kWh). La generación es real; si el yield es alto, la duda es la potencia registrada. En los Deye `energyPD` no sirve (regla del 2026-10-06).
- Candidatos a revisar la potencia (yield del día 1,4 a 1,7 veces la mediana de su conjunto, Reservas de Pance): Casa 23 (6,54 kWp), Casa 76 (7,14 kWp), Casa 30, Casa 18 y Casa 63. Sin dato independiente de la potencia FV instalada no se puede corregir: la telemetría del inversor no trae potencia FV instantánea. El estado `throttled` no sirve para detectar recorte (los Livoltek lo marcan casi siempre y los Deye nunca).
- Pendiente: que el usuario confirme la potencia (paneles) de esas casas.

## 2026-10-06 — Yield patrón por región para comparar los sistemas

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** el yield patrón con el que se comparan los sistemas es **1188 kWh/kWp·año para Cali** y **1323 kWh/kWp·año para los sistemas de la costa** (Turbaco, Barranquilla y Cartagena).

**Cómo se aplicó:** la columna "Frente al yield patrón" de la tabla "Rendimiento" es el yield anual proyectado del sistema (generación real del último día evaluado ÷ kWp × 365) dividido entre el patrón de su región; el patrón se muestra en el encabezado de cada ciudad. Reemplaza la comparación anterior "frente a su patrón" (índice del día contra la mediana de los 9 días previos de la misma casa), que ya no se usa. La alerta "baja vs patrón" (con "con corte" si el sistema estuvo 30 min o más sin red) aparece por debajo del 75 % del patrón; se retiró la alerta "baja de forma sostenida", que dependía de la comparación anterior. No hay alerta para valores altos. Con el 5-oct, los sistemas más por encima del patrón de Cali fueron Casa 23 (139 %), Casa 76 (131 %) y Casa 48PC (128 %), los mismos que se señalaron para revisar la potencia instalada.

**Dónde está el código:** `YIELD_PATRON` y `patron_yield` en `reporte-diario/reporte_diario.py`; cálculo en `reporte-diario/reporte_html.py`.

## 2026-10-06 — Alerta "baja vs patrón": "bajo consumo" en vez de "con corte"

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** en la alerta de rendimiento, en vez de "con corte" se evalúa si el consumo de la vivienda bajó y, si es así, se escribe **"bajo consumo"**.

**Por qué:** el "con corte" se calculaba con los cortes de toda la ventana de 24 h, incluidos los del día siguiente a la generación evaluada, y no explicaba el yield bajo de ese día.

**Cómo se aplicó:** "baja vs patrón" (por debajo del 75 % del yield patrón de su región) lleva ", bajo consumo" cuando el consumo del cliente (demanda del medidor solar) del día evaluado fue menor al 75 % del habitual de esa casa, medido como la mediana de sus 9 días previos (mínimo 3 días con dato; el umbral es `CONSUMO_BAJO`). Criterio por confirmar con el usuario: el 75 % y la base de comparación (mediana de los días previos). Con el 5-oct, "bajo consumo" salió en las Casas 10, 11, 35, 48, 57, 60p, 73 y 287; no en las 18PR, 55p, 77, 99, 104 y 111, que consumieron entre el 78 % y el 112 % de lo habitual.

**Dónde está el código:** `CONSUMO_BAJO` en `reporte-diario/reporte_diario.py`; `dem_hist` en `main()` y la alerta en `reporte-diario/reporte_html.py`.

## 2026-10-06 — Alerta "producción limitada (batería llena)" en la tabla de rendimiento

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario ("agrégala"):** cuando un sistema tenga el yield bajo (por debajo del 75 % del patrón de su región) y la batería llegue a la carga completa temprano, la alerta lo indica con "producción limitada (batería llena HH:MM)".

**Hallazgo que la originó (5-oct, Casas 99, 18PR, 111, 55p, 77 y 104, sin fallas, sin cortes y con consumo normal o habitual):** la batería llegó a 99 % entre las 08:45 y las 13:15 y desde entonces la producción FV igualó al consumo de la casa (curva reconstruida como consumo − red − potencia de batería, válida para Deye; en Livoltek el signo de `BattPower` es distinto). Como los sistemas no exportan, con la batería llena el inversor limita la producción al consumo: el yield mide la energía solar consumida y no la que el sistema podría producir. Además el balance de medidores no cuenta la energía que la batería almacena en el día (Casa 111: +5,7 kWh; Casa 77: +1,9 kWh); no se ajustó la regla de generación por balance.

**Criterio (mío, por confirmar con el usuario):** primera muestra de SOC ≥ 99 % entre las 06:00 y las 18:00 del día evaluado, y antes de las 12:00 (constantes `BATERIA_LLENA_SOC` y `LLENO_ANTES_H`). Con varios días evaluados (lunes), se exige en al menos la mitad. Solo se muestra junto a "baja vs patrón"; puede acompañar a "bajo consumo". Con el 5-oct salió en las Casas 10, 11, 18PR, 35, 48, 57, 73, 77, 99, 104 y 111; no en la 55p (batería llena a las 13:15), 60p ni 287.

**Dónde está el código:** `_lleno` en `main()` de `reporte-diario/reporte_diario.py`; la alerta en `reporte-diario/reporte_html.py`.

## 2026-10-06 — "Producción limitada en la tarde" (batería llena entre las 12:00 y las 16:00)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Decisión del usuario (opción 1 de la propuesta):** la alerta de rendimiento distingue dos casos. Batería llena (SOC ≥ 99 %) **antes de las 12:00**: "producción limitada (batería llena HH:MM)", porque se pierde la mayor parte del día. Batería llena **entre las 12:00 y las 16:00**: "producción limitada en la tarde (batería llena HH:MM)", porque solo se limita parte de la tarde. Después de las 16:00 no se marca (ya casi no hay sol que limitar).

**Caso que la originó (5-oct, Turbaco):** Casa 55p (73 % del patrón, producción de 4,6 kW a las 09:45 y batería llena a las 13:15, desde cuando la producción igualó al consumo) y Casa 60p (batería llena a las 14:45). La Casa 287 no entra: su batería no llegó a llenarse; su explicación es "bajo consumo".

**Dónde está el código:** `LLENO_TARDE_H` y `LLENO_ANTES_H` en `reporte-diario/reporte_diario.py`; la alerta en `reporte-diario/reporte_html.py`.

## 2026-10-06 — Sin barras en las tablas del reporte

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** eliminar también las barras de la tabla "Exportación de energía activa" (la última columna, junto a "Cobertura solar", dibujaba la energía exportada de cada casa frente a la mayor exportadora y se leía como si fuera la cobertura). Con esto el reporte ya no lleva barras en ninguna tabla (las de "Rendimiento" se quitaron antes). Las tablas solo muestran cifras y etiquetas.

**Dónde está el código:** tabla de exportación en `reporte-diario/reporte_html.py`.

## 2026-10-06 — Cada dato del reporte indica su periodo con el rango de horas

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** dejar claro de qué periodo es cada dato, con el día y el rango de horas, en cada encabezado.

**Qué lo originó:** en "Exportación", la columna "lun 5 oct" (0,04 kWh en la Casa 10) y "Exportada" (0,09 kWh) parecían inconsistentes. La primera era solo la parte del lunes dentro de la ventana (17:36 a 24:00) y la segunda toda la ventana de 24 h (5 oct 17:36 → 6 oct 17:36); la exportación de hoy (00:00 a 17:36, 0,06 kWh) no tenía columna. Además la tabla de rendimiento usaba el mismo encabezado "lun 5 oct kWh" para el día completo.

**Cómo se aplicó:** (1) exportación: una columna por día con su rango ("lun 5 oct 17:40–24:00" y "mar 6 oct 00:00–17:40") que suman el total; (2) exportada, importada y consumo del lado respaldado llevan el periodo de la ventana ("5 oct 17:40 → 6 oct 17:40"); (3) consumo del cliente, generación, cobertura y "Exportada / generada" indican "lun 5 oct 00:00–24:00" (días completos, con cierre diario); (4) rendimiento: columnas por día con "00:00–24:00"; (5) la tarjeta de exportación del resumen indica el periodo. La nota bajo la tabla lo explica.

**Dónde está el código:** `_rango`, `vent_h`, `per_dias` y `segs_ex` en `reporte-diario/reporte_html.py`; el segmento de hoy en `analizar` de `reporte-diario/reporte_diario.py`.
