-- rankings_chilecompra.pig - CC5212 Procesamiento Masivo de Datos
-- Script Apache Pig para análisis de concentración, rankings y evolución temporal
-- de compras públicas sobre ordenes_limpias.tsv.bz2

-- 1. Cargar datos limpios
raw_orders = LOAD 'hdfs://cm:9000/uhadoop2026/eones/ordenes_limpias.tsv.bz2' USING PigStorage('\t') AS (
    id_orden:chararray,
    codigo_oc:chararray,
    mes:int,
    estado:chararray,
    codigo_organismo:chararray,
    nombre_organismo:chararray,
    sector:chararray,
    id_proveedor:chararray,
    rut_proveedor:chararray,
    nombre_proveedor:chararray,
    moneda_oc:chararray,
    monto_bruto_clp:double,
    monto_limpio_clp:double,
    flag_regla:chararray
);

-- 2. Filtrar solo ordenes válidas (excluir canceladas)
valid_orders = FILTER raw_orders BY flag_regla != 'CANCELADA';

-- 3. Agrupación por proveedor para Rankings Financieros y de Volumen
orders_by_prov = GROUP valid_orders BY (id_proveedor, rut_proveedor, nombre_proveedor);

prov_rankings = FOREACH orders_by_prov {
    distinct_orgs = DISTINCT valid_orders.codigo_organismo;
    GENERATE
        group.id_proveedor AS id_proveedor,
        group.rut_proveedor AS rut_proveedor,
        group.nombre_proveedor AS nombre_proveedor,
        SUM(valid_orders.monto_limpio_clp) AS monto_total_clp,
        COUNT(valid_orders) AS n_ordenes,
        COUNT(distinct_orgs) AS n_organismos_distintos,
        (SUM(valid_orders.monto_limpio_clp) / (double)COUNT(valid_orders)) AS ticket_promedio;
};

-- 4. Top Proveedores por Monto
ordered_by_monto = ORDER prov_rankings BY monto_total_clp DESC;
top_monto = LIMIT ordered_by_monto 100;
STORE top_monto INTO 'hdfs://cm:9000/uhadoop2026/eones/rankings/top_monto' USING PigStorage('\t');

-- 5. Top Proveedores por Órdenes
ordered_by_ordenes = ORDER prov_rankings BY n_ordenes DESC;
top_ordenes = LIMIT ordered_by_ordenes 100;
STORE top_ordenes INTO 'hdfs://cm:9000/uhadoop2026/eones/rankings/top_ordenes' USING PigStorage('\t');

-- 6. Top Proveedores por Organismos Distintos
ordered_by_orgs = ORDER prov_rankings BY n_organismos_distintos DESC, monto_total_clp DESC;
top_orgs = LIMIT ordered_by_orgs 100;
STORE top_orgs INTO 'hdfs://cm:9000/uhadoop2026/eones/rankings/top_organismos' USING PigStorage('\t');

-- 7. Distribución por Sector Estatal
orders_by_sector = GROUP valid_orders BY sector;
sector_summary = FOREACH orders_by_sector {
    distinct_orgs_sector = DISTINCT valid_orders.codigo_organismo;
    GENERATE
        group AS sector,
        SUM(valid_orders.monto_limpio_clp) AS monto_total_sector,
        COUNT(valid_orders) AS n_ordenes_sector,
        COUNT(distinct_orgs_sector) AS n_organismos_sector;
};
ordered_sector = ORDER sector_summary BY monto_total_sector DESC;
STORE ordered_sector INTO 'hdfs://cm:9000/uhadoop2026/eones/rankings/sectores' USING PigStorage('\t');

-- 8. Evolución Mensual (1..12)
orders_by_month = GROUP valid_orders BY mes;
monthly_summary = FOREACH orders_by_month GENERATE
    group AS mes,
    SUM(valid_orders.monto_limpio_clp) AS monto_total_mes,
    COUNT(valid_orders) AS n_ordenes_mes,
    (SUM(valid_orders.monto_limpio_clp) / (double)COUNT(valid_orders)) AS ticket_promedio_mes;
ordered_month = ORDER monthly_summary BY mes ASC;
STORE ordered_month INTO 'hdfs://cm:9000/uhadoop2026/eones/rankings/evolucion_mensual' USING PigStorage('\t');
