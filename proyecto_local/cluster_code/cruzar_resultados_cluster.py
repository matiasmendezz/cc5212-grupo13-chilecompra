#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CC5212 - Procesamiento Masivo de Datos (Grupo 13)
Script de Post-Procesamiento para cruzar las salidas descargadas del Cluster (uhadoop):
  - Entrada 1: ranking_por_monto.tsv (descargado de HDFS tras ejecutar Pig)
  - Entrada 2: pagerank_giraph.tsv (descargado de HDFS tras ejecutar Giraph)
  - Entrada 3: nodos.tsv (diccionario maestro de IDs numéricos 1XXXXXX y 2XXXXXX)
Genera:
  - Tabla maestra consolidada (Rank Financiero vs. Rank PageRank)
  - Perfil 1 del Profesor: Alto Monto y Bajo PageRank (Monocultivo Financiero)
  - Perfil 2 del Profesor: Bajo/Moderado Monto y Alto PageRank (Infraestructura Crítica)
"""

import csv
import sys
from pathlib import Path

def cargar_nodos(nodos_path):
    nodos = {}
    with open(nodos_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 5 or not parts[0].isdigit():
                continue
            nid = int(parts[0])
            nodos[nid] = {
                "tipo": parts[1],
                "codigo": parts[2],
                "rut": parts[3],
                "nombre": parts[4],
            }
    return nodos

def cargar_pagerank(pr_path):
    pr = {}
    with open(pr_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            try:
                nid = int(parts[0])
                score = float(parts[1])
                pr[nid] = score
            except ValueError:
                continue
    return pr

def cargar_pig_ranking(pig_path):
    """
    Lee la salida de rankings_chilecompra_colab_g13.pig:
    proveedor_id \t rut_proveedor \t nombre_proveedor \t es_persona_natural \t monto_total_clp \t total_ordenes \t total_organismos_distintos
    O bien la salida de rankings_chilecompra.pig (esquema de 9 columnas).
    """
    fin_data = {}
    with open(pig_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 7:
                cod_prov = parts[0]
                fin_data[cod_prov] = {
                    "rut": parts[1],
                    "nombre": parts[2],
                    "monto_clp": float(parts[4]),
                    "n_ordenes": int(parts[5]),
                    "n_orgs": int(parts[6]),
                }
            elif len(parts) == 6:
                cod_prov = parts[0]
                fin_data[cod_prov] = {
                    "rut": parts[1],
                    "nombre": parts[2],
                    "monto_clp": float(parts[3]),
                    "n_ordenes": int(parts[4]),
                    "n_orgs": int(parts[5]),
                }
    return fin_data

def main():
    if len(sys.argv) < 4:
        print("Uso: python3 cruzar_resultados_cluster.py <nodos.tsv> <ranking_por_monto.tsv> <pagerank_giraph.tsv>")
        sys.exit(1)

    nodos = cargar_nodos(sys.argv[1])
    fin_data = cargar_pig_ranking(sys.argv[2])
    pr_scores = cargar_pagerank(sys.argv[3])

    consolidado = []
    for nid, info in nodos.items():
        if info["tipo"] != "PROVEEDOR":
            continue
        cod = info["codigo"]
        if cod not in fin_data:
            continue
        f_row = fin_data[cod]
        score = pr_scores.get(nid, 0.0)
        consolidado.append({
            "nid": nid,
            "codigo": cod,
            "rut": f_row["rut"],
            "nombre": f_row["nombre"],
            "monto_clp": f_row["monto_clp"],
            "n_ordenes": f_row["n_ordenes"],
            "n_orgs": f_row["n_orgs"],
            "pagerank": score,
        })

    # Ordenar por Monto y asignar rank_monto
    consolidado.sort(key=lambda x: x["monto_clp"], reverse=True)
    for idx, row in enumerate(consolidado, 1):
        row["rank_monto"] = idx

    # Ordenar por PageRank y asignar rank_pr
    consolidado.sort(key=lambda x: x["pagerank"], reverse=True)
    for idx, row in enumerate(consolidado, 1):
        row["rank_pr"] = idx

    # Perfil 1: Top 50 en Monto pero Rank PageRank > 500
    perfil_1 = [r for r in consolidado if r["rank_monto"] <= 50 and r["rank_pr"] > 500]
    perfil_1.sort(key=lambda x: x["rank_monto"])

    # Perfil 2: Top 30 en PageRank pero Rank Monto > 150
    perfil_2 = [r for r in consolidado if r["rank_pr"] <= 30 and r["rank_monto"] > 150]
    perfil_2.sort(key=lambda x: x["rank_pr"])

    print("\n=== PERFIL 1 (ALTO MONTO / BAJO PAGERANK - MONOCULTIVO FINANCIERO) ===")
    for r in perfil_1[:10]:
        print(f"RankMonto #{r['rank_monto']:<4} | RankPR #{r['rank_pr']:<6} | Orgs: {r['n_orgs']:<4} | ${r['monto_clp']/1e6:,.1f}M | {r['nombre']}")

    print("\n=== PERFIL 2 (BAJO MONTO / ALTO PAGERANK - INFRAESTRUCTURA CRÍTICA) ===")
    for r in perfil_2[:10]:
        print(f"RankPR #{r['rank_pr']:<4} | RankMonto #{r['rank_monto']:<6} | Orgs: {r['n_orgs']:<4} | ${r['monto_clp']/1e6:,.1f}M | {r['nombre']}")

if __name__ == "__main__":
    main()
