# CC5212 - Procesamiento Masivo de Datos (Grupo 13)
## Ranking Financiero vs. Centralidad Estructural en ChileCompra (2025)

Repositorio entregable de código, resultados del clúster (`uhadoop`) y análisis del **Grupo 13** para el curso **CC5212-1 (Procesamiento Masivo de Datos, DCC - Universidad de Chile)** sobre las Órdenes de Compra públicas de Chile durante 2025 (`5.141.167` registros de ítems, `1.856.038` órdenes únicas, `1.853.390` órdenes válidas).

---

### Estructura del Repositorio

```text
.
├── 01_preparacion_datos/   # Limpieza de los 12 CSV de ChileCompra y exportación a HDFS
├── 02_pig/                 # Scripts Apache Pig, validador, salidas y logs oficiales del clúster
├── 03_giraph/              # Código fuente Java (Lab 8 + Ponderado), script Pig de pesos y salidas
├── 04_analisis_cruce/      # Cruce Pig + Giraph, perfiles, métricas y gráficos (variantes A, B y W)
└── docs/                   # Minutas de preparación de datos y carga al clúster
```

---

### Detalle por Etapa

1. **`01_preparacion_datos/`**
   - `MDP_G13_notebook_v2.ipynb`: Notebook ejecutado de preparación y limpieza (45 órdenes corregidas por divisa y 21 anomalías extremas excluidas; gasto limpio de `$18,18 billones CLP`), exportación de insumos para HDFS (`ordenes_limpias.tsv.bz2`, `aristas.tsv`, `aristas_bidireccional.tsv`, `aristas_ponderadas.tsv`, `nodos.tsv`) y tablas de control.
   - `procesar_ordenes.py` y `procesar_diciembre.py`: Scripts exploratorios iniciales de los CSV mensuales.

2. **`02_pig/`**
   - `g13_rankings.pig`: Script principal de **Apache Pig** ejecutado sobre `ordenes_limpias.tsv.bz2` (30 columnas). Genera `ranking_monto`, `ranking_ordenes`, `ranking_organismos`, `concentracion_sector` y `evolucion_mensual`.
   - `g13_ranking_mensual.pig`: Script de **Apache Pig** que obtiene el Top 10 de proveedores por monto limpio en cada uno de los 12 meses (`120` filas).
   - `verificar_paso4_pig.py`: Validación local de los totales descargados desde HDFS (`75.600` proveedores, `1.853.390` órdenes usadas y `$18,18 billones CLP`). Se ejecuta pasando la carpeta de resultados (por defecto `02_pig/resultados`):
     ```bash
     python3 02_pig/verificar_paso4_pig.py 02_pig/resultados
     ```
   - `resultados/`:
     - `ranking_monto.tsv`, `ranking_ordenes.tsv`, `ranking_organismos.tsv`, `concentracion_sector.tsv`, `evolucion_mensual.tsv` y `ranking_mensual.tsv`.
     - `pig_completo.log` (tiempo total: `5m 25,5s`, 11 jobs MapReduce) y `pig_mensual.log` (tiempo total: `3m 59,7s`).

3. **`03_giraph/`**
   - `g13_aristas_peso.pig`: Script Pig que construye el grafo bidireccional ponderado con peso $w_{uv} = \ln(1 + \text{monto})$ (`953.406` aristas en `/uhadoop2026/projects/grupo13/aristas_bidir_log`; tiempo: `37,2s`).
   - `src/`: Código fuente Java del proyecto `mdp-giraph`:
     - Clases base del Laboratorio 8: `Main.java`, `PageRank.java`, `PageRankRunner.java`, `SortByRank.java`, `TextNullTextEdgeInputFormat.java`, `VertexValueTextOutputFormat.java`, `PageRankAgg.java`.
     - Clases nuevas para PageRank Ponderado: `WeightedPageRank.java`, `WeightedPageRankRunner.java` y `TextDoubleTextEdgeInputFormat.java`.
   - `resultados/`: Salidas de **Apache Giraph** (10 iteraciones, $d = 0,85$, 4 workers) ordenadas globalmente con `SortByRank`:
     - `pr_dirigido_s.tsv`: **Variante A** (grafo dirigido $O \to P$, sin pesos).
     - `pr_bidireccional_s.tsv`: **Variante B** (grafo bidireccional $O \leftrightarrow P$, sin pesos).
     - `pr_ponderado_s.tsv` y `giraph_ponderado.log`: **Variante W** (grafo bidireccional $O \leftrightarrow P$ con peso $\ln(1 + \text{monto})$; tiempo: `real 0m 59,7s`, `time elapsed 48.769 ms`, 4 workers).

4. **`04_analisis_cruce/`**
   - `cruzar_resultados_cluster.py` y `analisis_cruce.py`: Scripts de cruce entre `02_pig/resultados/ranking_monto.tsv`, `nodos.tsv` y las salidas de Giraph, cálculo de correlación de Spearman, índice de Gini (`0,944`) y clasificación de perfiles (criterio `etapa3`).
   - **Nota sobre `nodos.tsv`:** Este archivo no se almacena en el repositorio por tamaño y se descarga desde HDFS antes de ejecutar el cruce:
     ```bash
     hdfs dfs -get /uhadoop2026/projects/grupo13/nodos.tsv .
     ```
   - `variante_A/` (dirigido), `variante_B/` (bidireccional sin pesos) y `variante_W/` (bidireccional ponderado $\ln(1+\text{monto})$): cada carpeta contiene `resumen.txt`, `perfil1_detalle.csv`, `perfil2_detalle.csv` y `dispersion_monto_vs_pagerank.png`.

5. **`docs/`**
   - `Resumen_preparacion_datos_G13.pdf`: Resumen de calidad de datos y reglas de limpieza.
   - `Carga_cluster_y_proximos_pasos_G13.pdf`: Bitácora de carga a HDFS y plan de ejecución en el clúster.

---

### Comandos Ejecutados en el Clúster (`uhadoop`) y Tiempos Registrados

#### 1. Apache Pig (Rankings principales, ranking mensual y grafo ponderado)
```bash
# Rankings principales y agregaciones (real: 5m 25,5s | Pig: 5m 22,7s)
time pig -param ENTRADA=/uhadoop2026/projects/grupo13/ordenes_limpias.tsv.bz2 \
    -param SALIDA=/uhadoop2026/projects/grupo13/pig_resultados_v2 \
    g13_rankings.pig 2>&1 | tee pig_completo.log

# Top 10 de proveedores por mes (real: 3m 59,7s | Pig: 3m 56,6s)
time pig -param ENTRADA=/uhadoop2026/projects/grupo13/ordenes_limpias.tsv.bz2 \
    -param SALIDA=/uhadoop2026/projects/grupo13/pig_mensual \
    g13_ranking_mensual.pig 2>&1 | tee pig_mensual.log

# Construcción de aristas bidireccionales con peso ln(1 + monto) (Pig: 37,2s)
pig g13_aristas_peso.pig
```

#### 2. Apache Giraph (4 workers, 10 iteraciones) y `SortByRank`
```bash
# Variante A (dirigido sin pesos) y Variante B (bidireccional sin pesos) - 4 workers
hadoop jar mdp-giraph.jar PageRankRunner \
    /uhadoop2026/projects/grupo13/aristas.tsv \
    /uhadoop2026/projects/grupo13/pr_dirigido 4

hadoop jar mdp-giraph.jar PageRankRunner \
    /uhadoop2026/projects/grupo13/aristas_bidireccional.tsv \
    /uhadoop2026/projects/grupo13/pr_bidireccional 4

# Variante W (bidireccional ponderado ln(1 + monto)) - 4 workers (real: 0m 59,7s | Giraph: 48,8s)
time hadoop jar mdp-giraph-weighted.jar WeightedPageRankRunner \
    /uhadoop2026/projects/grupo13/aristas_bidir_log \
    /uhadoop2026/projects/grupo13/pr_ponderado 4 2>&1 | tee giraph_ponderado.log

# Ordenamiento global de resultados con 1 reducer
hadoop jar mdp-giraph-weighted.jar SortByRank -D mapreduce.job.reduces=1 \
    /uhadoop2026/projects/grupo13/pr_ponderado \
    /uhadoop2026/projects/grupo13/pr_ponderado_s
```

#### 3. Cruce y análisis de perfiles (ejecutado desde la raíz del repositorio)
```bash
python3 04_analisis_cruce/cruzar_resultados_cluster.py nodos.tsv \
    02_pig/resultados/ranking_monto.tsv 03_giraph/resultados/pr_bidireccional_s.tsv \
    --criterio etapa3 --salida cruce_B_etapa3

python3 04_analisis_cruce/cruzar_resultados_cluster.py nodos.tsv \
    02_pig/resultados/ranking_monto.tsv 03_giraph/resultados/pr_ponderado_s.tsv \
    --criterio etapa3 --salida cruce_W_etapa3

python3 04_analisis_cruce/analisis_cruce.py cruce_W_etapa3 \
    --alt cruce_B_etapa3 --etiqueta "Ponderado" --salida 04_analisis_cruce/variante_W
```
