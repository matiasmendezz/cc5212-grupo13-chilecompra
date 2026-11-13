# CC5212 - Procesamiento Masivo de Datos (Grupo 13)
## Ranking Financiero vs. Centralidad Estructural en ChileCompra (2025)

Repositorio de código y documentación del proyecto del **Grupo 13** para el curso **CC5212-1 (Procesamiento Masivo de Datos, DCC - Universidad de Chile)** sobre las Órdenes de Compra públicas de Chile durante el año 2025 (`5.141.167` / `5.141.233` registros de ítems, `1,85 millones` de órdenes únicas).

---

### Estructura del Repositorio

- **`g13_rankings.pig`**: Script oficial de **Apache Pig** para ejecutar en el clúster (`uhadoop`), compatible con el esquema de 30 columnas de `ordenes_limpias.tsv.bz2`. Genera:
  - `ranking_monto` (por monto total limpio CLP)
  - `ranking_ordenes` (por número de órdenes válidas)
  - `ranking_organismos` (por cantidad de organismos compradores distintos)
  - `concentracion_sector` (gasto por sector del Estado)
  - `evolucion_mensual` (gasto y órdenes meses 1 a 12)
- **`verificar_paso4_pig.py`**: Script auxiliar para validar localmente las salidas descargadas desde HDFS contra las métricas de control (`~75.600` proveedores, `~1.853.390` órdenes usadas y `~$18,18 billones CLP`).
- **`resultados_pig/`**: Salidas oficiales descargadas desde HDFS tras ejecutar `g13_rankings.pig` en el clúster (`ranking_monto.tsv`, `ranking_ordenes.tsv`, `ranking_organismos.tsv`, `concentracion_sector.tsv`, `evolucion_mensual.tsv` y el log `pig_completo.log`).
- **`dataset/`**:
  - `Proyecto_Ranking_Proveedores_Chile.ipynb`: Notebook de preparación, limpieza de divisas (45 órdenes corregidas y 21 anomalías extremas excluidas) y exportación de tablas/grafos.
  - `Resumen_preparacion_datos_G13.pdf`: Minuta de preparación de datos.
  - `procesar_ordenes.py`, `procesar_diciembre.py`: Scripts iniciales de exploración de CSVs.
- **`proyecto_local/`**:
  - `01_auditoria_csv.py`, `02_generar_datos_y_grafos.py`, `03_rankings_y_pagerank.py`, `04_metricas_avanzadas_y_graficos.py`: Pipeline completo ejecutado en Python multiproceso, incluyendo cálculo de 4 variantes de PageRank, análisis de Gini/Lorenz y extracción de los 2 perfiles del profesor.
  - `cluster_code/`: Código para **Apache Pig** y **Apache Giraph** (`WeightedPageRankComputation.java`, `WeightedPageRankJsonComputation.java`, `preparar_input_giraph.py`, `cruzar_resultados_cluster.py`, `rankings_chilecompra*.pig`).
  - `informe_latex/`: Fuentes `.tex`, figuras vectoriales (`figuras/`) y PDFs generados (`informe_final_G13.pdf`, `guia_proyecto_cluster_G13.pdf`).
- **`Carga_cluster_y_proximos_pasos_G13.pdf`**: Bitácora de carga a HDFS y hoja de ruta de ejecución en el clúster.
