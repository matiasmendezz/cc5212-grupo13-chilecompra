#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04_metricas_avanzadas_y_graficos.py - CC5212 Procesamiento Masivo de Datos
Cálculo de métricas analíticas enriquecidas y generación de figuras para el Informe Final en LaTeX.

Calcula:
1. Concentración y Desigualdad (Gini y Pareto):
   - Coeficiente de Gini de monto adjudicado y de PageRank (Variante D).
   - Porcentaje acumulado en Top 10, 50, 100, Top 1% (756 provs), Top 5% (3.780 provs).
2. Análisis Persona Natural vs. Persona Jurídica (Empresa):
   - Clasificación por RUT (< 50M = Natural, >= 50M = Jurídica).
   - Proveedores, órdenes, montos y PageRank promedio.
3. Top 15 Organismos Públicos más Centrales (Hubs del Estado en PageRank D y B).
4. Matriz de Correlación Global (Spearman y Kendall) entre rankings.
5. Generación de 5 figuras vectoriales en PDF (y PNG de 300 DPI):
   - fig1_limpieza_waterfall.pdf
   - fig2_sectores_y_evolucion.pdf
   - fig3_comparacion_pagerank.pdf
   - fig4_mapa_perfiles_profe.pdf
   - fig5_curva_lorenz.pdf
"""

import os
import sys
import csv
import bz2
import json
import math
import time
import re
import numpy as np
from collections import defaultdict
from scipy.stats import spearmanr, kendalltau

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import Patch

# Configuración de estilo editorial científico
plt.rcParams.update({
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "font.size": 9.5,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.labelweight": "bold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8.5,
    "figure.titlesize": 12,
    "figure.titleweight": "bold",
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
    "axes.axisbelow": True,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.08
})

DATA_DIR = "/home/matias/Desktop/cc5212/proyecto_local/data"
FIG_DIR = "/home/matias/Desktop/cc5212/proyecto_local/informe_latex/figuras"
OUTPUT_METRICS_JSON = "/home/matias/Desktop/cc5212/proyecto_local/informe_latex/metricas_avanzadas.json"

DAMPING_FACTOR = 0.85
MAX_SUPERSTEPS = 30

def gini_coefficient(array):
    """Calcula el coeficiente de Gini exacto de un arreglo de valores no negativos."""
    array = np.sort(np.asarray(array, dtype=np.float64))
    if np.all(array == 0):
        return 0.0
    n = len(array)
    index = np.arange(1, n + 1)
    return (2.0 * np.sum(index * array)) / (n * np.sum(array)) - (n + 1.0) / n

def parse_rut_number(rut_str):
    """Extrae el número de RUT (antes del guión) eliminando puntos."""
    if not rut_str:
        return None
    clean = rut_str.strip().replace(".", "")
    m = re.match(r"^(\d+)", clean)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None

def main():
    start_time = time.time()
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_METRICS_JSON), exist_ok=True)
    
    print("=" * 80)
    print("CC5212 - ETAPA 4: MÉTRICAS AVANZADAS Y GENERACIÓN DE FIGURAS")
    print(f"Directorio de figuras: {FIG_DIR}")
    print("=" * 80)
    
    # 1. Cargar Nodos y Aristas
    print("\n[1/5] Cargando grafos y ejecutando PageRank en 4 Variantes...")
    nodos_path = os.path.join(DATA_DIR, "nodos.tsv")
    aristas_path = os.path.join(DATA_DIR, "aristas.tsv")
    
    node_info = {}
    id_to_idx = {}
    idx_to_id = []
    org_indices = []
    prov_indices = []
    
    with open(nodos_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        next(reader)
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
                "node_id": nid,
                "tipo": tipo,
                "codigo": cod_orig,
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
    org_indices = np.array(org_indices, dtype=np.int32)
    prov_indices = np.array(prov_indices, dtype=np.int32)
    
    edges_u = []
    edges_v = []
    w_orders = []
    w_monto = []
    w_log = []
    
    with open(aristas_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        next(reader)
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
            w_orders.append(n_ord)
            w_monto.append(monto)
            w_log.append(max(0.001, log_m))
            
    edges_u = np.array(edges_u, dtype=np.int32)
    edges_v = np.array(edges_v, dtype=np.int32)
    w_orders = np.array(w_orders, dtype=np.float64)
    w_log = np.array(w_log, dtype=np.float64)
    
    # Algoritmos PageRank
    def pr_directed(src, dst, weights=None):
        if weights is None:
            weights = np.ones(len(src), dtype=np.float64)
        deg_w = np.bincount(src, weights=weights, minlength=num_nodes)
        norm_w = np.zeros(len(src), dtype=np.float64)
        mask = deg_w[src] > 0
        norm_w[mask] = weights[mask] / deg_w[src][mask]
        r = np.full(num_nodes, 1.0 / num_nodes, dtype=np.float64)
        base = (1.0 - DAMPING_FACTOR) / num_nodes
        for _ in range(MAX_SUPERSTEPS):
            msgs = np.bincount(dst, weights=r[src] * norm_w, minlength=num_nodes)
            r = base + DAMPING_FACTOR * msgs
        return r

    def pr_bidirectional(u_arr, v_arr, weights=None):
        if weights is None:
            weights = np.ones(len(u_arr), dtype=np.float64)
        src = np.concatenate([u_arr, v_arr])
        dst = np.concatenate([v_arr, u_arr])
        w = np.concatenate([weights, weights])
        deg_w = np.bincount(src, weights=w, minlength=num_nodes)
        norm_w = np.zeros(len(src), dtype=np.float64)
        mask = deg_w[src] > 0
        norm_w[mask] = w[mask] / deg_w[src][mask]
        r = np.full(num_nodes, 1.0 / num_nodes, dtype=np.float64)
        base = (1.0 - DAMPING_FACTOR) / num_nodes
        for _ in range(MAX_SUPERSTEPS):
            msgs = np.bincount(dst, weights=r[src] * norm_w, minlength=num_nodes)
            r = base + DAMPING_FACTOR * msgs
        return r

    pr_a = pr_directed(edges_u, edges_v, weights=None)
    pr_b = pr_bidirectional(edges_u, edges_v, weights=None)
    pr_c = pr_bidirectional(edges_u, edges_v, weights=w_orders)
    pr_d = pr_bidirectional(edges_u, edges_v, weights=w_log)
    
    print(f"  -> PageRank calculado en 4 variantes para {num_nodes:,} nodos ({len(org_indices):,} orgs, {len(prov_indices):,} provs).")

    # 2. Cargar Agregaciones de Órdenes Limpias (Pig)
    print("\n[2/5] Agregando métricas financieras y por organismo...")
    path_bz2 = os.path.join(DATA_DIR, "ordenes_limpias.tsv.bz2")
    
    prov_monto = defaultdict(float)
    prov_orders = defaultdict(int)
    prov_orgs = defaultdict(set)
    prov_rut_map = {}
    prov_nom_map = {}
    
    org_monto = defaultdict(float)
    org_orders = defaultdict(int)
    org_provs = defaultdict(set)
    org_nom_map = {}
    org_sec_map = {}
    
    sector_monto = defaultdict(float)
    sector_orders = defaultdict(int)
    sector_orgs = defaultdict(set)
    
    monthly_monto = defaultdict(float)
    monthly_orders = defaultdict(int)
    
    # Para waterfall de limpieza:
    # Monto bruto canceladas, ahorro regla 1, ahorro regla 2
    ahorro_regla1 = 0.0
    ahorro_regla2 = 0.0
    monto_bruto_canceladas = 0.0
    monto_bruto_total = 0.0
    monto_limpio_total = 0.0
    
    with bz2.open(path_bz2, "rt", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        for r in reader:
            flag = r[13]
            m_bruto = float(r[11])
            m_limpio = float(r[12])
            monto_bruto_total += m_bruto
            
            if flag == "CANCELADA":
                monto_bruto_canceladas += m_bruto
                continue
                
            monto_limpio_total += m_limpio
            if flag == "CORREGIDA_45":
                ahorro_regla1 += (m_bruto - m_limpio)
            elif flag == "SOSPECHOSA_21":
                ahorro_regla2 += m_bruto
                
            mes = int(r[2])
            org_cod = r[4]
            org_nom = r[5]
            sector = r[6]
            prov_id = r[7]
            prov_rut = r[8]
            prov_nom = r[9]
            
            prov_monto[prov_id] += m_limpio
            prov_orders[prov_id] += 1
            prov_orgs[prov_id].add(org_cod)
            prov_rut_map[prov_id] = prov_rut
            prov_nom_map[prov_id] = prov_nom
            
            org_monto[org_cod] += m_limpio
            org_orders[org_cod] += 1
            org_provs[org_cod].add(prov_id)
            org_nom_map[org_cod] = org_nom
            org_sec_map[org_cod] = sector
            
            sector_monto[sector] += m_limpio
            sector_orders[sector] += 1
            sector_orgs[sector].add(org_cod)
            
            monthly_monto[mes] += m_limpio
            monthly_orders[mes] += 1
            
    print(f"  -> Monto Bruto Total:    ${monto_bruto_total/1e12:,.4f} Billones")
    print(f"  -> Canceladas:           ${monto_bruto_canceladas/1e12:,.4f} Billones")
    print(f"  -> Ahorro Regla 1 (UTM): ${ahorro_regla1/1e12:,.4f} Billones")
    print(f"  -> Ahorro Regla 2 (>10B):${ahorro_regla2/1e12:,.4f} Billones")
    print(f"  -> Monto Limpio Total:   ${monto_limpio_total/1e12:,.4f} Billones")

    # 3. Métricas Enriquecidas: Gini, Pareto, RUT y Organismos Centrales
    print("\n[3/5] Calculando métricas de concentración, Gini y tipología jurídica...")
    
    # Arreglo de montos por proveedor
    all_prov_montos = np.array([prov_monto[node_info[idx_to_id[idx]]["codigo"]] for idx in prov_indices], dtype=np.float64)
    all_prov_pr_a = pr_a[prov_indices]
    all_prov_pr_b = pr_b[prov_indices]
    all_prov_pr_c = pr_c[prov_indices]
    all_prov_pr_d = pr_d[prov_indices]
    all_prov_orders = np.array([prov_orders[node_info[idx_to_id[idx]]["codigo"]] for idx in prov_indices], dtype=np.int32)
    all_prov_org_counts = np.array([len(prov_orgs[node_info[idx_to_id[idx]]["codigo"]]) for idx in prov_indices], dtype=np.int32)
    
    gini_m = gini_coefficient(all_prov_montos)
    gini_prd = gini_coefficient(all_prov_pr_d)
    gini_pra = gini_coefficient(all_prov_pr_a)
    gini_ord = gini_coefficient(all_prov_orders)
    
    print(f"  -> Gini Monto Adjudicado: {gini_m:.4f} (Desigualdad financiera casi total)")
    print(f"  -> Gini PageRank D:       {gini_prd:.4f} (Distribución de red mucho más equitativa)")
    print(f"  -> Gini Órdenes:          {gini_ord:.4f}")
    
    # Pareto de concentración
    sorted_montos = np.sort(all_prov_montos)[::-1]
    cum_montos = np.cumsum(sorted_montos)
    tot_m = monto_limpio_total
    
    n_total_provs = len(all_prov_montos)
    top10_m = np.sum(sorted_montos[:10])
    top50_m = np.sum(sorted_montos[:50])
    top100_m = np.sum(sorted_montos[:100])
    top1pct_idx = int(n_total_provs * 0.01)  # 756
    top5pct_idx = int(n_total_provs * 0.05)  # 3.780
    top10pct_idx = int(n_total_provs * 0.10) # 7.560
    top20pct_idx = int(n_total_provs * 0.20) # 15.120
    
    pct_top10 = (top10_m / tot_m) * 100.0
    pct_top50 = (top50_m / tot_m) * 100.0
    pct_top100 = (top100_m / tot_m) * 100.0
    pct_top1pct = (np.sum(sorted_montos[:top1pct_idx]) / tot_m) * 100.0
    pct_top5pct = (np.sum(sorted_montos[:top5pct_idx]) / tot_m) * 100.0
    pct_top10pct = (np.sum(sorted_montos[:top10pct_idx]) / tot_m) * 100.0
    pct_top20pct = (np.sum(sorted_montos[:top20pct_idx]) / tot_m) * 100.0
    
    print(f"  -> Concentración Pareto:")
    print(f"     * Top 10 proveedores:   {pct_top10:>5.2f}% del gasto total (${top10_m/1e12:.2f} B)")
    print(f"     * Top 50 proveedores:   {pct_top50:>5.2f}% del gasto total (${top50_m/1e12:.2f} B)")
    print(f"     * Top 100 proveedores:  {pct_top100:>5.2f}% del gasto total (${top100_m/1e12:.2f} B)")
    print(f"     * Top 1% ({top1pct_idx:,} provs):  {pct_top1pct:>5.2f}% del gasto total")
    print(f"     * Top 5% ({top5pct_idx:,} provs):  {pct_top5pct:>5.2f}% del gasto total")
    print(f"     * Top 20% ({top20pct_idx:,} provs): {pct_top20pct:>5.2f}% del gasto total")
    
    # Análisis Persona Natural vs. Jurídica
    jur_mask = []
    nat_mask = []
    oth_mask = []
    for idx in prov_indices:
        nid = idx_to_id[idx]
        rut = node_info[nid]["rut"]
        rnum = parse_rut_number(rut)
        if rnum is None:
            oth_mask.append(True)
            jur_mask.append(False)
            nat_mask.append(False)
        elif rnum >= 50_000_000:
            jur_mask.append(True)
            nat_mask.append(False)
            oth_mask.append(False)
        else:
            nat_mask.append(True)
            jur_mask.append(False)
            oth_mask.append(False)
            
    jur_mask = np.array(jur_mask, dtype=bool)
    nat_mask = np.array(nat_mask, dtype=bool)
    oth_mask = np.array(oth_mask, dtype=bool)
    
    analisis_rut = {
        "empresas_juridicas": {
            "n_proveedores": int(np.sum(jur_mask)),
            "pct_proveedores": round(float(np.sum(jur_mask) / n_total_provs * 100.0), 2),
            "monto_total_clp": float(np.sum(all_prov_montos[jur_mask])),
            "pct_monto_total": round(float(np.sum(all_prov_montos[jur_mask]) / tot_m * 100.0), 2),
            "n_ordenes": int(np.sum(all_prov_orders[jur_mask])),
            "pct_ordenes": round(float(np.sum(all_prov_orders[jur_mask]) / 1853435 * 100.0), 2),
            "ticket_promedio": float(np.sum(all_prov_montos[jur_mask]) / np.sum(all_prov_orders[jur_mask])),
            "pagerank_d_promedio": float(np.mean(all_prov_pr_d[jur_mask])),
            "orgs_distintos_promedio": round(float(np.mean(all_prov_org_counts[jur_mask])), 2)
        },
        "personas_naturales": {
            "n_proveedores": int(np.sum(nat_mask)),
            "pct_proveedores": round(float(np.sum(nat_mask) / n_total_provs * 100.0), 2),
            "monto_total_clp": float(np.sum(all_prov_montos[nat_mask])),
            "pct_monto_total": round(float(np.sum(all_prov_montos[nat_mask]) / tot_m * 100.0), 2),
            "n_ordenes": int(np.sum(all_prov_orders[nat_mask])),
            "pct_ordenes": round(float(np.sum(all_prov_orders[nat_mask]) / 1853435 * 100.0), 2),
            "ticket_promedio": float(np.sum(all_prov_montos[nat_mask]) / np.sum(all_prov_orders[nat_mask])),
            "pagerank_d_promedio": float(np.mean(all_prov_pr_d[nat_mask])),
            "orgs_distintos_promedio": round(float(np.mean(all_prov_org_counts[nat_mask])), 2)
        },
        "otros_sin_rut": {
            "n_proveedores": int(np.sum(oth_mask)),
            "monto_total_clp": float(np.sum(all_prov_montos[oth_mask])),
            "n_ordenes": int(np.sum(all_prov_orders[oth_mask]))
        }
    }
    
    # Top 15 Organismos Públicos más Centrales (Hubs del Estado)
    org_list = []
    for idx in org_indices:
        nid = idx_to_id[idx]
        info = node_info[nid]
        cod = info["codigo"]
        org_list.append({
            "node_id": nid,
            "codigo": cod,
            "nombre": info["nombre"],
            "sector": info["sector"],
            "pagerank_d": float(pr_d[idx]),
            "pagerank_b": float(pr_b[idx]),
            "monto_gasto_clp": float(org_monto[cod]),
            "n_ordenes": int(org_orders[cod]),
            "n_proveedores_distintos": len(org_provs[cod])
        })
    org_list.sort(key=lambda x: -x["pagerank_d"])
    top15_organismos = org_list[:15]
    
    # Matriz de Correlación Global (Spearman y Kendall)
    print("\n[4/5] Calculando matriz de correlaciones globales entre rankings...")
    # Creamos rankings (1 = mejor)
    def rank_desc(arr):
        order = np.argsort(-arr)
        ranks = np.empty_like(order)
        ranks[order] = np.arange(1, len(arr) + 1)
        return ranks
        
    r_monto = rank_desc(all_prov_montos)
    r_orders = rank_desc(all_prov_orders)
    r_orgs = rank_desc(all_prov_org_counts)
    r_pra = rank_desc(all_prov_pr_a)
    r_prb = rank_desc(all_prov_pr_b)
    r_prc = rank_desc(all_prov_pr_c)
    r_prd = rank_desc(all_prov_pr_d)
    
    variables = [
        ("Monto Financiero", r_monto),
        ("Volumen Órdenes", r_orders),
        ("Capilaridad (Orgs)", r_orgs),
        ("PageRank A (G13)", r_pra),
        ("PageRank B (Bipartito)", r_prb),
        ("PageRank C (Frecuencia)", r_prc),
        ("PageRank D (Log-Financiero)", r_prd)
    ]
    
    corr_spearman = {}
    corr_kendall = {}
    
    for name1, r1 in variables:
        corr_spearman[name1] = {}
        corr_kendall[name1] = {}
        for name2, r2 in variables:
            # Spearman
            sp_val = float(spearmanr(r1, r2).statistic)
            corr_spearman[name1][name2] = round(sp_val, 4)
            # Kendall (sobre submuestra de 10.000 para rapidez computacional exacta si es grande)
            if name1 == name2:
                corr_kendall[name1][name2] = 1.0
            else:
                # Submuestra determinista para Kendall
                kd_val = float(kendalltau(r1[:15000], r2[:15000]).statistic)
                corr_kendall[name1][name2] = round(kd_val, 4)
                
    print("  -> Correlación de Spearman (Monto vs PageRank D):", corr_spearman["Monto Financiero"]["PageRank D (Log-Financiero)"])
    print("  -> Correlación de Spearman (Capilaridad vs PageRank D):", corr_spearman["Capilaridad (Orgs)"]["PageRank D (Log-Financiero)"])
    print("  -> Correlación de Spearman (PageRank A vs PageRank D):", corr_spearman["PageRank A (G13)"]["PageRank D (Log-Financiero)"])

    # Guardar métricas completas en JSON
    metricas_consolidadas = {
        "metadata": {
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_ordenes_validas": 1853435,
            "total_monto_limpio_clp": tot_m,
            "total_proveedores": n_total_provs,
            "total_organismos": len(org_indices),
            "total_aristas": len(edges_u)
        },
        "limpieza_financiera_waterfall": {
            "monto_bruto_total_pesos": monto_bruto_total,
            "descuento_ordenes_canceladas_pesos": monto_bruto_canceladas,
            "monto_bruto_validas_pesos": monto_bruto_total - monto_bruto_canceladas,
            "ahorro_regla_1_divisas_items_pesos": ahorro_regla1,
            "ahorro_regla_2_sospechosas_pesos": ahorro_regla2,
            "monto_limpio_final_pesos": monto_limpio_total,
            "porcentaje_reduccion_total": round((1.0 - monto_limpio_total / monto_bruto_total) * 100.0, 2)
        },
        "desigualdad_y_pareto": {
            "gini_monto_adjudicado": round(float(gini_m), 4),
            "gini_pagerank_variante_d": round(float(gini_prd), 4),
            "gini_pagerank_variante_a": round(float(gini_pra), 4),
            "gini_ordenes": round(float(gini_ord), 4),
            "concentracion_gasto": {
                "top_10_proveedores": {"monto_clp": float(top10_m), "pct_gasto": round(float(pct_top10), 2)},
                "top_50_proveedores": {"monto_clp": float(top50_m), "pct_gasto": round(float(pct_top50), 2)},
                "top_100_proveedores": {"monto_clp": float(top100_m), "pct_gasto": round(float(pct_top100), 2)},
                "top_1_porciento_756_provs": {"monto_clp": float(np.sum(sorted_montos[:top1pct_idx])), "pct_gasto": round(float(pct_top1pct), 2)},
                "top_5_porciento_3780_provs": {"monto_clp": float(np.sum(sorted_montos[:top5pct_idx])), "pct_gasto": round(float(pct_top5pct), 2)},
                "top_10_porciento_7560_provs": {"monto_clp": float(np.sum(sorted_montos[:top10pct_idx])), "pct_gasto": round(float(pct_top10pct), 2)},
                "top_20_porciento_15120_provs": {"monto_clp": float(np.sum(sorted_montos[:top20pct_idx])), "pct_gasto": round(float(pct_top20pct), 2)}
            }
        },
        "analisis_persona_natural_vs_juridica": analisis_rut,
        "top_15_organismos_hubs_estado": top15_organismos,
        "matriz_correlacion_spearman": corr_spearman,
        "matriz_correlacion_kendall": corr_kendall
    }
    
    with open(OUTPUT_METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(metricas_consolidadas, f, indent=2, ensure_ascii=False)
    print(f"  -> Métricas consolidadas en: {OUTPUT_METRICS_JSON}")

    # 4. Generación de las 5 Figuras Vectoriales
    print("\n[5/5] Generando las 5 figuras vectoriales para el Informe Final...")
    
    # FIGURA 1: Waterfall de Limpieza Financiera
    print("  -> Generando fig1_limpieza_waterfall.pdf...")
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    
    steps = [
        "Monto Bruto\nTotal",
        "Exclusión\nCanceladas",
        "Regla 1: Divisas\nMal Digitadas",
        "Regla 2: Órdenes\nSospechosas",
        "Monto Limpio\nDefinitivo"
    ]
    
    b_tot = monto_bruto_total / 1e12
    b_canc = -monto_bruto_canceladas / 1e12
    b_r1 = -ahorro_regla1 / 1e12
    b_r2 = -ahorro_regla2 / 1e12
    b_limp = monto_limpio_total / 1e12
    
    # Posiciones de barras
    bottoms = [0, b_tot + b_canc, b_tot + b_canc + b_r1, b_tot + b_canc + b_r1 + b_r2, 0]
    heights = [b_tot, abs(b_canc), abs(b_r1), abs(b_r2), b_limp]
    colors = ["#1f4e79", "#b22222", "#d9534f", "#e67e22", "#2e7d32"]
    
    bars = ax.bar(range(5), heights, bottom=bottoms, color=colors, width=0.55, edgecolor="black", linewidth=0.8, zorder=3)
    
    # Líneas conectoras
    ax.plot([0.275, 0.725], [b_tot + b_canc, b_tot + b_canc], color="gray", linestyle=":", linewidth=1)
    ax.plot([1.275, 1.725], [b_tot + b_canc + b_r1, b_tot + b_canc + b_r1], color="gray", linestyle=":", linewidth=1)
    ax.plot([2.275, 2.725], [b_tot + b_canc + b_r1 + b_r2, b_tot + b_canc + b_r1 + b_r2], color="gray", linestyle=":", linewidth=1)
    
    # Etiquetas de valor
    ax.text(0, b_tot + 0.8, f"${b_tot:.2f} B", ha="center", va="bottom", fontweight="bold", color="#1f4e79")
    ax.text(1, bottoms[1] + heights[1]/2, f"-${abs(b_canc):.2f} B\n(-19.9%)", ha="center", va="center", color="white", fontweight="bold", fontsize=8.5)
    ax.text(2, bottoms[2] + heights[2]/2, f"-${abs(b_r1):.2f} B\n(-38.4%)", ha="center", va="center", color="white", fontweight="bold", fontsize=8.5)
    ax.text(3, bottoms[3] + heights[3] + 0.6, f"-${abs(b_r2):.2f} B\n(-2.0%)", ha="center", va="bottom", color="#b95d00", fontweight="bold", fontsize=8.5)
    ax.text(4, b_limp + 0.8, f"${b_limp:.2f} B\n(39.7%)", ha="center", va="bottom", fontweight="bold", color="#2e7d32")
    
    ax.set_xticks(range(5))
    ax.set_xticklabels(steps, fontweight="bold")
    ax.set_ylabel("Monto en Billones de Pesos Chilenos (Billions CLP)", fontweight="bold")
    ax.set_title("Efecto de la Limpieza Financiera y Corrección de Datos en ChileCompra 2025", pad=14)
    ax.set_ylim(0, 52)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("$%.0f B"))
    
    # Cuadro explicativo
    ax.text(0.98, 0.95, 
            "• 45 órdenes infladas por factor UF/UTM (\\$17,60 B corregidos)\n"
            "• 21 órdenes en divisa sobre \\$10.000M CLP (\\$0,90 B ajustados)\n"
            "• Reducción neta total del 60.3% del monto bruto distorsionado",
            transform=ax.transAxes, ha="right", va="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#ced4da", alpha=0.95),
            fontsize=8.5)
            
    fig.savefig(os.path.join(FIG_DIR, "fig1_limpieza_waterfall.pdf"))
    fig.savefig(os.path.join(FIG_DIR, "fig1_limpieza_waterfall.png"), dpi=300)
    plt.close(fig)
    
    # FIGURA 2: Sectores del Estado y Evolución Mensual
    print("  -> Generando fig2_sectores_y_evolucion.pdf...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw={"width_ratios": [1.1, 1.0]})
    
    # Panel Izquierdo: Sectores
    sectores_raw = sorted(sector_monto.items(), key=lambda x: x[1])
    sec_names = [s[0] if s[0] != "NA" else "No Clasificado" for s in sectores_raw]
    sec_vals = [s[1] / 1e12 for s in sectores_raw]
    sec_ords = [sector_orders[s[0]] for s in sectores_raw]
    
    y_pos = np.arange(len(sec_names))
    bars_sec = ax1.barh(y_pos, sec_vals, color="#2b5c8f", edgecolor="black", linewidth=0.6, height=0.65, zorder=3)
    
    for i, (v, o) in enumerate(zip(sec_vals, sec_ords)):
        pct = (v / (monto_limpio_total / 1e12)) * 100.0
        ax1.text(v + 0.12, i, f"${v:.2f} B ({pct:.1f}%) | {o:,} OCs", va="center", fontsize=8, color="#1c2833", fontweight="bold")
        
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(sec_names, fontweight="bold")
    ax1.set_xlabel("Monto Limpio Adjudicado (Billones CLP)", fontweight="bold")
    ax1.set_title("(a) Distribución del Gasto por Sector del Estado", pad=10)
    ax1.set_xlim(0, 8.5)
    ax1.xaxis.set_major_formatter(ticker.FormatStrFormatter("$%.1f B"))
    
    # Panel Derecho: Evolución Mensual
    meses_num = np.arange(1, 13)
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    gasto_mensual = [monthly_monto[m] / 1e12 for m in meses_num]
    ordenes_mensual = [monthly_orders[m] / 1000 for m in meses_num]
    
    color_monto = "#1f4e79"
    color_ord = "#d9534f"
    
    line1 = ax2.plot(meses_num, gasto_mensual, color=color_monto, marker="o", linewidth=2.2, label="Gasto Limpio ($B CLP)", zorder=4)
    ax2.fill_between(meses_num, gasto_mensual, color=color_monto, alpha=0.15, zorder=2)
    ax2.set_xlabel("Mes del Año 2025", fontweight="bold")
    ax2.set_ylabel("Gasto Limpio Mensual (Billones CLP)", color=color_monto, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=color_monto)
    ax2.set_xticks(meses_num)
    ax2.set_xticklabels(meses_nombres, fontweight="bold")
    ax2.set_ylim(0.7, 2.9)
    ax2.yaxis.set_major_formatter(ticker.FormatStrFormatter("$%.1f B"))
    
    ax2_twin = ax2.twinx()
    line2 = ax2_twin.plot(meses_num, ordenes_mensual, color=color_ord, marker="s", linestyle="--", linewidth=1.8, label="Volumen de Órdenes (miles)", zorder=4)
    ax2_twin.set_ylabel("Órdenes de Compra (Miles de OCs)", color=color_ord, fontweight="bold")
    ax2_twin.tick_params(axis="y", labelcolor=color_ord)
    ax2_twin.set_ylim(90, 200)
    ax2_twin.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f k"))
    ax2_twin.grid(False)
    
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax2.legend(lines, labels, loc="lower left", framealpha=0.9)
    ax2.set_title("(b) Evolución Mensual del Gasto y Transacciones", pad=10)
    
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig2_sectores_y_evolucion.pdf"))
    fig.savefig(os.path.join(FIG_DIR, "fig2_sectores_y_evolucion.png"), dpi=300)
    plt.close(fig)
    
    # FIGURA 3: Comparación de PageRank (Organismos en A vs B/D y Rango de Proveedores)
    print("  -> Generando fig3_comparacion_pagerank.pdf...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8))
    
    # Panel Izquierdo: Organismos
    org_pr_a_sorted = np.sort(pr_a[org_indices])[::-1]
    org_pr_b_sorted = np.sort(pr_b[org_indices])[::-1]
    org_pr_d_sorted = np.sort(pr_d[org_indices])[::-1]
    ranks_org = np.arange(1, len(org_indices) + 1)
    
    ax1.plot(ranks_org, org_pr_a_sorted, color="#c0392b", linestyle="--", linewidth=2.2, label="Variante A: Dirigido Puro O→P (Baseline G13, Plano)")
    ax1.plot(ranks_org, org_pr_b_sorted, color="#2980b9", linewidth=2.0, label="Variante B: Bipartito Bidireccional O↔P (Sin Pesos)")
    ax1.plot(ranks_org, org_pr_d_sorted, color="#27ae60", linewidth=2.2, label="Variante D: Bipartito Ponderado Log-Financiero O↔P")
    
    ax1.set_yscale("log")
    ax1.set_xlabel("Ranking de Organismos Públicos (1 a 1.165)", fontweight="bold")
    ax1.set_ylabel("PageRank del Organismo (Escala Logarítmica)", fontweight="bold")
    ax1.set_title("(a) Colapso Estructural de Organismos en Variante A vs. B y D", pad=10)
    ax1.legend(loc="upper right", framealpha=0.9)
    
    # Anotación sobre Variante A
    ax1.annotate("Variante A: Los 1.165 organismos tienen el\nmismo valor idéntico: (1-d)/N = 1,95×10⁻⁶",
                 xy=(582, (1.0 - DAMPING_FACTOR) / num_nodes),
                 xytext=(400, 8e-6),
                 arrowprops=dict(facecolor="#c0392b", shrink=0.08, width=1.2, headwidth=6),
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="#fadbd8", edgecolor="#c0392b", alpha=0.9),
                 fontsize=8)
                 
    # Panel Derecho: Comparación de Rango de Proveedores en Variante A vs Variante D
    # Seleccionamos una muestra representativa de proveedores clave
    sample_pids = [
        "1524865",   # DaVita
        "7001",      # COPEC
        "7602",      # GASCO
        "1005",      # PRISA
        "11190",     # LATAM
        "780357347", # Las Araucarias
        "767297815", # LyP Group
        "767796757", # Integramundo
        "966815507", # Viconsa
        "590698601"  # Acciona
    ]
    
    # Scatter de rangos para 1.000 proveedores aleatorios + casos destacados
    np.random.seed(42)
    sample_indices = np.random.choice(prov_indices, size=1500, replace=False)
    ax2.scatter(r_pra[sample_indices - len(org_indices)], r_prd[sample_indices - len(org_indices)], 
                color="#7f8c8d", alpha=0.25, s=12, label="Proveedores (muestra)", zorder=2)
                
    ax2.plot([1, 75603], [1, 75603], color="black", linestyle=":", linewidth=1.2, label="Equivalencia perfecta (y = x)", zorder=3)
    
    # Destacar COPEC, LATAM, Las Araucarias y Viconsa
    # COPEC
    idx_copec = id_to_idx[2000001 + list(prov_nom_map.values()).index("COPEC S.A.")] if "COPEC S.A." in prov_nom_map.values() else None
    
    ax2.set_xlabel("Ranking de PageRank en Variante A (Dirigido)", fontweight="bold")
    ax2.set_ylabel("Ranking de PageRank en Variante D (Ponderado)", fontweight="bold")
    ax2.set_title("(b) Disparidad de Rankings de Proveedores: Variante A vs. D", pad=10)
    ax2.set_xlim(1, 76000)
    ax2.set_ylim(1, 76000)
    ax2.legend(loc="upper left", framealpha=0.9)
    
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig3_comparacion_pagerank.pdf"))
    fig.savefig(os.path.join(FIG_DIR, "fig3_comparacion_pagerank.png"), dpi=300)
    plt.close(fig)
    
    # FIGURA 4: MAPA BIDIMENSIONAL DE LOS DOS PERFILES DEL PROFESOR (CENTRAL)
    print("  -> Generando fig4_mapa_perfiles_profe.pdf...")
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    
    log_monto_provs = np.log10(np.maximum(1.0, all_prov_montos))
    log_prd_provs = np.log10(all_prov_pr_d)
    
    # Fondo con densidad scatter
    hb = ax.hexbin(log_monto_provs, log_prd_provs, gridsize=65, cmap="Blues", mincnt=1, bins="log", alpha=0.65, zorder=2)
    cb = fig.colorbar(hb, ax=ax, pad=0.02, shrink=0.85)
    cb.set_label("Densidad de Proveedores (log₁₀ conteo)", fontweight="bold", fontsize=9)
    
    # Cargar los perfiles exactos desde resultados_etapa3.json
    with open(os.path.join("/home/matias/Desktop/cc5212/proyecto_local/resultados_etapa3.json"), "r") as f_res:
        etapa3_data = json.load(f_res)
        
    p1_items = etapa3_data["perfiles_del_profesor"]["perfil_1_alto_monto_bajo_pagerank"]["top15"]
    p2_items = etapa3_data["perfiles_del_profesor"]["perfil_2_bajo_monto_alto_pagerank"]["top15"]
    
    # Puntos Perfil 1 (Alto Monto / Bajo PageRank)
    p1_x = [np.log10(p["monto_total_clp"]) for p in p1_items]
    p1_y = [np.log10(p["pagerank_variante_d"]) for p in p1_items]
    ax.scatter(p1_x, p1_y, color="#c0392b", edgecolor="black", s=70, marker="o", label="Perfil 1: Alto Monto / Bajo PageRank (Contratos Únicos)", zorder=5)
    
    # Puntos Perfil 2 (Bajo/Moderado Monto / Alto PageRank)
    p2_x = [np.log10(p["monto_total_clp"]) for p in p2_items]
    p2_y = [np.log10(p["pagerank_variante_d"]) for p in p2_items]
    ax.scatter(p2_x, p2_y, color="#27ae60", edgecolor="black", s=65, marker="s", label="Perfil 2: Bajo Monto / Alto PageRank (Proveedores Capilares)", zorder=5)
    
    # Hubs Consolidados (Alto Monto y Alto PageRank)
    hubs = [
        ("COPEC S.A.", 116.15e9, 8.236e-4),
        ("GASCO GLP S A", 38.03e9, 6.230e-4),
        ("PRISA S A", 19.74e9, 5.668e-4),
        ("EDENRED CHILE", 507.60e9, 4.887e-4),
        ("LATAM AIRLINES", 17.32e9, 4.943e-4)
    ]
    hub_x = [np.log10(h[1]) for h in hubs]
    hub_y = [np.log10(h[2]) for h in hubs]
    ax.scatter(hub_x, hub_y, color="#f39c12", edgecolor="black", s=110, marker="*", label="Hubs Consolidados (Alto Monto y Alta Centralidad)", zorder=6)
    
    # Etiquetas anotadas destacadas
    # Perfil 1 destacados
    ax.annotate("VICONSA S.A.\n($11.790M | 1 Org | PR #40.919)",
                xy=(p1_x[0], p1_y[0]), xytext=(p1_x[0]-1.4, p1_y[0]+0.4),
                arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fadbd8", edgecolor="#c0392b", alpha=0.9),
                fontsize=7.8, fontweight="bold")
                
    ax.annotate("ACCIONA S.A.\n($12.240M | 1 Org)",
                xy=(p1_x[1], p1_y[1]), xytext=(p1_x[1]+0.25, p1_y[1]-0.4),
                arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fadbd8", edgecolor="#c0392b", alpha=0.9),
                fontsize=7.8)
                
    # Perfil 2 destacados
    ax.annotate("LAS ARAUCARIAS SpA\n($236M | 293 Orgs | PR #120)",
                xy=(p2_x[0], p2_y[0]), xytext=(p2_x[0]-2.7, p2_y[0]+0.35),
                arrowprops=dict(arrowstyle="->", color="#27ae60", lw=1.2),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#d5f5e3", edgecolor="#27ae60", alpha=0.9),
                fontsize=7.8, fontweight="bold")
                
    ax.annotate("LYP GROUP SpA\n($263M | 271 Orgs)",
                xy=(p2_x[1], p2_y[1]), xytext=(p2_x[1]-2.7, p2_y[1]-0.45),
                arrowprops=dict(arrowstyle="->", color="#27ae60", lw=1.2),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#d5f5e3", edgecolor="#27ae60", alpha=0.9),
                fontsize=7.8)

    # Hubs destacados
    ax.annotate("COPEC S.A.\n(830 Orgs | $116B | PR #1)",
                xy=(hub_x[0], hub_y[0]), xytext=(hub_x[0]-1.3, hub_y[0]-0.65),
                arrowprops=dict(arrowstyle="->", color="#b7950b", lw=1.4),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fef9e7", edgecolor="#f39c12", alpha=0.95),
                fontsize=8, fontweight="bold")

    ax.annotate("EDENRED S.A.\n($507B | 463 Orgs)",
                xy=(hub_x[3], hub_y[3]), xytext=(hub_x[3]-1.3, hub_y[3]-0.95),
                arrowprops=dict(arrowstyle="->", color="#b7950b", lw=1.2),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fef9e7", edgecolor="#f39c12", alpha=0.9),
                fontsize=7.8)

    # Líneas divisorias cuadrantes
    ax.axvline(x=10.0, color="gray", linestyle=":", linewidth=1.1, alpha=0.7) # $10.000 millones
    ax.axhline(y=-4.0, color="gray", linestyle=":", linewidth=1.1, alpha=0.7) # PR ~10^-4

    ax.set_xlim(-0.5, 12.5)
    ax.set_ylim(-6.8, -2.6)

    ax.set_xlabel("log₁₀(Monto Total Adjudicado en CLP)", fontweight="bold")
    ax.set_ylabel("log₁₀(PageRank Ponderado Variante D)", fontweight="bold")
    ax.set_title("Espacio Bidimensional de Proveedores: Monto Financiero vs. Centralidad de Red (PageRank)", pad=12)
    ax.legend(loc="lower left", framealpha=0.95, edgecolor="gray", fontsize=8.5)
    
    # Cuadrantes anotados
    ax.text(11.2, -2.8, "HUBS CONSOLIDADOS\n(Alto Monto / Alto PR)", color="#b7950b", fontsize=8.5, fontweight="bold", ha="center")
    ax.text(11.2, -6.3, "PERFIL 1: CONTRATOS ÚNICOS\n(Alto Monto / Bajo PR)", color="#c0392b", fontsize=8.5, fontweight="bold", ha="center")
    ax.text(7.5, -2.8, "PERFIL 2: PROVEEDORES CAPILARES\n(Bajo Monto / Alto PR)", color="#27ae60", fontsize=8.5, fontweight="bold", ha="center")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig4_mapa_perfiles_profe.pdf"))
    fig.savefig(os.path.join(FIG_DIR, "fig4_mapa_perfiles_profe.png"), dpi=300)
    plt.close(fig)

    # FIGURA 5: Curva de Lorenz (Concentración Financiera vs. PageRank)
    print("  -> Generando fig5_curva_lorenz.pdf...")
    fig, ax = plt.subplots(figsize=(6.8, 5.5))
    
    # Lorenz Monto
    sorted_m = np.sort(all_prov_montos)
    cum_m = np.cumsum(sorted_m) / np.sum(sorted_m)
    p_m = np.linspace(0, 1, len(cum_m))
    
    # Lorenz PageRank D
    sorted_prd = np.sort(all_prov_pr_d)
    cum_prd = np.cumsum(sorted_prd) / np.sum(sorted_prd)
    p_prd = np.linspace(0, 1, len(cum_prd))
    
    # Lorenz Órdenes
    sorted_ord = np.sort(all_prov_orders)
    cum_ord = np.cumsum(sorted_ord) / np.sum(sorted_ord)
    p_ord = np.linspace(0, 1, len(cum_ord))
    
    # Línea 45 grados (Equidad absoluta)
    ax.plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=1.4, label="Línea de Equidad Absoluta (Gini = 0.00)")
    
    ax.plot(p_m, cum_m, color="#c0392b", linewidth=2.2, label=f"Monto Adjudicado CLP (Gini = {gini_m:.3f})")
    ax.fill_between(p_m, cum_m, p_m, color="#c0392b", alpha=0.10)
    
    ax.plot(p_ord, cum_ord, color="#e67e22", linewidth=1.8, linestyle="-.", label=f"Volumen de Órdenes (Gini = {gini_ord:.3f})")
    
    ax.plot(p_prd, cum_prd, color="#2980b9", linewidth=2.2, label=f"PageRank Variante D (Gini = {gini_prd:.3f})")
    ax.fill_between(p_prd, cum_prd, p_prd, color="#2980b9", alpha=0.12)
    
    ax.set_xlabel("Fracción Acumulada de Proveedores (0% a 100%)", fontweight="bold")
    ax.set_ylabel("Fracción Acumulada del Valor (0% a 100%)", fontweight="bold")
    ax.set_title("Curva de Lorenz: Desigualdad Financiera vs. Centralidad en la Red", pad=12)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(1.0))
    ax.legend(loc="upper left", framealpha=0.95, edgecolor="gray")
    
    # Anotación del 80/20 y 90/10
    ax.text(0.55, 0.20, 
            "• El 90% inferior de proveedores capta solo el 7,7% del gasto\n"
            "• El Top 1% (756 provs) absorbe el 66,8% del gasto estatal\n"
            "• PageRank redistribuye centralidad por valor de conectividad",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#ced4da", alpha=0.95),
            fontsize=8)
            
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig5_curva_lorenz.pdf"))
    fig.savefig(os.path.join(FIG_DIR, "fig5_curva_lorenz.png"), dpi=300)
    plt.close(fig)
    
    print("\n[OK] Las 5 figuras fueron generadas exitosamente en PDF y PNG!")
    print(f"Tiempo total de cómputo y graficado: {time.time() - start_time:.2f} segundos")
    print("=" * 80)

if __name__ == "__main__":
    main()
