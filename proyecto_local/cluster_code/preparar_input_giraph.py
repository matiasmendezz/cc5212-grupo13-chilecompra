#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CC5212 - Procesamiento Masivo de Datos (Grupo 13)
Script para transformar aristas.tsv (tanto del Colab del compañero sin cabecera como del
pipeline local con cabecera) en los formatos exactos de entrada de Apache Giraph
en el cluster uhadoop (Lab 8):
  1. Formato JSON de lista de adyacencia (JsonLongDoubleFloatDoubleVertexInputFormat):
     [id_vertice, valor_inicial, [[id_vecino_1, peso_1], [id_vecino_2, peso_2], ...]]
  2. Formato TSV de aristas sin cabecera (para EdgeInputFormat):
     origen \t destino \t peso
"""

import json
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARISTAS_IN = BASE_DIR / "data" / "aristas.tsv"
OUT_DIR = Path(__file__).resolve().parent

def main():
    adj_dirigido = defaultdict(list)      # Variante A: O -> P
    adj_bidir_log = defaultdict(list)     # Variantes B y D: O <-> P con peso log_monto
    all_nodes = set()

    aristas_tsv_bidir = OUT_DIR / "aristas_giraph_bidir_log.tsv"
    json_dirigido_path = OUT_DIR / "giraph_json_varianteA_dirigido.txt"
    json_bidir_path = OUT_DIR / "giraph_json_varianteBD_bidireccional.txt"

    with open(ARISTAS_IN, "r", encoding="utf-8") as fin, \
         open(aristas_tsv_bidir, "w", encoding="utf-8") as fout_tsv:
        for line in fin:
            parts = line.strip().split("\t")
            if len(parts) < 5 or not parts[0].isdigit():
                continue
            u = int(parts[0])
            v = int(parts[1])
            w_log = round(float(parts[4]), 6)

            all_nodes.add(u)
            all_nodes.add(v)

            # Grafo dirigido original (O -> P)
            adj_dirigido[u].append([v, w_log])

            # Grafo bidireccional (O <-> P) para Variantes B (sin peso) y D (con peso log_monto)
            adj_bidir_log[u].append([v, w_log])
            adj_bidir_log[v].append([u, w_log])

            # TSV sin cabecera para EdgeInputFormat (ida y vuelta)
            fout_tsv.write(f"{u}\t{v}\t{w_log}\n")
            fout_tsv.write(f"{v}\t{u}\t{w_log}\n")

    n_nodes = len(all_nodes)
    init_val = round(1.0 / n_nodes, 10)

    # Exportar formato JSON exacto de Lab 8: [vertex_id, vertex_val, [[dest_id, edge_val], ...]]
    with open(json_dirigido_path, "w", encoding="utf-8") as f_a, \
         open(json_bidir_path, "w", encoding="utf-8") as f_bd:
        for node in sorted(all_nodes):
            record_a = [node, init_val, adj_dirigido.get(node, [])]
            record_bd = [node, init_val, adj_bidir_log.get(node, [])]
            f_a.write(json.dumps(record_a) + "\n")
            f_bd.write(json.dumps(record_bd) + "\n")

    print(f"[OK] Nodos totales: {n_nodes:,}")
    print(f"[OK] Generado: {aristas_tsv_bidir}")
    print(f"[OK] Generado: {json_dirigido_path}")
    print(f"[OK] Generado: {json_bidir_path}")

if __name__ == "__main__":
    main()
