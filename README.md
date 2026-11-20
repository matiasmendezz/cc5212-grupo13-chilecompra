# CC5212 - Procesamiento Masivo de Datos (Grupo 13)
## Ranking Financiero vs. Centralidad Estructural en ChileCompra (2025)

Repositorio entregable de código, resultados del clúster y análisis del **Grupo 13** para el curso **CC5212-1 (Procesamiento Masivo de Datos, DCC - Universidad de Chile)** sobre las Órdenes de Compra públicas de Chile durante el año 2025 (`5.141.167` registros de ítems, `1.856.038` órdenes únicas, `1.853.390` órdenes válidas).

---

### Estructura del Repositorio

- **`dataset/`**: Preparación y limpieza de los 12 CSV mensuales de MercadoPúblico.
  - `Proyecto_Ranking_Proveedores_Chile.ipynb`: Notebook de limpieza (45 órdenes corregidas por divisa y 21 anomalías extremas excluidas; gasto limpio de `$18,18 billones CLP`) y exportación de los insumos para HDFS.
  - `Resumen_preparacion_datos_G13.pdf`: Resumen de la etapa de preparación de datos.
  - `procesar_ordenes.py`, `procesar_diciembre.py`: Scripts exploratorios iniciales.
- **`Carga_cluster_y_proximos_pasos_G13.pdf`**: Bitácora de carga a HDFS y plan de ejecución en el clúster (`uhadoop`).
- **`g13_rankings.pig`**: Script de **Apache Pig** ejecutado en el clúster sobre `ordenes_limpias.tsv.bz2` (30 columnas). Genera `ranking_monto`, `ranking_ordenes`, `ranking_organismos`, `concentracion_sector` y `evolucion_mensual`.
- **`verificar_paso4_pig.py`**: Script de validación de totales descargados desde HDFS contra las cifras de control (`75.600` proveedores, `1.853.390` órdenes usadas y `$18,18 billones CLP`).
- **`resultados_pig/`**: Salidas oficiales descargadas desde HDFS tras ejecutar `g13_rankings.pig` (`ranking_monto.tsv`, `ranking_ordenes.tsv`, `ranking_organismos.tsv`, `concentracion_sector.tsv`, `evolucion_mensual.tsv` y `pig_completo.log`).
- **`resultados_giraph/`**: Salidas oficiales de **Apache Giraph** (Lab 8, 4 workers, 10 iteraciones) ordenadas con `SortByRank`:
  - `pr_dirigido_s.tsv` (Variante A: grafo dirigido $O \to P$).
  - `pr_bidireccional_s.tsv` (Variante B: grafo bidireccional $O \leftrightarrow P$).
- **`analisis_cruce/`**: Scripts de cruce Pig + Giraph y caracterización de perfiles (`cruzar_resultados_cluster.py`, `analisis_cruce.py`), junto con `resumen.txt`, detalle de perfiles (`perfil1_detalle.csv`, `perfil2_detalle.csv`) y gráficos de dispersión para `variante_A/` y `variante_B/`.
