# Reporte diario de operación (Metrum)

Genera el reporte de operación de las últimas 24 horas de toda la flota de Metrum (Cali, Turbaco, Barranquilla y Cartagena).
Se ejecuta de lunes a viernes a las 7:00 a. m. (hora de Bogotá). El lunes cubre desde el viernes a las 7:00, es decir, todo el fin de semana.

## Qué incluye
- Puntos más relevantes, ordenados por gravedad (cortes en curso, inversores aislados, respaldo, baterías en reserva, inversores con falla, rendimiento, exportación, comunicación).
- Interrupciones y respaldo por sistema: cortes de red (medidor de red), tiempo que vio la casa (huecos de tensión del medidor solar, al caer y al volver la red), porcentaje de respaldo y SOC de inicio, mínimo y fin.
- Rendimiento: generación FV por día (`energyPD`), kWh por kW de inversor y comparación con el patrón propio (índice frente a la mediana de su ciudad).
- Exportación de energía activa (`energyAE` del medidor de red), importación y consumo del lado respaldado.
- Comunicación: dispositivos con último dato de más de 2 h.

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
