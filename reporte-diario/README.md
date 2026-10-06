# Reporte diario de operación (Metrum)

Genera el reporte de operación de las últimas 24 horas de toda la flota de Metrum (Cali, Turbaco, Barranquilla y Cartagena).
Se ejecuta de lunes a viernes a las 7:00 a. m. (hora de Bogotá). El lunes cubre desde el viernes a las 7:00, es decir, todo el fin de semana.

## Qué incluye
- Puntos más relevantes, ordenados por gravedad (cortes en curso, inversores aislados, respaldo, baterías en reserva, inversores con falla, rendimiento, exportación, comunicación).
- Resumen por ciudad: generación FV, yield anual proyectado, cobertura solar (generación ÷ consumo de los clientes) y cortes de red.
- Interrupciones por sistema ("Por sistema"): cortes de red (medidor de red), tiempo que vio la casa (huecos de tensión del medidor solar), estado "Ahora" y **veredicto de respaldo** (ver abajo). Una columna por corte: el **último corte registrado** de cada casa va completo (inicio → fin, duración, SOC inicio → fin, % de respaldo, fórmula del equipo: (T red − T solar) / T red, y el veredicto de respaldo de ese mismo corte, sin leyendas de otros cortes); los cortes anteriores (del más reciente al más antiguo, hasta 4) van solo con la leyenda de su % de respaldo, con hora y duración al pasar el cursor; si una casa tiene más, el resto queda en el desplegable "Detalle por corte" (todos los cortes, con huecos al caer y al volver).
- Casas solo con baterías (sin FV), en su propia tabla: cortes, tiempo sin red, respaldo, SOC inicio → mín → fin del mayor corte, SOC actual (último dato del inversor, con su hora) y estado "Ahora". Entran todas las casas excluidas por `exclusiones.json` o por la regla automática de "sin generación FV" (inversor que no pasa de 5 kWh/día en 5 días o más), no los pilotos. No suman en generación, yield, cobertura ni exportación; sus eventos del inversor (p. ej. `igf`) sí cuentan en "Inversores".
- Punto "Baterías en reserva": todos los sistemas (también los solo-baterías, tengan o no corte) cuyo último SOC es de 22 % o menos (`RESERVA`); la hora de cada dato se muestra solo si tiene más de 30 min respecto del corte del reporte.
- Rendimiento: generación FV diaria por balance de medidores, yield en kWh/kWp y comparación con el patrón propio de cada casa.
- Exportación de energía activa (`energyAE` del medidor de red), importación y consumo del lado respaldado.
- Comunicación: dispositivos con último dato de más de 2 h.

## Reglas de cálculo (todas decididas por el usuario; detalle en `om-agency/references/reglas-aprendidas.md`)
- **Generación** = balance de medidores con cierres diarios de las 00:00 Bogotá: demanda del medidor solar (`CenergyAI`) − importada + exportada del medidor de red. Nunca `energyPD` del inversor (subestima ~10× en inversores nuevos). Sin cierre diario del medidor: "sin cierre diario del medidor", fuera de las sumas.
- **Yield anual proyectado** = Σ generación diaria real ÷ Σ kWp instalados (`potencia_instalada.json`, de `Casas_V2.xlsx`, pico DC, no kW de inversor; Casas 412p y 425p: 9 paneles, 5,36 kWp) × 365.
- **Cobertura solar** = generación ÷ consumo de los clientes (demanda del medidor solar).
- **Corte en curso**: el inversor sin red (`voltGrid* < 5 V`) y el medidor de red sin dato posterior a la caída (un medidor sin tensión deja de enviar: se compara el timestamp, no el último valor).
- **Veredicto de respaldo por corte** (`veredicto_respaldo` en `reporte_diario.py`): sin hueco en el medidor solar → *Respaldo total*; hueco "al caer" corto (transferencia a isla) → *Respaldo total con transferencia*; hueco "durante" ≥ 2 min → *Caída durante el respaldo* (causa: batería agotada si SOC ≤ 12 %, si no "revisar inversor"); corte más corto que la transferencia y cobertura < 5 % → *Sin respaldo*; si el cliente ve más de 1 min sin tensión al caer la red (el primer hueco "al caer" más los que le siguen pegados, con menos de 60 s de tensión en medio: algunos Deye cortan dos veces con ~9 s de por medio; los huecos separados a mitad del corte o al volver la red no se suman) con la batería cargada (SOC al inicio del corte > 22 %) → *Retardo de transferencia* (la celda muestra la duración y el SOC). Prioridad: caída durante el respaldo, sin respaldo, retardo de transferencia, transferencia normal. "Alimenta": mediana de `BattPower` en el corte (>200 W batería, < −200 W solar, si no solar + batería llena). En cortes abiertos el veredicto es provisional. Cada hueco del medidor solar cuenta en **un solo corte**: el que empieza hasta 75 s de su inicio (al caer), si no el que lo contiene, si no el último que terminó hasta 10 min antes (al volver/reconectar).
- **No usar** un umbral de tensión del medidor solar (p. ej. 130 V) para decidir si hay respaldo: no se cumple en todos los sistemas (Casa 99 respaldó con 119–123 V).
- Nunca la palabra "flota": usar "conjunto de sistemas" o "portafolio Sunny".
- Pilotos (Promigas) excluidos siempre. Casa 447p, solo baterías: excluida de generación, yield y cobertura (ver `exclusiones.json`), pero se reporta en la tabla de casas solo con baterías.

## Estilo del reporte
`estilos.css` + `EXTRA_CSS` de `reporte_html.py` (encabezados de tablas con `<br>` y fuente 9,5 px para que no se apilen). Referencia visual: `ejemplo/reporte_2026-10-06.html` (versión publicada del 6 de octubre; su tabla de la Casa 447p y los puntos "Baterías en reserva" e "Inversores igf" se agregaron a mano y hoy los genera el script). Publicar el HTML como Artifact actualizando siempre la misma URL del reporte diario.

## Uso
```
python3 reporte-diario/reporte_diario.py                       # ventana automática que termina ahora
python3 reporte-diario/reporte_diario.py --fin 2026-10-05T07:00 --inicio 2026-10-02T07:00
```
Salida: `reporte_diario.html` (fragmento listo para publicar como Artifact) y `resumen_diario.json` (cifras y puntos relevantes).

Requiere las variables `METRUM_API_URL`, `METRUM_USERNAME` y `METRUM_PASSWORD`. Solo lee datos de Metrum.

## Reglas del equipo aplicadas
- Inversor sin red: `voltGridA/B/C < 5 V` (nunca igualdad exacta a 0). Si el medidor de red marca tensión, se reporta como inversor aislado y no como corte de red.
- Se revisa el timestamp del último dato de cada dispositivo antes de afirmar su estado.
- Sin hueco de tensión en el medidor solar, el cliente no percibió el corte (respaldo del 100 %).

## Pendientes conocidos
- Casas 9G y 108 sin cierre diario del 6-oct en el medidor: quedan sin generación hasta que llegue el cierre.
- Depuración: `DUMP_SV=f.json` y `DUMP_PK=f.pkl` guardan datos intermedios sin tocar el reporte.
