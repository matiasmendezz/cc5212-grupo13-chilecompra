-- ============================================================================
-- CC5212 - Procesamiento Masivo de Datos (Grupo 13)
-- Archivo: g13_rankings.pig
--
-- Objetivo (Sección 4):
--   1. Ranking de proveedores por monto total limpio (ranking_monto)
--   2. Ranking de proveedores por número de órdenes distintas (ranking_ordenes)
--   3. Ranking de proveedores por número de organismos distintos (ranking_organismos)
--   4. Concentración del gasto por sector del Estado (concentracion_sector)
--   5. Evolución mensual del gasto y órdenes (evolucion_mensual)
--
-- Reglas respetadas:
--   - Filtrar la cabecera (codigo != 'codigo') y quedarse solo con usar == 1.
--   - Sumar monto_clp_limpio (tratando vacíos/null como 0.0), no monto_clp.
--   - Contar órdenes con COUNT y organismos únicos con DISTINCT cod_organismo.
-- ============================================================================

-- 1. Carga del archivo de 30 columnas generado en Colab (ordenes_muestra.tsv u ordenes_limpias.tsv.bz2)
ordenes_raw = LOAD '$ENTRADA' USING PigStorage('\t') AS (
    codigo:chararray,
    mes:int,
    fecha_envio:chararray,
    fecha_creacion:chararray,
    fecha_aceptacion:chararray,
    estado:chararray,
    estado_proveedor:chararray,
    tipo:chararray,
    procedencia:chararray,
    cod_licitacion:chararray,
    cod_convenio_marco:chararray,
    moneda:chararray,
    monto_original:double,
    monto_clp:double,
    monto_clp_corr:double,
    monto_corregido:int,
    monto_clp_limpio:double,
    flag_monto:chararray,
    n_items:int,
    cod_organismo:chararray,
    organismo:chararray,
    sector:chararray,
    region_comprador:chararray,
    proveedor_id:chararray,
    rut_proveedor:chararray,
    nombre_proveedor:chararray,
    es_persona_natural:chararray,
    region_proveedor:chararray,
    actividad_proveedor:chararray,
    usar:int
);

-- 2. Filtrar la cabecera y quedarse únicamente con las órdenes válidas (usar == 1)
ordenes_filtradas = FILTER ordenes_raw BY (codigo != 'codigo') AND (usar == 1);

-- 3. Proyectar solo las columnas necesarias y tratar los vacíos (null) de monto_clp_limpio como 0.0
ordenes_limpias = FOREACH ordenes_filtradas GENERATE
    codigo,
    mes,
    cod_organismo,
    sector,
    proveedor_id,
    nombre_proveedor,
    (monto_clp_limpio IS NULL ? 0.0 : monto_clp_limpio) AS monto_limpio;

-- ============================================================================
-- A. MÉTRICAS Y RANKINGS POR PROVEEDOR (Monto, Órdenes y Organismos Distintos)
-- ============================================================================
por_proveedor = GROUP ordenes_limpias BY (proveedor_id, nombre_proveedor);

metricas_proveedor = FOREACH por_proveedor {
    orgs_distintos = DISTINCT ordenes_limpias.cod_organismo;
    GENERATE
        FLATTEN(group) AS (proveedor_id, nombre_proveedor),
        SUM(ordenes_limpias.monto_limpio) AS monto_total_clp,
        COUNT(ordenes_limpias) AS n_ordenes,
        COUNT(orgs_distintos) AS n_organismos;
};

-- A.1 Ranking por Monto Total Limpio
ranking_monto = ORDER metricas_proveedor BY monto_total_clp DESC, n_ordenes DESC;
STORE ranking_monto INTO '$SALIDA/ranking_monto' USING PigStorage('\t');

-- A.2 Ranking por Número de Órdenes Distintas
ranking_ordenes = ORDER metricas_proveedor BY n_ordenes DESC, monto_total_clp DESC;
STORE ranking_ordenes INTO '$SALIDA/ranking_ordenes' USING PigStorage('\t');

-- A.3 Ranking por Número de Organismos Compradores Distintos
ranking_organismos = ORDER metricas_proveedor BY n_organismos DESC, monto_total_clp DESC;
STORE ranking_organismos INTO '$SALIDA/ranking_organismos' USING PigStorage('\t');

-- ============================================================================
-- B. CONCENTRACIÓN DEL GASTO POR SECTOR DEL ESTADO
-- ============================================================================
por_sector = GROUP ordenes_limpias BY sector;

metricas_sector = FOREACH por_sector {
    orgs_sector = DISTINCT ordenes_limpias.cod_organismo;
    provs_sector = DISTINCT ordenes_limpias.proveedor_id;
    GENERATE
        group AS sector,
        SUM(ordenes_limpias.monto_limpio) AS monto_total_clp,
        COUNT(ordenes_limpias) AS n_ordenes,
        COUNT(orgs_sector) AS n_organismos,
        COUNT(provs_sector) AS n_proveedores;
};

concentracion_sector = ORDER metricas_sector BY monto_total_clp DESC;
STORE concentracion_sector INTO '$SALIDA/concentracion_sector' USING PigStorage('\t');

-- ============================================================================
-- C. EVOLUCIÓN MENSUAL DEL GASTO (Meses 1 a 12)
-- ============================================================================
por_mes = GROUP ordenes_limpias BY mes;

metricas_mes = FOREACH por_mes {
    provs_mes = DISTINCT ordenes_limpias.proveedor_id;
    orgs_mes = DISTINCT ordenes_limpias.cod_organismo;
    GENERATE
        group AS mes,
        SUM(ordenes_limpias.monto_limpio) AS monto_total_clp,
        COUNT(ordenes_limpias) AS n_ordenes,
        COUNT(provs_mes) AS n_proveedores,
        COUNT(orgs_mes) AS n_organismos;
};

evolucion_mensual = ORDER metricas_mes BY mes ASC;
STORE evolucion_mensual INTO '$SALIDA/evolucion_mensual' USING PigStorage('\t');
