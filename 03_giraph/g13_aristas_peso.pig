-- Arma el grafo bidireccional con peso ln(1 + monto) para el PageRank ponderado
ar = LOAD '/uhadoop2026/projects/grupo13/aristas_ponderadas.tsv' USING PigStorage('\t')
     AS (origen:chararray, destino:chararray, n_ordenes:long, monto:double);

-- Se calcula el peso; un monto vacío cuenta como 0
ida = FOREACH ar GENERATE origen, destino, LOG(1.0 + (monto IS NULL ? 0.0 : monto)) AS peso;

-- Cada arista también en sentido contrario
vuelta = FOREACH ar GENERATE destino AS origen, origen AS destino, LOG(1.0 + (monto IS NULL ? 0.0 : monto)) AS peso;

todas = UNION ida, vuelta;
STORE todas INTO '/uhadoop2026/projects/grupo13/aristas_bidir_log' USING PigStorage('\t');
