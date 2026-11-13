-- ============================================================================
-- CC5212 - Procesamiento Masivo de Datos (Grupo 13)
-- Script Apache Pig compatible 100% con el archivo ordenes_limpias.tsv (30 cols)
-- generado en la Celda 11 de Proyecto_Ranking_Proveedores_Chile.ipynb
-- ============================================================================

-- 1. Carga de las 30 columnas exportadas por el Colab del Grupo 13
raw_orders = LOAD '$INPUT_ORDENES' USING PigStorage('\t') AS (
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

-- 2. Filtrar órdenes válidas (usar == 1 descarta automáticamente la cabecera y las 2.648 excluidas)
valid_orders = FILTER raw_orders BY usar == 1;

-- 3. Agrupar por Proveedor y calcular métricas financieras y de red
by_provider = GROUP valid_orders BY (proveedor_id, rut_proveedor, nombre_proveedor, es_persona_natural);

provider_metrics = FOREACH by_provider {
    orgs_unicos = DISTINCT valid_orders.cod_organismo;
    GENERATE
        FLATTEN(group) AS (proveedor_id, rut_proveedor, nombre_proveedor, es_persona_natural),
        SUM(valid_orders.monto_clp_limpio) AS monto_total_clp,
        COUNT(valid_orders) AS total_ordenes,
        COUNT(orgs_unicos) AS total_organismos_distintos;
};

-- 4. Ranking por Monto Total Limpio (CLP)
rank_by_monto = ORDER provider_metrics BY monto_total_clp DESC;
STORE rank_by_monto INTO '$OUTPUT_DIR/ranking_por_monto' USING PigStorage('\t');

-- 5. Ranking por Cantidad de Órdenes Distintas
rank_by_ordenes = ORDER provider_metrics BY total_ordenes DESC;
STORE rank_by_ordenes INTO '$OUTPUT_DIR/ranking_por_ordenes' USING PigStorage('\t');

-- 6. Ranking por Cantidad de Organismos Compradores Distintos (Capilaridad)
rank_by_organismos = ORDER provider_metrics BY total_organismos_distintos DESC;
STORE rank_by_organismos INTO '$OUTPUT_DIR/ranking_por_organismos' USING PigStorage('\t');

-- 7. Concentración de Gasto por Sector del Estado
by_sector = GROUP valid_orders BY sector;
sector_metrics = FOREACH by_sector {
    orgs_sec = DISTINCT valid_orders.cod_organismo;
    provs_sec = DISTINCT valid_orders.proveedor_id;
    GENERATE
        group AS sector,
        SUM(valid_orders.monto_clp_limpio) AS monto_sector_clp,
        COUNT(valid_orders) AS ordenes_sector,
        COUNT(orgs_sec) AS organismos_sector,
        COUNT(provs_sec) AS proveedores_sector;
};
rank_sector = ORDER sector_metrics BY monto_sector_clp DESC;
STORE rank_sector INTO '$OUTPUT_DIR/gasto_por_sector' USING PigStorage('\t');

-- 8. Evolución Mensual del Gasto (Meses 1 a 12)
by_month = GROUP valid_orders BY mes;
month_metrics = FOREACH by_month GENERATE
    group AS mes,
    SUM(valid_orders.monto_clp_limpio) AS monto_mensual_clp,
    COUNT(valid_orders) AS ordenes_mensuales;
rank_month = ORDER month_metrics BY mes ASC;
STORE rank_month INTO '$OUTPUT_DIR/evolucion_mensual' USING PigStorage('\t');
