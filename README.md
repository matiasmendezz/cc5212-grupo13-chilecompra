# CC5212 - Procesamiento Masivo de Datos (Grupo 13)
## Ranking Financiero vs. Centralidad Estructural en ChileCompra (2025)

Repositorio entregable de código, resultados del clúster (`uhadoop`) y análisis del **Grupo 13** para el curso **CC5212-1 (Procesamiento Masivo de Datos, DCC - Universidad de Chile)** sobre las Órdenes de Compra públicas de Chile durante 2025 (`5.141.167` registros de ítems, `1.856.038` órdenes únicas, `1.853.390` órdenes válidas).

---

### Estructura del Repositorio

```text
.
├── 01_preparacion_datos/   # Limpieza de los 12 CSV de ChileCompra y exportación a HDFS
├── 02_pig/                 # Script Apache Pig, validador y salidas oficiales del clúster
├── 03_giraph/              # Salidas oficiales de PageRank en Apache Giraph (Variantes A y B)
├── 04_analisis_cruce/      # Cruce Pig + Giraph, perfiles, métricas y gráficos de dispersión
└── docs/                   # Minutas de preparación de datos y carga al clúster
```

### Detalle por Etapa

1. **`01_preparacion_datos/`**
   - `Proyecto_Ranking_Proveedores_Chile.ipynb`: Notebook de limpieza (45 órdenes corregidas por divisa y 21 anomalías extremas excluidas; gasto limpio de `$18,18 billones CLP`) y exportación de los insumos para HDFS.
   - `procesar_ordenes.py` y `procesar_diciembre.py`: Scripts exploratorios iniciales de los CSV mensuales.

2. **`02_pig/`**
   - `g13_rankings.pig`: Script de **Apache Pig** ejecutado sobre `ordenes_limpias.tsv.bz2` (30 columnas). Genera `ranking_monto`, `ranking_ordenes`, `ranking_organismos`, `concentracion_sector` y `evolucion_mensual`.
   - `verificar_paso4_pig.py`: Validación local de los totales descargados desde HDFS (`75.600` proveedores, `1.853.390` órdenes usadas y `$18,18 billones CLP`).
   - `resultados/`: Los 5 `.tsv` descargados de HDFS y `pig_completo.log`.

3. **`03_giraph/`**
   - `resultados/pr_dirigido_s.tsv`: PageRank **Variante A** (grafo dirigido $O \to P$, Lab 8, 4 workers, 10 iteraciones, ordenado con `SortByRank`).
   - `resultados/pr_bidireccional_s.tsv`: PageRank **Variante B** (grafo bidireccional $O \leftrightarrow P$, misma configuración).

4. **`04_analisis_cruce/`**
   - `cruzar_resultados_cluster.py` y `analisis_cruce.py`: Scripts de cruce Pig + Giraph, correlación de Spearman, índice de Gini y extracción de los dos perfiles solicitados por la cátedra.
   - `variante_A/` y `variante_B/`: `resumen.txt`, `perfil1_detalle.csv`, `perfil2_detalle.csv` y `dispersion_monto_vs_pagerank.png`.

5. **`docs/`**
   - `Resumen_preparacion_datos_G13.pdf`: Resumen de calidad de datos y reglas de limpieza.
   - `Carga_cluster_y_proximos_pasos_G13.pdf`: Bitácora de carga a HDFS y plan de ejecución en el clúster.
