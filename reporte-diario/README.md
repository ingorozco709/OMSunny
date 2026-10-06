# Reporte diario de operación (Metrum)

Genera el reporte de operación de las últimas 24 horas de toda la flota de Metrum (Cali, Turbaco, Barranquilla y Cartagena).
Se ejecuta de lunes a viernes a las 7:00 a. m. (hora de Bogotá). El lunes cubre desde el viernes a las 7:00, es decir, todo el fin de semana.

## Qué incluye
- Puntos más relevantes, ordenados por gravedad (cortes en curso, inversores aislados, respaldo, baterías en reserva, inversores con falla, rendimiento, exportación, comunicación).
- Resumen por ciudad: generación FV, yield anual proyectado, cobertura solar (generación ÷ consumo de los clientes) y cortes de red.
- Interrupciones por sistema ("Por sistema"): cortes de red (medidor de red), tiempo que vio la casa (huecos de tensión del medidor solar), % de respaldo del peor corte (fórmula del equipo: (T red − T solar) / T red), SOC al inicio y al final del mayor corte, estado "Ahora" y **veredicto de respaldo** (ver abajo). Detalle por corte en un desplegable.
- Rendimiento: generación FV diaria por balance de medidores, yield en kWh/kWp y comparación con el patrón propio de cada casa.
- Exportación de energía activa (`energyAE` del medidor de red), importación y consumo del lado respaldado.
- Comunicación: dispositivos con último dato de más de 2 h.

## Reglas de cálculo (todas decididas por el usuario; detalle en `om-agency/references/reglas-aprendidas.md`)
- **Generación** = balance de medidores con cierres diarios de las 00:00 Bogotá: demanda del medidor solar (`CenergyAI`) − importada + exportada del medidor de red. Nunca `energyPD` del inversor (subestima ~10× en inversores nuevos). Sin cierre diario del medidor: "sin cierre diario del medidor", fuera de las sumas.
- **Yield anual proyectado** = Σ generación diaria real ÷ Σ kWp instalados (`potencia_instalada.json`, de `Casas.xlsx`, pico DC, no kW de inversor) × 365.
- **Cobertura solar** = generación ÷ consumo de los clientes (demanda del medidor solar).
- **Corte en curso**: el inversor sin red (`voltGrid* < 5 V`) y el medidor de red sin dato posterior a la caída (un medidor sin tensión deja de enviar: se compara el timestamp, no el último valor).
- **Veredicto de respaldo por corte** (`veredicto_respaldo` en `reporte_diario.py`): sin hueco en el medidor solar → *Respaldo total*; solo hueco "al caer" de ≤ 2 min (transferencia a isla) → *Respaldo total con transferencia*; hueco "durante" ≥ 2 min → *Caída durante el respaldo* (causa: batería agotada si SOC ≤ 12 %, si no "revisar inversor"); corte más corto que la transferencia y cobertura < 5 % → *Sin respaldo*. "Alimenta": mediana de `BattPower` en el corte (>200 W batería, < −200 W solar, si no solar + batería llena). En cortes abiertos el veredicto es provisional.
- **No usar** un umbral de tensión del medidor solar (p. ej. 130 V) para decidir si hay respaldo: no se cumple en todos los sistemas (Casa 99 respaldó con 119–123 V).
- Nunca la palabra "flota": usar "conjunto de sistemas" o "portafolio Sunny".
- Pilotos (Promigas) excluidos siempre; Casa 447p solo baterías, excluida (ver `exclusiones.json`).

## Estilo del reporte
`estilos.css` + `EXTRA_CSS` de `reporte_html.py` (encabezados de tablas con `<br>` y fuente 9,5 px para que no se apilen). Referencia visual: `ejemplo/reporte_2026-10-06.html` (versión publicada del 6 de octubre; incluye una tabla manual de la Casa 447p, que el generador no produce). Publicar el HTML como Artifact actualizando siempre la misma URL del reporte diario.

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
- La tabla "Casa solo con baterías (sin FV)" y los puntos "Baterías en reserva" / "Inversores igf" del reporte publicado del 6-oct se agregaron a mano; el generador aún no los produce.
- Depuración: `DUMP_SV=f.json` y `DUMP_PK=f.pkl` guardan datos intermedios sin tocar el reporte.
