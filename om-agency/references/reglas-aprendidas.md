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

## 2026-10-06 — La reserva de la batería se toma como el 20 %

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** la reserva de la batería se toma como **20 %** (antes 22 %) para todos los sistemas.

**Qué cambia (constante `RESERVA` en `reporte-diario/reporte_diario.py`):** el punto "Baterías" (sistemas que llegaron a la reserva durante un corte), el punto "Baterías en reserva" (último SOC de 20 % o menos) y el texto de "Límites del análisis". Como la batería "cargada" del veredicto "Retardo de transferencia" se define como SOC al inicio del corte mayor a la reserva, ese umbral también pasa a 20 %. Las entradas anteriores de este archivo que citan el 22 % son históricas y quedan reemplazadas por esta.

**Efecto con los datos del 6-oct (17:41):** "Baterías en reserva" incluye la Casa 99 (20 %) además de 102p (15 %), 121 CR (19 %), 415p (19 %) y 447p (12 %); los veredictos de respaldo no cambiaron.

## 2026-10-07 — El veredicto de respaldo incluye el tiempo que el cliente vio en el último corte

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** en la columna "Veredicto de respaldo (último corte)" de la tabla "Por sistema", se incluye el **tiempo que el cliente vio en el último corte** y se repite en todos los reportes.

**Cómo se aplicó:** debajo de la etiqueta del veredicto, la primera línea es "tiempo que vio la casa: X" (suma de los huecos de tensión del medidor solar asociados a ese corte, la misma cifra de su % de respaldo) o "0 s, sin hueco"; luego van "alimenta" y la causa o el retardo de transferencia, como antes.

**Dónde está el código:** `vio` y `vr_det` en `reporte-diario/reporte_html.py`.

## 2026-10-07 — Cortes anteriores con tiempo sin red y tiempo que vio la casa

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** en las columnas "Anterior 1…4" de la tabla "Por sistema", además del % de respaldo y la hora, se muestran el **tiempo que se fue la red** (duración del corte) y el **tiempo que el cliente vio la interrupción** (suma de huecos de tensión del medidor solar). Sustituye la regla de que la duración solo salía al pasar el cursor.

**Dónde está el código:** `celdas_prev` y el encabezado "Anterior N" en `reporte-diario/reporte_html.py`.

## 2026-10-07 — Detalle por corte: columna "Hueco durante"

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario ("agrégalo"):** en "Detalle por corte" se agrega la columna **Hueco durante**, con la duración y la hora de inicio de cada hueco de tensión que ocurre a mitad del corte (ni al caer ni al volver la red). Antes ese tiempo solo estaba en "Total que vio la casa" y la fila parecía inconsistente (ej. Casa 2, 6 oct: corte 09:29–12:10, hueco al caer —, al volver —, total 32 s; el hueco fue de 11:35:10 a 11:35:42).

**Dónde está el código:** `durante_txt` y `det_head` en `reporte-diario/reporte_html.py`.

## 2026-10-07 — "Puntos más relevantes" desplegable

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "Puntos más relevantes" se muestra como un desplegable, igual que "Detalle por corte" (cerrado por defecto, con el número de puntos en el título). El resumen de las viñetas en la respuesta de la rutina no cambia.

**Dónde está el código:** bloque "Puntos más relevantes" de `reporte-diario/reporte_html.py`.

## 2026-10-07 — Reporte exclusivo de interrupciones del día

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Solicitud del usuario:** "reporte exclusivo de las interrupciones que se han presentado el día de hoy hasta este momento".

**Cómo se genera:** `python3 reporte-diario/reporte_diario.py --solo-interrupciones` (ventana de las 00:00 de hoy a la hora de corte, hora de Bogotá). Usa el mismo análisis del reporte diario (cortes, huecos, veredicto de respaldo, último corte por casa, casas solo con baterías), pero la página solo lleva lo de cortes de red: titular con el estado (en curso o no), KPI de sistemas con cortes, % de respaldo, sistemas con falla de respaldo en su último corte y mayor tiempo sin tensión que vio una casa; puntos relevantes de interrupciones; resumen por ciudad; eventos de red; "Por sistema"; detalle por corte y límites. No lleva rendimiento, exportación ni comunicación. Se publica como Artifact aparte, sin tocar el del reporte diario.

**Dónde está el código:** `--solo-interrupciones` en `reporte-diario/reporte_diario.py` y el bloque `solo_interrupciones` de `generar` en `reporte-diario/reporte_html.py`.

## 2026-10-07 — Vista rápida gráfica y tablas en desplegables (versión final del reporte diario)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucciones del usuario (aplicadas y publicadas el 2026-10-07):**
- El reporte lleva una sección "Vista rápida" con gráficas: semáforo del respaldo, tarjetas por ciudad, línea de tiempo de cortes con barras combinadas (verde respaldado, rojo lo que vio el cliente) y SOC al inicio del corte (último dato registrado si falta), mapa de calor casa × evento, histograma de lo que vio la casa (tooltip con las casas), batería inicio → mínimo → fin por casa (reemplaza las curvas de SOC), baterías por debajo de 50 %, generación frente a consumo, ranking de las casas por **energía exportada**, yield frente al patrón y hora de batería llena.
- Se descartaron: curvas de SOC, cortes por hora del día y dispersión de generación frente a kWp.
- Todas las tablas del reporte (desde "Por ciudad") y "Puntos más relevantes" van en desplegables cerrados.
- El ranking que se pidió es de **exportación de energía**, no de cobertura solar: no sustituir el criterio que pide el usuario sin su confirmación. Con exportaciones menores a 1 kWh se muestra en Wh.
- Cada instrucción nueva del usuario se ejecuta solo cuando lo autoriza ("no las ejecutes hasta que te dé la instrucción").

**Dónde está el código:** bloque `VISUAL`/`sec_vis` y plantilla final de `reporte-diario/reporte_html.py`.

## 2026-10-07 — La hora de generación va en el título

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** el título del reporte diario incluye la hora (Bogotá) a la que se genera el reporte: `<title>` "Operación diaria 7 oct · 15:58" y el encabezado "Operación de las últimas 24 horas · generado 15:58". Es la hora de generación, no la de corte de la ventana (07:00).

**Dónde está el código:** `pagina` y `h1 .gh` en `reporte-diario/reporte_html.py`.

## 2026-10-07 — Reporte de interrupciones del día en versión gráfica

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "vuélvelo más gráfico" (sobre el reporte exclusivo de interrupciones del día).

**Cómo se aplicó:** `--solo-interrupciones` reutiliza los gráficos de la "Vista rápida" del reporte diario que tratan de cortes (semáforo, línea de tiempo por casa, mapa de calor por evento, cuánto vio la casa, batería durante el corte más largo, baterías bajo 50 %) y agrega dos propios: tarjetas por ciudad centradas en interrupciones y una línea de tiempo de eventos de red (una fila por evento, barra coloreada por el respaldo de la peor casa y, a la derecha, casas afectadas, duración típica y peor respaldo). La rejilla horaria de la línea de tiempo por casa es de 1 h cuando la ventana es de 18 h o menos. Las tablas pasan a desplegables cerrados. No se incluyen gráficas que el usuario ya descartó en el reporte diario (cortes por hora del día, curvas de SOC, dispersión generación frente a kWp).

**Precisión de los porcentajes:** en los gráficos, un respaldo entre 97 % y 100 % se muestra con un decimal (98,7 %), para que un valor en ámbar (< 99 %) nunca aparezca como «99».

**Dónde está el código:** `tarj_c_int`, `grafico_ev` (dentro del bloque `VISUAL`) y `vis_int` en `reporte-diario/reporte_html.py`.

## 2026-10-07 — Hora del corte en el título de baterías y ranking de exportación en kWh

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucciones del usuario:** (1) el título de la gráfica "Baterías por debajo de 50 % al corte del reporte" lleva la fecha y hora del corte (ej. "7 oct 07:00") para que se sepa a qué hora se hace el corte; la "hora a la que haces el reporte" que pidió se refería a esa hora de corte, no a la de generación. (2) El ranking de las casas por energía exportada va siempre en **kWh** con 2 decimales (no en Wh: generaba mucho ruido); el tooltip trae 3 decimales.

**Dónde está el código:** título de baterías y `grafico_rk` en `reporte-diario/reporte_html.py`.

## 2026-10-07 — Ranking de exportación: eje fijo en 5 kWh, dinámico solo si algo lo supera

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** el eje horizontal del ranking de las casas por energía exportada se fija en **5 kWh** (marcas cada 1 kWh). Solo cuando una casa exporta más de 5 kWh el eje se vuelve dinámico: se ajusta al mayor valor, con marcas en pasos redondos (2, 5, 10, 50 kWh…).

**Dónde está el código:** `max_ex`, `paso_k` y `mxk` en `grafico_rk` de `reporte-diario/reporte_html.py`.

## 2026-10-07 — La hora de generación sale del título principal (h1)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** quitar la hora de generación solo del **título principal** del reporte ("Operación de las últimas 24 horas"). Se mantiene en el `<title>` de la página ("Operación diaria 7 oct · 16:26") y en la línea de datos del encabezado ("Generado 16:26"). Ajusta la entrada anterior ("La hora de generación va en el título"): el h1 ya no lleva "· generado HH:MM".

**Dónde está el código:** encabezado `h1` en `reporte-diario/reporte_html.py`.

## 2026-10-08 — Mapa de calor a tamaño natural y tooltips táctiles

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Hallazgos del usuario (reporte del 8-oct):** (1) el mapa de calor "Respaldo de cada casa en los eventos de red" se veía enorme cuando había pocos eventos (2 columnas): el CSS `.scroll svg` fuerza `min-width` de 720 px y el SVG se escalaba 3 veces. (2) En el celular los detalles de las gráficas (el `<title>` del SVG) no aparecen al tocar una barra.

**Cómo se aplicó:** el SVG del mapa de calor lleva `min-width:0` y su ancho natural en px, así que conserva la proporción del resto del reporte. Se agregó `TOUCH_JS` (script al final de la página): en pantallas sin cursor (`hover: none`), al tocar una barra, punto o celda se muestra el mismo texto del `<title>` (o del atributo `title`) en un recuadro flotante que se oculta al tocar en otro lado, al desplazarse o a los 8 s. En equipos con cursor no hace nada y siguen los tooltips nativos.

**Dónde está el código:** `TOUCH_JS` y el estilo del SVG del mapa de calor en `reporte-diario/reporte_html.py`.

## 2026-10-08 — Título del mapa de calor (eventos de 3 casas o más) y SOC visible en barras angostas

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucciones del usuario:** (1) el mapa de calor "Respaldo de cada casa en los eventos de red" solo dibuja eventos que afectaron a **3 casas o más** (criterio por número de casas, no por minutos), así que deja fuera los cortes de 1 o 2 casas (p. ej. Casa 48PC y Casa 121 CR el 7-oct). El título lo dice: "· solo eventos que afectaron a 3 casas o más; no incluye los cortes de 1 o 2 casas (microcortes)". (2) La etiqueta "SOC xx%" al inicio del corte en la línea de tiempo no se quitó: solo se ocultaba cuando la barra medía menos de 52 px (cortes cortos frente a las 24 h, como los 40 min de Turbaco). Ahora, en cortes de 5 min o más, va dentro de la barra si cabe y a su derecha si es angosta.

**Dónde está el código:** `etiqueta` en la línea de tiempo y el título del mapa de calor en `reporte-diario/reporte_html.py`.

## 2026-10-08 — El SOC al inicio del corte va siempre dentro de la barra

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** la etiqueta del SOC al inicio del corte en la línea de tiempo va **dentro de la barra** (no a su derecha). Ajusta la entrada anterior ("SOC visible en barras angostas"): ahora, en cortes de 5 min o más, se escribe "SOC 39%" si la barra mide 52 px o más; si es más angosta (corte corto frente a las 24 h), solo "39%" en letra de 8,5 px dentro de la barra; solo si ni así cabe, a su derecha como último recurso.

**Dónde está el código:** `etiqueta` en la línea de tiempo de `reporte-diario/reporte_html.py`.

## 2026-10-08 — El mapa de calor incluye los conjuntos de menos de 3 sistemas

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** el mapa de calor "Respaldo de cada casa en los eventos de red" no puede filtrar solo por "3 casas o más": Castellana Real (Casa 121 CR), Pance Campestre (Casa 48PC) y otros conjuntos tienen un único sistema y nunca aparecerían. Ajusta la entrada anterior (criterio de 3 casas).

**Cómo se aplicó:** un evento entra al mapa si afectó a 3 casas o más de un mismo conjunto (zona) o, en conjuntos con menos de 3 sistemas, al conjunto completo (afectados >= min(3, tamaño del conjunto)). El tamaño del conjunto sale del atributo `zona` de los sistemas incluidos. Quedan fuera los cortes de 1 o 2 casas de un conjunto grande (p. ej. Casa 73 en Reservas de Pance). El título lo explica. El 7-oct el mapa pasó de 2 a 8 columnas e incluye la Casa 48PC (4 eventos) y la Casa 121 CR (2 eventos).

**Dónde está el código:** `_entra` y `evs` del mapa de calor en `reporte-diario/reporte_html.py`.

## 2026-10-08 — El título del mapa de calor vuelve a ser corto

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** quitar el texto en gris del título del mapa de calor "Respaldo de cada casa en los eventos de red" (el que explicaba el criterio de los eventos).

**Cómo se aplicó:** el `<h3>` queda solo como "Respaldo de cada casa en los eventos de red", sin el `<span class="h3s">`. El criterio de qué eventos entran (3 casas o más de un conjunto, o conjunto completo de menos de 3 casas) no cambia; solo queda en la nota al pie del mapa ("cada celda es el % de respaldo del corte; solo eventos de 3 casas o más de un conjunto, o de un conjunto completo de menos de 3 casas").

**Dónde está el código:** los dos `<h3>` del mapa de calor (reporte diario e interrupciones) en `reporte-diario/reporte_html.py`.

## 2026-10-08 — El SOC de la línea de tiempo lleva icono de batería

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** el porcentaje que aparece dentro de cada barra de "Cortes de red en la ventana, por casa" se confunde con el % de respaldo. Se eligió la opción de poner un icono de batería junto al número.

**Cómo se aplicó:** la etiqueta del SOC al inicio del corte (cortes de 5 min o más) sigue dentro de la barra y ahora va precedida de un icono de batería con el nivel de carga: icono + "SOC 39%" si la barra es ancha (62 px o más), icono + "39%" en letra chica si es angosta, icono + "39" si es muy angosta (unos 24 px, p. ej. un corte de 30 min frente a 24 h) y, solo si ni así cabe, a su derecha. La leyenda de la gráfica pasa a ser el primer elemento y lleva el mismo icono: "SOC: carga de la batería al inicio del corte, no es el respaldo (cortes de 5 min o más; * = último dato registrado)".

**Dónde está el código:** `icono_bateria` y `etiqueta` en la línea de tiempo, `leyenda_t` y las clases `.bat` / `.bat-f` en `reporte-diario/reporte_html.py`.

## 2026-10-08 — El umbral de "baja vs patrón" y la línea punteada del yield pasan a 90 %

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "la línea punteada [de la gráfica de yield frente al patrón de su región] debe estar al 90 %". Reemplaza el 75 % de las entradas anteriores sobre "baja vs patrón".

**Cómo se aplicó:** una sola constante, `YIELD_ALERTA = 0.90` en `reporte-diario/reporte_html.py`, define: la línea punteada y su eje "90 %" en la gráfica de yield, el color de los puntos (azul ≥ 90 %, ámbar por debajo), la cuenta "por debajo de 90 % (N sistemas)" de la leyenda y la alerta "baja vs patrón" de la tabla "Rendimiento" y de los puntos relevantes (con sus causas "bajo consumo" y "producción limitada", que siguen igual). El 7-oct pasó de 37 a 41 sistemas por debajo del umbral. El umbral de "bajo consumo" (75 % del consumo habitual de la casa, `CONSUMO_BAJO`) no cambia.

**Dónde está el código:** `YIELD_ALERTA` y su uso en `reporte-diario/reporte_html.py` (alerta, gráfica de yield y nota de la tabla Rendimiento).

## 2026-10-08 — El nombre del reporte (título de la página) no lleva la hora

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "quita la hora del nombre del reporte". Reemplaza la entrada anterior que agregaba la hora de generación al `<title>`.

**Cómo se aplicó:** el `<title>` del reporte diario queda solo como "Operación diaria 8 oct" (sin "· HH:MM"), igual que el del reporte de interrupciones. El título principal visible tampoco lleva la hora. La hora de generación se conserva únicamente en la línea de datos del encabezado ("Generado 09:03") y la hora del corte del reporte, en el título de la gráfica de baterías.

**Dónde está el código:** plantilla `pagina` del reporte diario en `reporte-diario/reporte_html.py`.

## 2026-10-08 — El reporte va con fondo oscuro

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "cambie el reporte a fondo oscuro".

**Cómo se aplicó:** en `reporte-diario/estilos.css` la paleta oscura (`--bg:#0f1317`, `--surface:#161b20`, texto `#e7edf1`…) pasó a ser la base del `:root` con `color-scheme: dark`, y se quitaron la paleta clara y los bloques `prefers-color-scheme` / `[data-theme]`. El reporte se ve oscuro siempre, sin depender del tema del equipo o del navegador de quien lo abre. Aplica al reporte diario y al de interrupciones (comparten `estilos.css`). Las gráficas y tablas usan tokens, así que no hubo que tocar sus colores. Para volver al tema claro basta restaurar la paleta clara en el `:root` de `estilos.css` (queda en el historial de git).

**Dónde está el código:** `:root` de `reporte-diario/estilos.css`.

## 2026-10-08 — Interrupciones del día: estado actual y respuesta del respaldo por evento

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Solicitud del usuario:** tras una interrupción de red en Cali, "un reporte del estado actual de los sistemas y cómo se comportaron ante la interrupción en temas de respaldo".

**Cómo se aplicó (`--solo-interrupciones`):** el reporte agrega, para las ciudades con cortes hoy, (1) la tabla **Estado actual de los sistemas** (todos los sistemas de la ciudad: red ahora, SOC y hora, modo del inversor `invrun` y hora, y veredicto del último corte, con la serie del inversor), (2) por cada evento de 3 o más sistemas, la tabla **Cómo respondió el respaldo** (un renglón por casa y una columna por corte del evento, ordenado de peor a mejor respaldo) con un resumen por marca, y la nota de los sistemas cuyos cortes fueron mucho más cortos que el evento (otra alimentación), y (3) una tabla de **cortes aislados** para los eventos de un solo sistema. El título lleva la ciudad cuando son una o dos.

**Dónde está el código:** `R["run_ult"]` en `analizar` (`reporte-diario/reporte_diario.py`) y `sec_estado`, `sec_resp`, `sec_aisl` del bloque `solo_interrupciones` de `reporte-diario/reporte_html.py`.

## 2026-10-08 — La tabla "Estado actual de los sistemas" va agrupada por zona

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Solicitud del usuario:** "en esta tabla agrúpalos por zona" (sobre la tabla Estado actual de los sistemas · Cali del reporte de interrupciones).

**Cómo se aplicó:** los sistemas se agrupan por ciudad y zona (atributo `zone` del medidor, conjunto residencial). Cada grupo abre con una fila de encabezado con el nombre de la zona y un resumen: número de sistemas, cuántos siguen sin red (o "todos con red") y cuántos tuvieron una falla de respaldo en su último corte (Sin respaldo, Caída durante el respaldo o Retardo de transferencia). Las zonas van de mayor a menor número de sistemas y las casas dentro de cada zona por número. Cuando el reporte abarca más de una ciudad, el encabezado lleva la ciudad ("Barranquilla · Terra by Kaia"). La ciudad ya no se repite en el renglón de cada casa.

**Dónde está el código:** `_zona_nombre`, `grupos_est` y `lista_est` en el bloque `solo_interrupciones` de `reporte-diario/reporte_html.py`.


## 2026-10-09 — Casa 447p fuera del reporte (aún no entregada a operaciones)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "excluye la casa 447p del reporte, que aún no ha sido entregada a operaciones y me está contaminando el reporte". Reemplaza la regla anterior que la dejaba en la tabla de casas solo con baterías, en "Baterías en reserva" y en los eventos de inversor (`igf`).

**Cómo se aplicó:** `exclusiones.json` tiene una clave nueva `"fuera"` (casas que no entran al reporte en ningún lugar, como los pilotos); la Casa 447p pasó de `"excluir"` a `"fuera"`. El generador ya no descarga ni analiza sus datos: no aparece en la tabla de casas solo con baterías (el desplegable no se muestra mientras no haya otras), en "Baterías en reserva", en los eventos del inversor (`igf`), en comunicación ni en ningún conteo de sistemas. El resumen JSON la lista en `excluidos` con el motivo "fuera del reporte (no entregada a operaciones)". Cuando operaciones la reciba, se quita de `"fuera"` en `exclusiones.json` y vuelve a analizarse (si sigue sin generación FV, entra a "excluir").

**Dónde está el código:** `cargar_exclusiones`, `MOTIVO_FUERA` y `motivo_exclusion` en `reporte-diario/reporte_diario.py`; lista en `reporte-diario/exclusiones.json`.

## 2026-10-09 — Logo Sunny (Powered by Promigas) en el encabezado de los reportes

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** agregar el logo de Sunny (Powered by Promigas) a los reportes y dejar el fondo oscuro.

**Cómo se aplicó:** el archivo `reporte-diario/logo_sunny.png` se embebe como imagen data URI (≈40 KB) como primer elemento del `<header>` del reporte diario y del de interrupciones, arriba a la izquierda, de 64 px de alto. El logo conserva su propio fondo claro (`#f2f2ef`) con esquinas redondeadas, porque su texto es oscuro y no se lee sobre el fondo oscuro de la página; la página sigue con `--bg:#0f1317`. Si falta el archivo, el reporte sale sin logo. Para cambiar el logo se reemplaza `logo_sunny.png` (mismo nombre).

**Dónde está el código:** `_logo_html` / `LOGO` y los dos `<header>` en `reporte-diario/reporte_html.py`; `header img.logo` en `reporte-diario/estilos.css`.

## 2026-10-09 — El logo va con fondo oscuro y en la esquina superior derecha

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "te dije que al logo le dejaras también el fondo oscuro y mejor ubícalo en el recuadro rojo" (esquina superior derecha del encabezado). Reemplaza la entrada anterior, donde el logo iba sobre un recuadro claro a la izquierda.

**Cómo se aplicó:** `reporte-diario/logo_sunny_original.png` es el logo oficial (fondo claro, textos oscuros). `reporte-diario/logo_a_oscuro.py` (solo biblioteca estándar) quita el fondo (transparente) y aclara los textos, "Sunny" en turquesa claro conservando su degradado y "Powered by PROMIGAS" en gris claro; el sol naranja no cambia. El resultado es `logo_sunny.png` (≈417 × 149 px), que se embebe como data URI en el encabezado, alineado a la derecha y de 84 px de alto; el título queda en la columna izquierda. En pantallas de 760 px o menos el logo pasa encima del título (56 px de alto). La página sigue con `--bg:#0f1317`. Para actualizar el logo: reemplazar `logo_sunny_original.png` y ejecutar `python3 -I reporte-diario/logo_a_oscuro.py`.

**Dónde está el código:** `_logo_html` / `LOGO` y los dos `<header>` en `reporte-diario/reporte_html.py`; reglas `header`, `header>*` y `header img.logo` en `reporte-diario/estilos.css`.

## 2026-10-09 — Logo vectorial (SVG) para que no se vea pixelado

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Observación del usuario:** "el logo se ve algo pixelado, ¿puedes mejorarle la calidad?".

**Causa:** el logo oficial que se tiene es una imagen de solo 529 × 207 px, ya borrosa; al mostrarla a 84 px de alto en pantallas de alta densidad se ampliaba y se veía pixelada.

**Cómo se aplicó:** se vectorizó. `reporte-diario/logo_a_vectorial.py` (usa pillow, numpy y potracer) separa el logo en el sol naranja y el texto "Sunny", los traza como curvas suaves con su degradado (naranja a amarillo, turquesa claro a azul turquesa) y escribe "Powered by PROMIGAS" como texto real (Montserrat/Segoe UI/Arial con ancho fijo, en gris claro y negrita para PROMIGAS), de modo que se ve nítido a cualquier tamaño. El resultado es `logo_sunny.svg` (≈17 KB), embebido en el encabezado como data URI; `logo_sunny.png` queda como respaldo si falta el SVG. El trazo conserva la forma del logo, pero el texto pequeño es una recomposición con una tipografía parecida, no el lockup oficial: si se consigue el logo oficial en SVG o en PNG de alta resolución, se guarda como `logo_sunny.svg` y listo.

**Dónde está el código:** `_logo_html` en `reporte-diario/reporte_html.py`; `reporte-diario/logo_a_vectorial.py`.

## 2026-10-13 — Reporte de un periodo a mano: el encabezado dice el periodo

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Solicitud del usuario:** "actualízame el reporte con los datos desde el sábado a las 00 horas hasta hoy a las 7 am" (10 oct 00:00 a 13 oct 07:00, 79 h, publicado en el mismo artifact).

**Problema:** con `--inicio` distinto de 24 h, el reporte decía "Últimas 24 horas" / "Operación de las últimas 24 horas" y titulaba "Operación diaria 13 oct", aunque la ventana era de 79 h.

**Cómo se aplicó:** el título de la página, el rótulo y el encabezado dependen de la ventana: lunes automático (fin de semana) y ventana de 24 h (±1,5 h) no cambian; cualquier otra ventana pasa a "Operación 10 oct al 13 oct" (título), "Periodo de 79 horas" (rótulo) y "Operación del 10 oct al 13 oct" (encabezado). La rutina diaria sigue igual ("Operación diaria 13 oct", "Operación de las últimas 24 horas"). Para pedir un periodo: `reporte_diario.py --inicio AAAA-MM-DDTHH:MM --fin AAAA-MM-DDTHH:MM`. Los días completos del periodo (00:00 a 24:00) dan la generación, el yield y la cobertura; el resto va por ventana.

**Dónde está el código:** `titulo`, `rot_kick` y `rot_h1` en `generar` de `reporte-diario/reporte_html.py`.

## 2026-10-13 — Cada corte de red se mide por separado (los huecos que cubren varios cortes se reparten)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "mide por individual cada corte de red y así mismo muéstralos en las gráficas". Reemplaza la regla "cada hueco cuenta en un solo corte" y descarta unir cortes cercanos.

**Problema que lo motivó:** el 10-oct (Casa 121 CR) la red cayó 01:13 → 01:57, volvió 3 s y cayó otra vez 01:57 → 04:21 (y 04:22 → 04:27). La casa estuvo sin tensión 01:20 → 04:23 (3 h 03 min) con la batería en la reserva. Como el hueco se asignaba solo al corte donde empezaba, el segundo corte salía con "la casa vio 0 s" y 100 % de respaldo aunque la casa estuvo a oscuras todo ese corte; el KPI de tiempo con tensión salía inflado (88,3 % en lugar de 55,0 % para el 10 al 13 de oct).

**Cómo se aplicó:** `repartir_huecos` reparte cada hueco de tensión entre los cortes que cubre, por el tiempo que cae dentro de cada uno. La cabeza del hueco va al corte de siempre (al caer, el que lo contiene o el último que terminó hasta 10 min antes). Si el hueco sigue, lo que cae dentro de los cortes siguientes cuenta en cada uno (tipo "durante", continuación) y la tensión que no vuelve con la red ya de regreso cuenta "al volver" del corte anterior. Cada tiempo se cuenta una sola vez. La caída durante el respaldo se juzga por el hueco completo (2 min o más) cuando empezó en ese corte. Los cortes nunca se unen, aunque la red vuelva solo 3 s. Resultado en la Casa 121 CR: cortes de 01:13 (14,8 %), 01:57 (0 %) y 04:22 (0 %), los tres "Caída durante el respaldo". Probado contra 262 cortes de 6 ventanas anteriores (30-sep al 8-oct): solo cambian 2 (Casa 10, 1-oct 05:58 y 06:02, un hueco que cubría dos cortes seguidos). También se corrigió el SOC al inicio del corte cuando el inversor no reportó en los 30 min previos: ahora es el último dato registrado antes del corte (marcado con *), no la primera muestra de la ventana.

**Gráficas:** la línea de tiempo, el mapa de calor, el histograma de "cuánto vio la casa en cada corte" y las tablas usan el valor de cada corte. En periodos de más de 36 h, la línea de tiempo marca el eje cada 6 h con el día en cada medianoche ("dom 11") y las etiquetas de SOC a la derecha de una barra angosta se omiten si se montarían sobre la siguiente barra (el SOC sigue en el cursor).

**Límites:** el semáforo del respaldo sigue mirando solo el último corte de cada casa (decisión anterior); una casa con cortes anteriores fallidos y un último corte bueno aparece en "Respaldo total" y hay que leer el detalle por corte.

**Dónde está el código:** `repartir_huecos`, `veredicto_respaldo` y el bloque de respaldo por corte en `reporte-diario/reporte_diario.py`; eje y etiquetas de la línea de tiempo en `reporte-diario/reporte_html.py`.

## 2026-10-13 — Casas 35 y 57 siempre cuentan como sistemas con FV

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Pregunta del usuario:** "¿por qué marcaste esta casa [Casa 57] como solo con baterías?".

**Causa:** no fue una decisión a mano: la regla automática de "sin generación FV" (el balance de medidores no pasa de 5 kWh/día en 5 o más días de los últimos 9, `PV_MIN_KWH` y `PV_MIN_DIAS`) las tomó por casas sin FV. La Casa 57 (Livoltek HP3-10KL2, 4,165 kWp) y la Casa 35 (3,57 kWp) sí tienen FV, pero consumen muy poco (3 a 4 kWh/día), no exportan y el inversor limita la producción cuando la batería se llena temprano. El balance de medidores mide la energía solar consumida, así que sale en 2,7 a 3,1 kWh/día (Casa 57) y 3,3 a 3,9 (Casa 35) todos los días; el contador del propio inversor marca 4,1 a 5,3 y 5,0 a 5,6 kWh/día, y la batería hace un ciclo diario entre 75 y 100 %. La Casa 35 se salvaba solo cuando la ventana de 9 días incluía un día por encima de 5 kWh, así que la clasificación saltaba de un día a otro.

**Cómo se aplicó:** `exclusiones.json` pasó a `"incluir": ["Casa 35", "Casa 57"]`, que fuerza a contarlas como sistemas con FV (generación, yield, cobertura, exportación, rendimiento). Con eso el reporte vuelve a 47 sistemas. Pendiente de vigilar: Casa 104 (4,165 kWp, balance de 0,5 a 2,3 kWh/día) tiene el mismo riesgo y hoy solo se salva por un día de 5,6 kWh del 3 de oct; cuando salga de la ventana, la regla la tomará por solo baterías. Si ocurre, agregarla a `"incluir"`.

**Dónde está el código:** `motivo_exclusion` y `cargar_exclusiones` en `reporte-diario/reporte_diario.py`; lista en `reporte-diario/exclusiones.json`.

## 2026-10-13 — El mapa de calor lleva la fecha de cada evento

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "agrégale a esta gráfica [Respaldo de cada casa en los eventos de red] la fecha de las interrupciones".

**Cómo se aplicó:** cada columna del mapa de calor trae tres líneas: la fecha del evento ("sáb 10 oct"), la ciudad y la hora de inicio. Entre dos columnas de días distintos hay una línea vertical tenue. El cursor sobre una celda también muestra la fecha ("10 oct 01:13"). Aplica al reporte diario y al de interrupciones.

**Dónde está el código:** bloque del mapa de calor (`grafico_hm`) en `reporte-diario/reporte_html.py` y la clase `ax-f` en `reporte-diario/estilos.css`.

## 2026-10-13 — Casa 447p vuelve al reporte; Casa 104 forzada como sistema con FV

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "ya puedes agregar a los reportes la Casa 447p, que fue energizada totalmente desde el 8 de octubre; la Casa 104 viene operando bien, solo que tiene bajo consumo; las Casas 60p y 382p al parecer tienen problemas de comunicación por baja señal, la tendré en seguimiento". Reemplaza la entrada del 9-oct que dejaba la Casa 447p fuera del reporte.

**Cómo se aplicó:**
- `exclusiones.json`: `"fuera"` queda vacío; `"incluir"` pasa a Casa 35, Casa 57, Casa 104 y Casa 447p. La Casa 447p (Livoltek HP3-15KL2, 3,57 kWp) ya cuenta en todo: generación, yield, cobertura, exportación, baterías en reserva, eventos del inversor, comunicación y tablas. Con ella el reporte tiene 48 sistemas. La Casa 104 (4,165 kWp) se fuerza como sistema con FV porque su consumo es muy bajo (0,5 a 2,3 kWh/día de balance), sin exportación, y la regla automática la habría tomado por solo baterías en cuanto saliera de la ventana el único día con más de 5 kWh.
- Casas 60p y 382p (Turbaco): sus fallas de comunicación se tratan como problema de señal en seguimiento del equipo; el reporte las sigue mostrando en "Comunicación y equipos" cuando el último dato supera 2 h, sin cambios en el generador.

**Qué esperar:** la Casa 447p tiene aún poco historial (9 días de ventana, solo desde el 8-oct con FV), así que su yield y su "patrón propio" se estabilizan en unos días; la Casa 104 sale con "baja vs patrón" (yield muy bajo) por su bajo consumo, no por falla.

**Dónde está el código:** lista en `reporte-diario/exclusiones.json`; `cargar_exclusiones` y `motivo_exclusion` en `reporte-diario/reporte_diario.py`.

## 2026-10-14 — Eventos descartados a pedido (visita técnica en Gerona Club House)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "excluye del reporte la interrupción de Gerona; ayer hubo una visita técnica para realizar un balanceo de cargas en el tablero del cliente".

**Cómo se aplicó:** `exclusiones.json` tiene una clave nueva `"eventos_fuera"`: lista de `{casa, desde, hasta, motivo}` (hora de Bogotá, `hasta` excluido). Los cortes de red y los huecos de tensión de esa casa que empiezan dentro del rango se descartan al analizar la casa, así que no cuentan en cortes, respaldo, mapa de calor, línea de tiempo ni en los avisos; el resumen JSON los lista en `eventos_descartados` con su motivo. El evento de Gerona era un hueco de tensión de 20 min 27 s en la Casa 9G (13-oct 14:56, sin corte de red asociado en los medidores de red); la entrada cubre esa casa el 13-oct completo. Solo se descartan eventos de esa casa en ese día: los siguientes siguen contándose.

**Cuándo aplicar lo mismo:** si el equipo avisa de una visita técnica o una intervención programada que cortó el servicio, agregar la casa, el rango de fechas y el motivo a `"eventos_fuera"`; no se quitan casas ni se tocan umbrales.

**Dónde está el código:** `cargar_exclusiones`, `motivo_evento_fuera` y `EVENTOS_FUERA` / `EVENTOS_DESCARTADOS` en `reporte-diario/reporte_diario.py`; lista en `reporte-diario/exclusiones.json`.

## 2026-10-14 — El mapa de calor muestra todas las interrupciones

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "cambiemos esa regla y que aparezcan todas las interrupciones en esa gráfica". Reemplaza el filtro del 8-oct (eventos de 3 casas o más de un mismo conjunto, o conjunto completo de menos de 3 casas). Motivo: los cortes de Turbaco del 13-oct (Casas 60p, 86p y 425p, una casa cada vez, en un conjunto de 16) no salían en el mapa.

**Cómo se aplicó:** el mapa "Respaldo de cada casa en los eventos de red" dibuja todos los eventos de la ventana, también los de una sola casa; ya no se filtra por conjunto (se quitó `_entra` y el tamaño por zona). La nota al pie dice "incluye todos los eventos de red de la ventana". Las columnas siguen con fecha, ciudad y hora; el SVG sigue con su ancho natural y desplazamiento horizontal.

**Dónde está el código:** bloque del mapa de calor en `reporte-diario/reporte_html.py` (variable `evs`).

## 2026-10-14 — Pruebas de comisionamiento en Turbaco (cortes de las Casas 60p, 86p y 425p descartados)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "ayer estuvieron en Turbaco haciendo pruebas de comisionamiento en esas casas que aparecen con interrupciones, entonces puedes excluirlas del reporte de interrupciones".

**Cómo se aplicó:** `exclusiones.json` → `"eventos_fuera"` suma tres entradas (Casa 60p, Casa 86p y Casa 425p, 13-oct completo, motivo "Pruebas de comisionamiento en Turbaco (Prado Verde Primavera)"). Los cortes de red y los huecos de tensión de esas casas que empezaron el 13-oct no cuentan en cortes, respaldo, mapa de calor, línea de tiempo ni avisos; quedan listados en `eventos_descartados` del resumen JSON. Eran los tres cortes de Turbaco del 13-oct (08:37, 11:27 y 14:46), uno por casa, sin traslape y sin afectar a las otras 15 casas del conjunto. Las casas siguen en el reporte para todo lo demás (generación, baterías, inversores, comunicación): solo se descartan sus interrupciones de ese día.

**Dónde está el código:** `motivo_evento_fuera` en `reporte-diario/reporte_diario.py`; lista en `reporte-diario/exclusiones.json`.

## 2026-10-14 — La línea de tiempo de cortes lleva la fecha en cada marca del eje

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "colócale la fecha también donde colocaste las horas para saber a qué días pertenecen las interrupciones" (gráfica "Cortes de red en la ventana, por casa").

**Cómo se aplicó:** cada marca del eje superior lleva dos líneas: la fecha ("mar 13 oct") arriba y la hora ("08:00") debajo. Si las marcas quedan a menos de 62 px una de otra (ventanas de hasta 18 h con una marca por hora, o periodos muy largos), la fecha se pone solo en la primera marca y en cada medianoche. En periodos de más de 36 h la medianoche conserva su línea vertical más visible. El eje creció 12 px hacia abajo y el SVG tiene más margen a la derecha para que la última fecha no se corte.

**Dónde está el código:** bloque del eje de horas de la línea de tiempo (`paso_g`, `fecha_en_todas`) en `reporte-diario/reporte_html.py`.

## 2026-10-15 — Interrupciones de Turbaco del 14-oct excluidas (mismo patrón de las pruebas del 13-oct)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "excluye las interrupciones de Turbaco", tras avisarle que el reporte del 15-oct traía otra vez cortes de una sola casa en Turbaco, de cerca de 1 h cada uno y uno tras otro (Casa 412p 09:28, Casa 415p 11:15 y Casa 447p 14:34 y 15:27), como los de las pruebas de comisionamiento del 13-oct.

**Cómo se aplicó:** `exclusiones.json` → `"eventos_fuera"` suma tres entradas (Casa 412p, Casa 415p y Casa 447p, 14-oct completo, hora de Bogotá). Se descartan sus cortes de red y sus huecos de tensión que empezaron ese día, incluido el hueco de 1 h 10 min de la Casa 447p (14:22 a 15:32), que empezó antes del corte de red y aparecía como "hueco sin corte de red asociado". Quedan en `eventos_descartados` del resumen JSON. Las casas siguen en el reporte para todo lo demás (generación, baterías, inversores, comunicación). No es una exclusión de la ciudad: solo cubre esas casas ese día. Si las pruebas siguen otro día, hay que agregar la casa, el rango de fechas y el motivo; un corte real de la red en Turbaco otro día se sigue contando.

**Pendiente (no aplicado):** un hueco de tensión que empieza antes del corte de red y lo cubre (caso de la Casa 447p) no se asigna a ese corte: el corte sale con "vio 0 s" y el hueco queda como "sin corte de red asociado". Se propuso asignarlo al corte que cubre; el usuario aún no lo pidió.

**Dónde está el código:** `motivo_evento_fuera` en `reporte-diario/reporte_diario.py`; lista en `reporte-diario/exclusiones.json`.

## 2026-10-15 — Etiqueta oculta de "micro corte" en las interrupciones intermedias de menos de 1 min

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Contexto:** en el corte de Cali del 14-oct (23:18, 25 min 50 s) cinco casas Deye (63, 70, 74, 99 y 111) tuvieron una franja roja a mitad de la barra: la casa perdió la tensión unos 31 s con la red ya caída y el inversor alimentándola con batería. Los medidores de red mostraron un solo corte continuo y 0 V a las 23:30, así que no fue un regreso de la red. El hueco intermedio llegó 11 min 04 o 05 s después del primero en las cinco casas, aunque cada una perdió la red en un segundo distinto: apunta a un temporizador interno del inversor.

**Instrucción del usuario:** "colócale una etiqueta oculta de micro corte (los segundos que dura) a todas esas interrupciones intermedias menores a 1 min".

**Cómo se aplicó:** en la gráfica "Cortes de red en la ventana, por casa", cada hueco de tensión de tipo "durante" (a mitad del corte; ni "al caer" ni "al volver") cuya duración total es menor a `MICRO_CORTE_MAX` = 60 s lleva, sobre su franja roja, una zona sensible un poco más ancha con la etiqueta oculta "Micro corte · N s · HH:MM:SS · Casa X · interrupción intermedia con la red caída". Solo se ve al pasar el cursor o al tocar (el script de tooltips táctiles ya la muestra). La columna "Hueco durante" de "Detalle por corte" lleva la misma etiqueta como `title`. Un hueco de 60 s exactos o más no la lleva. No cambia el veredicto de respaldo: sigue pasando a "Caída durante el respaldo" solo si el hueco intermedio dura 2 min o más. Los huecos "al caer" y "al volver" no llevan etiqueta, aunque un primer hueco que empieza más de 75 s después de caer la red (Casas 63 y 70) se clasifica como intermedio y sí la lleva.

**Dónde está el código:** `MICRO_CORTE_MAX`, `es_micro_corte` y `etiqueta_micro_corte` en `reporte-diario/reporte_html.py` (línea de tiempo de cortes por casa y `durante_txt`).

## 2026-10-15 — El límite del micro corte incluye 1 min (60 s)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "la Casa 63 no tiene la etiqueta, valida por favor". Se validó en el reporte publicado: la Casa 63 tenía tres franjas rojas y solo la primera (hueco de 59 s a las 23:19:56) llevaba la etiqueta "Micro corte"; la del medio (23:31:00 a 23:32:00) dura 60 s exactos y quedaba fuera por el criterio "menos de 1 min". El medidor da la hora en segundos enteros, así que 59 s y 60 s no se distinguen, y la Casa 63 es la misma situación de las otras cuatro casas Deye, con los dos huecos del doble de largo (dos reinicios seguidos de unos 30 s).

**Cómo se aplicó:** `es_micro_corte` pasa de `< MICRO_CORTE_MAX` a `<= MICRO_CORTE_MAX` (60 s incluido) comparando en segundos enteros, los mismos que muestra la etiqueta (el hueco de la Casa 63 dura 60,003 s con los milisegundos de los eventos, y con la comparación directa seguía sin etiqueta), en la línea de tiempo de cortes por casa y en la columna "Hueco durante" de "Detalle por corte". Un hueco de más de 60 s sigue sin etiqueta. Los huecos "al caer" y "al volver" (el de 15 s de la Casa 63 al volver la red, p. ej.) siguen sin ella: la etiqueta es solo para las interrupciones intermedias.

**Dónde está el código:** `MICRO_CORTE_MAX` y `es_micro_corte` en `reporte-diario/reporte_html.py`.

## 2026-10-18 — Balanceo de cargas en la Casa 121 CR (viernes 16-oct): huecos de tensión descartados

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "para que lo tengas en cuenta en el reporte de mañana: en la Casa 121 CR estuvimos haciendo balanceo de cargas el viernes para evitar el disparo de la protección de carga del sistema". Se refiere a los tres huecos de tensión del viernes 16-oct que el análisis del fin de semana había marcado como "sin corte de red asociado": 11:41 (19 s), 12:26 a 12:38 (11 min 57 s) y 13:23 a 13:31 (7 min 33 s), con el medidor de red en 124 V y el inversor encendido.

**Cómo se aplicó:** `exclusiones.json` → `"eventos_fuera"` suma una entrada para la Casa 121 CR con el 16-oct completo (hora de Bogotá; motivo "Balanceo de cargas en la casa el viernes 16 oct, para evitar el disparo de la protección de carga del sistema"). Los cortes de red y huecos de tensión de esa casa que empiecen ese día no cuentan en el reporte (el del lunes 19-oct, que va desde el viernes 07:00, los trae) y quedan en `eventos_descartados` del resumen JSON. La casa sigue en el reporte para todo lo demás. Mismo tratamiento que la visita técnica de Gerona (13-oct) y las pruebas de Turbaco.

**Dónde está el código:** `motivo_evento_fuera` en `reporte-diario/reporte_diario.py`; lista en `reporte-diario/exclusiones.json`.

## 2026-10-20 — Casas nuevas en pruebas y estabilización: fuera del reporte hasta que el usuario lo pida (Casa 101)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Instrucción del usuario:** "La Casa 101 es nueva y aún no se ha entregado a operaciones, por favor sácala del reporte; cuando identifiques que son casas nuevas no las incluyas en el reporte hasta que yo te lo pida, porque son sistemas que energizan pero están en etapa de pruebas y estabilización".

**Qué la originó:** el reporte del 20-oct (publicado a las 07:00) salió con 49 sistemas en vez de 48: apareció la Casa 101 (Terra by Kaia, Barranquilla), nueva en Metrum (su inversor reporta desde el 19-oct ~16:00 y el medidor de red desde el 17-oct; sin marca, modelo ni capacidad en los atributos y sin kWp en `potencia_instalada.json`). Entraba al reporte con tres cortes (dos sin respaldo, con SOC de 6 % y 12 %), `igf` ×3, batería en reserva y la mayor exportación (1,81 kWh): todo de una casa en pruebas.

**Cómo se aplicó:**
- `exclusiones.json` → `"fuera": ["Casa 101"]`.
- Regla general (`MOTIVO_NUEVA` y `motivo_exclusion` en `reporte-diario/reporte_diario.py`): toda casa que Metrum tiene y que no está en `potencia_instalada.json` (el registro de las casas en operación) se trata como casa nueva y queda fuera del reporte: no se analiza y aparece en `excluidos` del resumen JSON con el motivo "casa nueva en pruebas y estabilización". `"incluir"` la deja entrar aunque no tenga kWp. Si `potencia_instalada.json` no carga, la regla no se aplica (no se saca a todas las casas). Probado con datos del 20-oct: sin la entrada manual, la Casa 101 sale como casa nueva (48 sistemas); con `"incluir"` entra (49).
- Al revisar el resumen, `sistemas` debe ser 48 (más las casas que el usuario haya pedido incluir). Las casas nuevas excluidas se mencionan en una sola línea al final de la respuesta, para que el usuario decida cuándo incluirlas; no se incluyen por iniciativa propia.
- Para incluir una casa nueva cuando el usuario lo pida: quitarla de `"fuera"` (si está), agregar su kWp a `potencia_instalada.json` (o ponerla en `"incluir"` si aún no hay kWp) y actualizar el número de sistemas esperado en la rutina. Al actualizar `potencia_instalada.json` con un archivo nuevo del usuario no se agregan las casas nuevas que él no haya pedido incluir.
- Mismo criterio para el tablero de baterías (artifact aparte): no incluye casas nuevas.

**Efecto con los datos del 20-oct:** el reporte pasa de 49 a 48 sistemas; los cortes, de 10 en 4 eventos a 7 en 3 (la Casa 101 aportaba tres); y el respaldo global, de 20,2 % a 2,1 %, porque queda dominado por el corte de 1 h 52 min de la Casa 12 (0 % de respaldo).

**Dónde está el código:** `MOTIVO_NUEVA`, `motivo_exclusion` y `main` en `reporte-diario/reporte_diario.py`; lista en `reporte-diario/exclusiones.json`.

## 2026-10-20 — Casa 435p: falla despejada el 19-oct; sigue con problemas de comunicación (en seguimiento del equipo)

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos, Monitor de Salud de Flota.

**Aviso del usuario:** "Ayer se despejó la falla de la Casa 435p, pero sigue con problemas de comunicación". La telemetría de Metrum lo confirma: el inversor (Livoltek HP3-10KL2) estuvo en falla del 19-oct 02:15 al 17:45 (eventos `igf` de 02:00 a 17:30) y desde las 17:45 reporta modo normal. La comunicación del sitio (Turbaco, Prado Verde Primavera) es inestable: caídas del enlace del gateway, del medidor de red, del medidor solar y del inversor el 18 y el 19-oct, y fuera de línea desde el 20-oct 06:29 (último dato del inversor 05:45, con la batería en 13 %).

**Cómo se aplica:**
- La Casa 435p ya no se presenta como inversor en falla. El reporte del 20-oct la listó en "Inversores" (igf ×38) solo porque esos eventos caen dentro de su ventana (19-oct 07:00 a 20-oct 07:00); el punto cuenta los estados de falla de la ventana, no el estado actual. Si vuelve a reportar `fault` o `alarm` después del 19-oct 17:45, se informa como una falla nueva.
- Su problema de comunicación se trata igual que el de las Casas 60p y 382p: está en seguimiento del equipo y, si aparece sin datos, se dice en una línea al final del resumen, sin pedir acciones. A diferencia de ellas, el usuario no ha dicho que la causa sea baja señal; no se afirma una causa.
- Sin cambios en el generador. La nota quedó también en el texto de la rutina diaria.

## 2026-10-21 — El resumen del reporte pasa a medidores circulares con meta y realidad

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos.

**Instrucción del usuario:** "quiero volver este resumen con gráficos circulares tipo desaborad [dashboard] que marquen las metas y la realidad" (21-oct), sobre las seis tarjetas de indicadores de la parte alta del reporte; y, sobre la cobertura: "la cobertura solar es del 90%". Al ver el borrador: "Me gusta, puedes publicarlo por favor". El 22-oct, cuando la rutina de las 06:50 publicó el reporte con las tarjetas anteriores: "Porq al reporte de hoy no le aplicaste los cambios que definimos ayer con los graficos circulares ?"; autorizó subir el cambio al generador del repositorio ("Si subelo").

**Qué la originó:** el 21-oct los medidores se armaron en una copia de trabajo y se publicaron a mano. La rutina diaria genera con el código de la rama `claude/loving-hawking-iwftvn` del repositorio y su regla es no modificar código ni hacer commits, así que el 22-oct salió con el formato anterior. **Un cambio de formato aprobado por el usuario solo llega a la rutina cuando está en el repositorio:** al aprobarlo hay que pedir de inmediato el OK para subirlo (la rutina no puede hacerlo) y decir que, sin eso, el siguiente reporte sale con el formato anterior.

**Cómo se aplicó:** seis medidores (arco = realidad, marca clara = meta, marca tenue = umbral de alerta) y el desplegable "Metas y cálculo de cada indicador":
- Sistemas sin cortes de red: meta, ninguno con cortes (propuesta, por confirmar con el usuario).
- Respaldo: 99 % o más (el umbral de "Respaldo total").
- Generación FV: patrón del portafolio (mediana de la generación total de los días previos, mínimo 3, × los días de la ventana).
- Yield proyectado: yield patrón de la región (1188 Cali, 1323 costa) ponderado por kWp.
- Cobertura solar: 90 % o más (instrucción del usuario).
- Energía exportada del mes: tope de 30 kWh al mes de todo el portafolio (propuesta, por confirmar), acumulado desde el día 1: contador `energyAE` del medidor de red al cierre de la ventana menos el de las 00:00 del día 1; sin dato al cierre se usa el último valor del contador (Casa 447p el 22-oct). El 22-oct iba en 20,6 kWh (69 % del tope).
- La nota de cobertura dice con cuántos sistemas se calculó ("47 de 48 que tienen datos de todos los días de la ventana") y "Límites del análisis" lista las casas y los días sin cierre diario, en vez de un texto fijo. En el mismo cambio quedaron los ajustes para reportes de periodo largo (rótulo del periodo, eje por día, hora mediana de batería llena); en el diario el único efecto es que el yield se divide entre los días con cierre diario de cada casa, lo que solo cambia el lunes.

**Dónde está el código:** `METAS`, `_medidor`, `_estado_ratio` y el bloque "resumen en medidores circulares" en `reporte-diario/reporte_html.py`; `exp_mes` y `exp_ctr_fin` en `analizar` y `main` de `reporte-diario/reporte_diario.py`.

## 2026-10-22 — Datos cada minuto: la lectura de series de Metrum pagina las respuestas

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos.

**Qué la originó:** el 21-oct la Casa 2 pasó de datos cada 15 min a cada minuto (inversor y medidores desde las 10:28–10:31, hora de Bogotá; el usuario: "la frecuencia de datos de la casa 2 cambió a minutal, puedes verlo ?"). Ese mismo día 21 sistemas ya estaban a 1 min y 23 seguían a 15 min. Metrum devuelve a lo sumo `limit` puntos por clave y, en orden ascendente, los más antiguos primero: con una sola respuesta el final del rango se pierde sin avisar. Con datos cada minuto le pasaría al historial de 10 días de `energyPD` (más de 14 000 puntos con un límite de 5000; desde el 25-oct), a la ventana del lunes del medidor de red (84 h, unos 5 050 puntos) y a la hora de batería llena de un día completo (1440 puntos con un límite de 1000).

**Cómo se aplicó:** `serie()` pide el resto de las claves que llegan al límite, desde su último punto y sin duplicar, hasta cubrir el rango; las claves que no llegan al límite no se vuelven a pedir. Probado contra Metrum con la Casa 2: la serie paginada con límites de 1 a 500 es idéntica a la de una sola respuesta, y el reporte del 22-oct y el del lunes 19-oct con el límite en 300 (150 para la batería llena) salen idénticos a los normales (HTML y JSON).

**Dónde está el código:** `serie` en `reporte-diario/reporte_diario.py`.

## 2026-10-22 — Los medidores del resumen son de las últimas 24 horas; el de exportación deja de ser del mes

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos.

**Instrucción del usuario (22-oct):** "te recuerdo que en el reporte diario estos datos son de las ultimas 24 horas de operación" (sobre los seis medidores). Antes había propuesto cambiar el primer medidor: "Los cortes de red del OR yo no los puedo evitar, cambiemos ese kpis por sistemas con respaldo. O no se que opinas tu ?"; al ver el borrador de «Sistemas con respaldo» (sin corte de red, o con respaldo total en todos sus cortes: 47 de 48 el 22-oct, falla la Casa 9G por un corte de red de 6 s) respondió: "como así que 47 sistemas sin respaldo ? mejor deja la metrica de sistemas sin corte de red".

**Cómo se aplicó:**
- El primer medidor sigue siendo «Sistemas sin cortes de red» (informativo: los cortes del operador de red no dependen de Sunny; la meta de que ninguno tenga cortes es una propuesta por confirmar). No volver a proponer «Sistemas con respaldo» salvo que el usuario lo pida; el respaldo ya lo mide el medidor «Respaldo».
- «Energía exportada» pasa de acumulado del mes a las últimas 24 h de la ventana (72 h el lunes): el arco es lo exportado en la ventana (suma de la exportación de cada sistema con dato) y la meta es la parte del tope mensual de 30 kWh que le toca (30 ÷ días del mes × días de la ventana: 0,97 kWh por día en octubre; propuesta, por confirmar). El 22-oct: 0,8 kWh frente a ≤ 1,0 kWh. Debajo va el acumulado del mes ("En oct: 20,6 de 30 kWh (69 %); proyección del mes: 30 kWh"), que no pinta el arco pero pasa el medidor a rojo si supera el tope.
- Generación FV, yield y cobertura siguen siendo del último día completo con cierre diario (regla de cierres), no de las 24 h móviles.

**Dónde está el código:** bloque "6) energía activa exportada en la ventana" del resumen en medidores, en `reporte-diario/reporte_html.py`.

## 2026-10-22 — Meta de exportación: 1 kWh por día

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos.

**Instrucción del usuario:** "la meta de exportación es 1kWh dia". Reemplaza el tope de 30 kWh al mes (una propuesta del agente, nunca confirmada) de las entradas del 21 y del 22-oct.

**Cómo se aplicó:** `METAS["exportacion"] = 1.0` (kWh por día de todo el portafolio). El medidor «Energía exportada» compara lo exportado en la ventana con 1 kWh × los días de la ventana (1,0 kWh en 24 h; 3,0 kWh el lunes): verde dentro de la meta y ámbar por encima. El acumulado del mes y su promedio por día van como texto debajo (22-oct: 20,6 kWh, 0,97 kWh por día); ya no hay tope mensual ni rojo por el mes. Con los datos del 22-oct: 0,8 kWh frente a ≤ 1,0 kWh.

**Dónde está el código:** `METAS` y el bloque "6) energía activa exportada" del resumen en medidores, en `reporte-diario/reporte_html.py`.

## 2026-10-22 — SOC al apagarse la casa sin lectura reciente: el último dato registrado ese mismo día, con *

**Aplica a:** Analista de Disponibilidad y Reportes, Generador de Reportes Operativos Periódicos (reporte diario y reporte ejecutivo del periodo).

**Instrucción del usuario:** el 7-oct, para la leyenda del corte: "a la leyenda del corte le incluiría el SOC al inicio del corte y donde no encuentras dato usa el ultimo dato registrado". El 22-oct, al ver la barra «Sin dato de SOC» en la diapositiva de causas del reporte ejecutivo de octubre: "yo te dije que cuando pase eso tomas el ultimo dato del soc registrado del mismo dia del evento y le puedes colocar un * con la aclaración".

**Cómo se aplicó (reporte ejecutivo de octubre):** el SOC al apagarse la casa es el dato de hasta 30 min antes. Si no hay (inversor sin comunicación), se toma el último dato registrado el mismo día del evento (hora Bogotá), antes del apagón o, si ese día no hubo ninguno antes, el primero posterior; queda marcado con * y la diapositiva (nota al pie y notas del orador) y el libro de soporte (hoja "Huecos por causa") dicen de dónde salió. No hay barra «Sin dato de SOC» mientras exista algún dato ese día. Si ese día no hay ningún dato y el apagón empieza con la red ya de vuelta, se clasifica como demora al volver a la red (con la red de vuelta el SOC no es la causa). No poner un tope de horas al dato: el de 6 h que se había usado era un invento del agente (se atribuyó al generador, que no lo tiene). Octubre: 31 huecos con * (1,2 h de 25,1 h); los dos que estaban sin clasificar eran la Casa 121 CR (02/10, inversor sin comunicación desde la tarde anterior) y la Casa 382p (18/10, inversor sin comunicar 10 días).

**Pendiente de confirmar con el usuario:** el reporte diario (`soc0_viejo` en `reporte-diario/reporte_diario.py` y la leyenda con * de `reporte_html.py`) usa el último dato registrado antes del corte sin límite de día; no se ha ajustado al "mismo día".
