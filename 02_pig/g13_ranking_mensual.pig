-- Top 10 de proveedores por monto limpio en cada mes de 2025
ordenes = LOAD '$ENTRADA' USING PigStorage('\t') AS (
    codigo:chararray, mes:int, fecha_envio:chararray, fecha_creacion:chararray,
    fecha_aceptacion:chararray, estado:chararray, estado_proveedor:chararray,
    tipo:chararray, procedencia:chararray, cod_licitacion:chararray,
    cod_convenio_marco:chararray, moneda:chararray, monto_original:double,
    monto_clp:double, monto_clp_corr:double, monto_corregido:int,
    monto_clp_limpio:double, flag_monto:chararray, n_items:int,
    cod_organismo:chararray, organismo:chararray, sector:chararray,
    region_comprador:chararray, proveedor_id:chararray, rut_proveedor:chararray,
    nombre_proveedor:chararray, es_persona_natural:chararray,
    region_proveedor:chararray, actividad_proveedor:chararray, usar:int);

-- Se quita la cabecera y se dejan solo las órdenes válidas
validas = FILTER ordenes BY codigo != 'codigo' AND usar == 1;
base = FOREACH validas GENERATE mes, proveedor_id, nombre_proveedor,
    (monto_clp_limpio IS NULL ? 0.0 : monto_clp_limpio) AS monto;

-- Monto y órdenes de cada proveedor en cada mes
por_mes_prov = GROUP base BY (mes, proveedor_id, nombre_proveedor);
mes_prov = FOREACH por_mes_prov GENERATE FLATTEN(group) AS (mes, proveedor_id, nombre_proveedor),
    SUM(base.monto) AS monto_clp, COUNT(base) AS n_ordenes;

-- Top 10 dentro de cada mes
por_mes = GROUP mes_prov BY mes;
top_mes = FOREACH por_mes {
    ordenado = ORDER mes_prov BY monto_clp DESC;
    top10 = LIMIT ordenado 10;
    GENERATE FLATTEN(top10);
};

resultado = ORDER top_mes BY mes ASC, monto_clp DESC;
STORE resultado INTO '$SALIDA/ranking_mensual' USING PigStorage('\t');
