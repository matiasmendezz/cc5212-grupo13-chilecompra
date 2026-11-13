#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_rankings_y_pagerank.py - CC5212 Procesamiento Masivo de Datos
Etapa 3: Rankings Financieros/Volumen (Emulación Pig) + PageRank en 4 Modalidades (Emulación Giraph)

Objetivos:
1. Emulación Pig:
   - Agregación por proveedor: monto_total_clp, n_ordenes, n_organismos_distintos, ticket_promedio, organismo_principal (% de concentración).
   - Rankings Top 25: por monto, por órdenes, por organismos distintos.
   - Distribución por sector estatal y evolución mensual.
2. Emulación Giraph (PageRank exacto con 30 supersteps, d = 0.85):
   - Variante A: Baseline G13 (Dirigido Puro O -> P sin pesos).
   - Variante B: Bipartito Bidireccional Sin Pesos (O <-> P).
   - Variante C: PageRank Ponderado por Frecuencia (O <-> P, w = n_ordenes).
   - Variante D: PageRank Ponderado Log-Financiero (O <-> P, w = ln(1 + M)).
3. Extracción de los 2 Perfiles del Profesor:
   - Perfil 1: Alto Monto y Bajo PageRank (Contratos únicos / concentración extrema).
   - Perfil 2: Bajo/Moderado Monto y Alto PageRank (Proveedores capilares / multipresencia institucional).
4. Guardar resultados en resultados_etapa3.json.
"""

import os
import sys
import csv
import bz2
import math
import json
import time
import numpy as np
from collections import defaultdict

# Aumentar límite de tamaño de campo para csv
max_int = sys.maxsize
while True:
    try:
        csv.field_size_limit(max_int)
        break
    except OverflowError:
        max_int = int(max_int / 10)

DATA_DIR = "/home/matias/Desktop/cc5212/proyecto_local/data"
OUTPUT_JSON = "/home/matias/Desktop/cc5212/proyecto_local/resultados_etapa3.json"

DAMPING_FACTOR = 0.85
MAX_SUPERSTEPS = 30

def load_nodes_and_edges(data_dir: str):
    """Carga los nodos y aristas para construir los grafos."""
    nodos_path = os.path.join(data_dir, "nodos.tsv")
    aristas_path = os.path.join(data_dir, "aristas.tsv")
    
    # 1. Nodos
    # node_id_int -> {tipo_nodo, codigo_original, rut, nombre, sector}
    node_info = {}
    id_to_idx = {}
    idx_to_id = []
    
    org_indices = []
    prov_indices = []
    
    with open(nodos_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        idx = 0
        for r in reader:
            nid = int(r[0])
            tipo = r[1]
            cod_orig = r[2]
            rut = r[3]
            nombre = r[4]
            sector = r[5]
            
            node_info[nid] = {
                "idx": idx,
                "node_id_int": nid,
                "tipo_nodo": tipo,
                "codigo_original": cod_orig,
                "rut": rut,
                "nombre": nombre,
                "sector": sector
            }
            id_to_idx[nid] = idx
            idx_to_id.append(nid)
            
            if tipo == "ORGANISMO":
                org_indices.append(idx)
            else:
                prov_indices.append(idx)
            idx += 1
            
    num_nodes = len(idx_to_id)
    
    # 2. Aristas
    # org_id_int, prov_id_int, n_ordenes, monto_total_clp, log_monto
    edges_u = []
    edges_v = []
    weights_n_orders = []
    weights_monto = []
    weights_log_monto = []
    
    with open(aristas_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        for r in reader:
            u_id = int(r[0])
            v_id = int(r[1])
            n_ord = int(r[2])
            monto = float(r[3])
            log_m = float(r[4])
            
            u_idx = id_to_idx[u_id]
            v_idx = id_to_idx[v_id]
            
            edges_u.append(u_idx)
            edges_v.append(v_idx)
            weights_n_orders.append(n_ord)
            weights_monto.append(monto)
            weights_log_monto.append(max(0.001, log_m))
            
    return {
        "num_nodes": num_nodes,
        "node_info": node_info,
        "id_to_idx": id_to_idx,
        "idx_to_id": idx_to_id,
        "org_indices": np.array(org_indices, dtype=np.int32),
        "prov_indices": np.array(prov_indices, dtype=np.int32),
        "u": np.array(edges_u, dtype=np.int32),
        "v": np.array(edges_v, dtype=np.int32),
        "w_orders": np.array(weights_n_orders, dtype=np.float64),
        "w_monto": np.array(weights_monto, dtype=np.float64),
        "w_log": np.array(weights_log_monto, dtype=np.float64)
    }

def run_pagerank_directed(N: int, src: np.ndarray, dst: np.ndarray, weights: np.ndarray = None, 
                          d: float = 0.85, max_iter: int = 30) -> np.ndarray:
    """
    PageRank dirigido (u -> v) emulando exactamente Apache Giraph Pregel:
    r_{s+1}(i) = (1 - d) / N + d * sum_{j in In(i)} r_s(j) * (w_{ji} / sum_k w_{jk})
    """
    if weights is None:
        weights = np.ones(len(src), dtype=np.float64)
        
    out_degree_weight = np.bincount(src, weights=weights, minlength=N)
    norm_w = np.zeros(len(src), dtype=np.float64)
    valid_mask = out_degree_weight[src] > 0
    norm_w[valid_mask] = weights[valid_mask] / out_degree_weight[src][valid_mask]
    
    r = np.full(N, 1.0 / N, dtype=np.float64)
    base_jump = (1.0 - d) / N
    
    for _ in range(max_iter):
        msg_values = r[src] * norm_w
        received_msgs = np.bincount(dst, weights=msg_values, minlength=N)
        r = base_jump + d * received_msgs
        
    return r

def run_pagerank_bidirectional(N: int, u: np.ndarray, v: np.ndarray, weights: np.ndarray = None,
                               d: float = 0.85, max_iter: int = 30) -> np.ndarray:
    """
    PageRank bipartito bidireccional (u <-> v) emulando Giraph Pregel:
    Flujo recíproco de centralidad entre organismos y proveedores.
    """
    if weights is None:
        weights = np.ones(len(u), dtype=np.float64)
        
    # Ambas direcciones
    src = np.concatenate([u, v])
    dst = np.concatenate([v, u])
    w = np.concatenate([weights, weights])
    
    out_degree_weight = np.bincount(src, weights=w, minlength=N)
    norm_w = np.zeros(len(src), dtype=np.float64)
    valid_mask = out_degree_weight[src] > 0
    norm_w[valid_mask] = w[valid_mask] / out_degree_weight[src][valid_mask]
    
    r = np.full(N, 1.0 / N, dtype=np.float64)
    base_jump = (1.0 - d) / N
    
    for _ in range(max_iter):
        msg_values = r[src] * norm_w
        received_msgs = np.bincount(dst, weights=msg_values, minlength=N)
        r = base_jump + d * received_msgs
        
    return r

def compute_pig_rankings(data_dir: str):
    """
    Calcula los rankings financieros, de volumen y sectoriales equivalentes a Apache Pig
    leyendo directamente el archivo limpio ordenes_limpias.tsv.bz2.
    """
    path_bz2 = os.path.join(data_dir, "ordenes_limpias.tsv.bz2")
    
    # Agregados por proveedor:
    # prov_id -> {nombre, rut, monto_total, n_ordenes, orgs: set(), org_montos: defaultdict(float), org_nombres: dict()}
    prov_data = {}
    
    # Agregados por sector:
    # sector -> {monto_total_clp, n_ordenes, orgs: set()}
    sector_data = defaultdict(lambda: {"monto_total_clp": 0.0, "n_ordenes": 0, "orgs": set()})
    
    # Agregados mensuales:
    # mes -> {monto_total_clp, n_ordenes}
    monthly_data = defaultdict(lambda: {"monto_total_clp": 0.0, "n_ordenes": 0})
    
    total_valid_orders = 0
    total_valid_monto = 0.0
    
    with bz2.open(path_bz2, "rt", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        # 0: id_orden, 1: codigo_oc, 2: mes, 3: estado, 4: codigo_organismo, 5: nombre_organismo
        # 6: sector, 7: id_proveedor, 8: rut_proveedor, 9: nombre_proveedor, 10: moneda_oc
        # 11: monto_bruto_clp, 12: monto_limpio_clp, 13: flag_regla
        
        for r in reader:
            flag = r[13]
            if flag == "CANCELADA":
                continue
                
            total_valid_orders += 1
            mes = int(r[2])
            org_cod = r[4]
            org_nom = r[5]
            sector = r[6]
            prov_id = r[7]
            prov_rut = r[8]
            prov_nom = r[9]
            m_limpio = float(r[12])
            
            total_valid_monto += m_limpio
            
            # Proveedor
            if prov_id not in prov_data:
                prov_data[prov_id] = {
                    "id_proveedor": prov_id,
                    "rut_proveedor": prov_rut,
                    "nombre_proveedor": prov_nom,
                    "monto_total_clp": 0.0,
                    "n_ordenes": 0,
                    "orgs": set(),
                    "org_montos": defaultdict(float),
                    "org_nombres": {}
                }
            
            p = prov_data[prov_id]
            p["monto_total_clp"] += m_limpio
            p["n_ordenes"] += 1
            p["orgs"].add(org_cod)
            p["org_montos"][org_cod] += m_limpio
            p["org_nombres"][org_cod] = org_nom
            
            # Sector
            s = sector_data[sector]
            s["monto_total_clp"] = s.get("monto_total_clp", 0.0) + m_limpio
            s["n_ordenes"] += 1
            s["orgs"].add(org_cod)
            
            # Mes
            m = monthly_data[mes]
            m["monto_total_clp"] += m_limpio
            m["n_ordenes"] += 1
            
    # Post-procesamiento proveedores
    prov_summary = []
    for prov_id, p in prov_data.items():
        m_tot = p["monto_total_clp"]
        n_ord = p["n_ordenes"]
        n_orgs = len(p["orgs"])
        ticket = m_tot / n_ord if n_ord > 0 else 0.0
        
        # Organismo principal
        if p["org_montos"]:
            top_org_cod, top_org_monto = max(p["org_montos"].items(), key=lambda x: x[1])
            top_org_nom = p["org_nombres"].get(top_org_cod, "")
            pct_org = (top_org_monto / m_tot * 100.0) if m_tot > 0 else 0.0
        else:
            top_org_cod, top_org_monto, top_org_nom, pct_org = "", 0.0, "", 0.0
            
        prov_summary.append({
            "id_proveedor": prov_id,
            "rut_proveedor": p["rut_proveedor"],
            "nombre_proveedor": p["nombre_proveedor"],
            "monto_total_clp": m_tot,
            "n_ordenes": n_ord,
            "n_organismos_distintos": n_orgs,
            "ticket_promedio": ticket,
            "organismo_principal": {
                "codigo_organismo": top_org_cod,
                "nombre_organismo": top_org_nom,
                "monto_clp": top_org_monto,
                "pct_ventas_proveedor": round(pct_org, 2)
            }
        })
        
    # Top 25 por Monto
    top25_monto = sorted(prov_summary, key=lambda x: -x["monto_total_clp"])[:25]
    # Top 25 por Órdenes
    top25_ordenes = sorted(prov_summary, key=lambda x: -x["n_ordenes"])[:25]
    # Top 25 por Organismos Distintos
    top25_organismos = sorted(prov_summary, key=lambda x: (-x["n_organismos_distintos"], -x["monto_total_clp"]))[:25]
    
    # Resumen sectorial
    sectores_res = []
    for sec, s in sector_data.items():
        m_sec = s["monto_total_clp"]
        pct = (m_sec / total_valid_monto * 100.0) if total_valid_monto > 0 else 0.0
        sectores_res.append({
            "sector": sec,
            "monto_total_clp": m_sec,
            "pct_gasto_total": round(pct, 2),
            "n_ordenes": s["n_ordenes"],
            "n_organismos": len(s["orgs"])
        })
    sectores_res.sort(key=lambda x: -x["monto_total_clp"])
    
    # Resumen mensual
    meses_res = []
    for m in range(1, 13):
        m_info = monthly_data[m]
        m_tot = m_info["monto_total_clp"]
        n_ord = m_info["n_ordenes"]
        ticket = m_tot / n_ord if n_ord > 0 else 0.0
        meses_res.append({
            "mes": m,
            "monto_total_clp": m_tot,
            "n_ordenes": n_ord,
            "ticket_promedio": ticket
        })
        
    return {
        "total_valid_orders": total_valid_orders,
        "total_valid_monto_clp": total_valid_monto,
        "prov_summary_dict": {p["id_proveedor"]: p for p in prov_summary},
        "top25_monto": top25_monto,
        "top25_ordenes": top25_ordenes,
        "top25_organismos": top25_organismos,
        "sectores": sectores_res,
        "meses": meses_res
    }

def main():
    t_start = time.time()
    print("=" * 80)
    print("CC5212 - ETAPA 3: RANKINGS FINANCIEROS Y PAGERANK EN 4 MODALIDADES")
    print(f"Cargando datos desde: {DATA_DIR}")
    print("=" * 80)
    
    # 1. Emulación Pig
    print("\n[1/3] Calculando Rankings Financieros y de Volumen (Emulación Pig)...")
    t0 = time.time()
    pig_results = compute_pig_rankings(DATA_DIR)
    print(f"  -> Procesadas {pig_results['total_valid_orders']:,} órdenes válidas en {time.time() - t0:.2f} s")
    print(f"  -> Monto limpio total verificado: ${pig_results['total_valid_monto_clp']/1e12:.4f} billones CLP")
    
    print("\n--- TOP 5 PROVEEDORES POR MONTO TOTAL ---")
    for i, p in enumerate(pig_results["top25_monto"][:5], 1):
        print(f"  {i}. {p['nombre_proveedor'][:35]:35} (RUT: {p['rut_proveedor']:12}): ${p['monto_total_clp']/1e9:,.2f} mil M CLP | {p['n_ordenes']:,} OCs | {p['n_organismos_distintos']} orgs")
        print(f"     Org principal: {p['organismo_principal']['nombre_organismo'][:40]} ({p['organismo_principal']['pct_ventas_proveedor']:.1f}% de sus ventas)")
        
    print("\n--- DISTRIBUCIÓN POR SECTOR ESTATAL ---")
    for s in pig_results["sectores"]:
        print(f"  * {s['sector']:35}: ${s['monto_total_clp']/1e12:.2f} B ({s['pct_gasto_total']:>5.1f}%) | {s['n_ordenes']:>8,} OCs | {s['n_organismos']} orgs")
        
    # 2. Cargar Grafos y Emulación Giraph
    print("\n[2/3] Construyendo grafos y ejecutando PageRank en 4 Variantes (30 supersteps, d=0.85)...")
    graph = load_nodes_and_edges(DATA_DIR)
    N = graph["num_nodes"]
    u = graph["u"]
    v = graph["v"]
    node_info = graph["node_info"]
    prov_indices = graph["prov_indices"]
    org_indices = graph["org_indices"]
    idx_to_id = graph["idx_to_id"]
    
    print(f"  -> Nodos cargados: {N:,} (1.165 organismos, 75.603 proveedores)")
    print(f"  -> Aristas cargadas: {len(u):,}")
    
    # Variante A: Baseline G13 (Dirigido Puro O -> P sin pesos)
    t_a = time.time()
    pr_a = run_pagerank_directed(N, u, v, weights=None, d=DAMPING_FACTOR, max_iter=MAX_SUPERSTEPS)
    dur_a = time.time() - t_a
    # Análisis de los organismos en Variante A
    org_pr_a = pr_a[org_indices]
    unique_org_vals_a = np.unique(np.round(org_pr_a, 12))
    base_val = (1.0 - DAMPING_FACTOR) / N
    print(f"\n  [Variante A: Baseline G13 (Dirigido O -> P sin pesos)] ({dur_a:.3f} s)")
    print(f"    * PageRank organismos: exactamente {len(unique_org_vals_a)} valor distinto ({base_val:.8e} = (1-d)/N).")
    print(f"    * Diagnóstico técnico: En el grafo dirigido O -> P los organismos tienen in-degree = 0,")
    print(f"      por lo que no reciben flujo y quedan fijados en el salto aleatorio (1-d)/N.")
    print(f"      El peso que transfieren a cada proveedor es 1/deg+(u), premiando a organismos que compran a un solo proveedor.")
    
    # Variante B: Bipartito Bidireccional Sin Pesos (O <-> P)
    t_b = time.time()
    pr_b = run_pagerank_bidirectional(N, u, v, weights=None, d=DAMPING_FACTOR, max_iter=MAX_SUPERSTEPS)
    dur_b = time.time() - t_b
    print(f"\n  [Variante B: Bipartito Bidireccional Sin Pesos (O <-> P)] ({dur_b:.3f} s)")
    print(f"    * Flujo recíproco de centralidad: organismos acumulan PageRank dinámico de sus proveedores y viceversa.")
    
    # Variante C: PageRank Ponderado por Frecuencia (O <-> P con w = n_ordenes)
    t_c = time.time()
    pr_c = run_pagerank_bidirectional(N, u, v, weights=graph["w_orders"], d=DAMPING_FACTOR, max_iter=MAX_SUPERSTEPS)
    dur_c = time.time() - t_c
    print(f"\n  [Variante C: PageRank Ponderado por Frecuencia (w = n_ordenes)] ({dur_c:.3f} s)")
    
    # Variante D: PageRank Ponderado Log-Financiero (O <-> P con w = ln(1 + M))
    t_d = time.time()
    pr_d = run_pagerank_bidirectional(N, u, v, weights=graph["w_log"], d=DAMPING_FACTOR, max_iter=MAX_SUPERSTEPS)
    dur_d = time.time() - t_d
    print(f"\n  [Variante D: PageRank Ponderado Log-Financiero (w = ln(1 + M))] ({dur_d:.3f} s)")
    
    # Variante D Dirigida (para comparación adicional)
    pr_d_dir = run_pagerank_directed(N, u, v, weights=graph["w_log"], d=DAMPING_FACTOR, max_iter=MAX_SUPERSTEPS)

    # 3. Mapear PageRank a Proveedores y Contrastar con Rankings Financieros
    print("\n[3/3] Extrayendo Perfiles 1 y 2 del Profesor y calculando contrastes...")
    prov_dict = pig_results["prov_summary_dict"]
    
    # Construir tabla completa para todos los 75.603 proveedores
    providers_analysis = []
    
    # Índices ordenados por monto para ranking de monto
    all_prov_ids_by_monto = sorted(prov_dict.keys(), key=lambda pid: -prov_dict[pid]["monto_total_clp"])
    monto_rank_map = {pid: rank for rank, pid in enumerate(all_prov_ids_by_monto, 1)}
    
    # Ranks por PageRank para cada variante (sobre proveedores)
    def compute_pr_rankings(pr_scores):
        prov_scores = [(idx, pr_scores[idx]) for idx in prov_indices]
        prov_scores.sort(key=lambda x: -x[1])
        return {idx_to_id[idx]: (rank, score) for rank, (idx, score) in enumerate(prov_scores, 1)}
        
    rank_map_a = compute_pr_rankings(pr_a)
    rank_map_b = compute_pr_rankings(pr_b)
    rank_map_c = compute_pr_rankings(pr_c)
    rank_map_d = compute_pr_rankings(pr_d)
    
    total_provs = len(prov_indices)
    
    for idx in prov_indices:
        nid = idx_to_id[idx]
        info = node_info[nid]
        pid = info["codigo_original"]
        p_pig = prov_dict.get(pid)
        
        if not p_pig:
            continue
            
        rank_m = monto_rank_map[pid]
        pct_m = (total_provs - rank_m) / total_provs * 100.0
        
        rank_pr_a, score_pr_a = rank_map_a[nid]
        rank_pr_b, score_pr_b = rank_map_b[nid]
        rank_pr_c, score_pr_c = rank_map_c[nid]
        rank_pr_d, score_pr_d = rank_map_d[nid]
        
        pct_pr_b = (total_provs - rank_pr_b) / total_provs * 100.0
        pct_pr_d = (total_provs - rank_pr_d) / total_provs * 100.0
        
        providers_analysis.append({
            "id_proveedor": pid,
            "rut_proveedor": p_pig["rut_proveedor"],
            "nombre_proveedor": p_pig["nombre_proveedor"],
            "monto_total_clp": p_pig["monto_total_clp"],
            "n_ordenes": p_pig["n_ordenes"],
            "n_organismos_distintos": p_pig["n_organismos_distintos"],
            "ticket_promedio": p_pig["ticket_promedio"],
            "organismo_principal": p_pig["organismo_principal"],
            "rank_monto": rank_m,
            "percentil_monto": round(pct_m, 2),
            "pagerank_variante_a": score_pr_a,
            "rank_pr_a": rank_pr_a,
            "pagerank_variante_b": score_pr_b,
            "rank_pr_b": rank_pr_b,
            "percentil_pr_b": round(pct_pr_b, 2),
            "pagerank_variante_c": score_pr_c,
            "rank_pr_c": rank_pr_c,
            "pagerank_variante_d": score_pr_d,
            "rank_pr_d": rank_pr_d,
            "percentil_pr_d": round(pct_pr_d, 2),
            # Disparidad de rango: rank_PR - rank_monto (positivo alto = mucho monto pero bajo PR)
            "disparidad_perfil1": rank_pr_d - rank_m,
            # Disparidad inversa: rank_monto - rank_PR (positivo alto = bajo monto pero altísimo PR)
            "disparidad_perfil2": rank_m - rank_pr_d
        })
        
    # --- PERFIL 1: ALTO MONTO Y BAJO PAGERANK ---
    # Proveedores en el Top 250 de facturación (miles de millones de CLP), pero con muy baja conectividad (1 a 3 organismos)
    # y ranking de PageRank muy bajo en comparación a su volumen financiero.
    candidatos_perfil1 = [
        p for p in providers_analysis 
        if p["rank_monto"] <= 250 and p["n_organismos_distintos"] <= 3
    ]
    # Ordenar por mayor disparidad y monto
    candidatos_perfil1.sort(key=lambda x: -x["disparidad_perfil1"])
    top15_perfil1 = candidatos_perfil1[:15]
    
    # --- PERFIL 2: BAJO/MODERADO MONTO Y ALTO PAGERANK ---
    # Proveedores en el Top 150 de PageRank (altísima centralidad y capilaridad institucional),
    # pero cuyo ranking por monto es moderado o bajo (rank_monto > 500) y le venden a decenas/cientos de organismos.
    candidatos_perfil2 = [
        p for p in providers_analysis 
        if p["rank_pr_d"] <= 150 and p["rank_monto"] > 500 and p["n_organismos_distintos"] >= 25
    ]
    candidatos_perfil2.sort(key=lambda x: -x["disparidad_perfil2"])
    top15_perfil2 = candidatos_perfil2[:15]
    
    print("\n" + "=" * 80)
    print("TOP 10 PERFIL 1: ALTO MONTO Y BAJO PAGERANK (Concentración Extrema / Contratos Únicos)")
    print("=" * 80)
    for i, p in enumerate(top15_perfil1[:10], 1):
        print(f"  {i}. {p['nombre_proveedor'][:35]:35} (RUT: {p['rut_proveedor']:12})")
        print(f"     Monto: ${p['monto_total_clp']/1e9:,.2f} mil M CLP (Rank Monto: #{p['rank_monto']} | Top {100-p['percentil_monto']:.2f}%)")
        print(f"     PageRank D: Rank #{p['rank_pr_d']} | Orgs distintos: {p['n_organismos_distintos']} | OCs: {p['n_ordenes']}")
        print(f"     Org Principal: {p['organismo_principal']['nombre_organismo'][:40]} ({p['organismo_principal']['pct_ventas_proveedor']:.1f}% de sus ventas)")
        print(f"     Disparidad de rango (PR - Monto): +{p['disparidad_perfil1']:,} puestos de rezago en red")
        print()
        
    print("=" * 80)
    print("TOP 10 PERFIL 2: BAJO/MODERADO MONTO Y ALTO PAGERANK (Proveedores Capilares Multiorganismo)")
    print("=" * 80)
    for i, p in enumerate(top15_perfil2[:10], 1):
        print(f"  {i}. {p['nombre_proveedor'][:35]:35} (RUT: {p['rut_proveedor']:12})")
        print(f"     PageRank D: Rank #{p['rank_pr_d']} (Top {100-p['percentil_pr_d']:.2f}%) | Orgs distintos: {p['n_organismos_distintos']} | OCs: {p['n_ordenes']:,}")
        print(f"     Monto: ${p['monto_total_clp']/1e6:,.1f} M CLP (Rank Monto: #{p['rank_monto']:,} | Ticket prom: ${p['ticket_promedio']:,.0f})")
        print(f"     Org Principal: {p['organismo_principal']['nombre_organismo'][:40]} (Sólo {p['organismo_principal']['pct_ventas_proveedor']:.1f}% de sus ventas)")
        print(f"     Ventaja de red (Monto - PR): +{p['disparidad_perfil2']:,} puestos sobre su volumen monetario")
        print()
        
    # Comparativa Top 10 en Variante A vs Variante B vs Variante D
    top10_pr_a = sorted(providers_analysis, key=lambda x: x["rank_pr_a"])[:10]
    top10_pr_b = sorted(providers_analysis, key=lambda x: x["rank_pr_b"])[:10]
    top10_pr_d = sorted(providers_analysis, key=lambda x: x["rank_pr_d"])[:10]
    
    # Consolidar JSON de resultados
    resultados_json = {
        "metadata": {
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tiempo_segundos": round(time.time() - t_start, 2),
            "total_ordenes_validas": pig_results["total_valid_orders"],
            "total_monto_limpio_clp": pig_results["total_valid_monto_clp"],
            "total_proveedores": total_provs,
            "total_organismos": len(org_indices),
            "total_aristas": len(u),
            "damping_factor": DAMPING_FACTOR,
            "max_supersteps": MAX_SUPERSTEPS
        },
        "emulacion_pig": {
            "top25_monto": pig_results["top25_monto"],
            "top25_ordenes": pig_results["top25_ordenes"],
            "top25_organismos_distintos": pig_results["top25_organismos"],
            "distribucion_sectores": pig_results["sectores"],
            "evolucion_mensual": pig_results["meses"]
        },
        "emulacion_giraph_pagerank": {
            "variante_a_baseline_g13": {
                "descripcion": "Dirigido Puro Organismo -> Proveedor sin pesos (Baseline propuesto por G13).",
                "tiempo_segundos": round(dur_a, 4),
                "num_valores_distintos_organismos": len(unique_org_vals_a),
                "valor_constante_organismos": float(base_val),
                "top10_proveedores": [
                    {"nombre": p["nombre_proveedor"], "rut": p["rut_proveedor"], "pagerank": p["pagerank_variante_a"], "orgs_distintos": p["n_organismos_distintos"], "rank_monto": p["rank_monto"]}
                    for p in top10_pr_a
                ]
            },
            "variante_b_bipartito_sin_pesos": {
                "descripcion": "Bipartito Bidireccional Organismo <-> Proveedor sin pesos.",
                "tiempo_segundos": round(dur_b, 4),
                "top10_proveedores": [
                    {"nombre": p["nombre_proveedor"], "rut": p["rut_proveedor"], "pagerank": p["pagerank_variante_b"], "orgs_distintos": p["n_organismos_distintos"], "rank_monto": p["rank_monto"]}
                    for p in top10_pr_b
                ]
            },
            "variante_c_ponderado_frecuencia": {
                "descripcion": "Bipartito Bidireccional ponderado por n_ordenes (w = n_ordenes).",
                "tiempo_segundos": round(dur_c, 4)
            },
            "variante_d_ponderado_log_financiero": {
                "descripcion": "Bipartito Bidireccional ponderado por logaritmo del monto (w = ln(1 + Monto)).",
                "tiempo_segundos": round(dur_d, 4),
                "top10_proveedores": [
                    {"nombre": p["nombre_proveedor"], "rut": p["rut_proveedor"], "pagerank": p["pagerank_variante_d"], "orgs_distintos": p["n_organismos_distintos"], "rank_monto": p["rank_monto"]}
                    for p in top10_pr_d
                ]
            }
        },
        "perfiles_del_profesor": {
            "perfil_1_alto_monto_bajo_pagerank": {
                "definicion": "Proveedores en el Top de facturación estatal (Top 250), pero con bajo PageRank y abasteciendo a solo 1-3 organismos.",
                "total_candidatos": len(candidatos_perfil1),
                "top15": top15_perfil1
            },
            "perfil_2_bajo_monto_alto_pagerank": {
                "definicion": "Proveedores con altísimo PageRank (Top 150), abasteciendo a decenas/cientos de organismos, pero con facturación total moderada/baja.",
                "total_candidatos": len(candidatos_perfil2),
                "top15": top15_perfil2
            }
        }
    }
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados_json, f, indent=2, ensure_ascii=False)
        
    print(f"\n[OK] Resultados guardados exitosamente en: {OUTPUT_JSON}")
    print(f"Tiempo total de cómputo: {time.time() - t_start:.2f} segundos")
    print("=" * 80)

if __name__ == "__main__":
    main()
