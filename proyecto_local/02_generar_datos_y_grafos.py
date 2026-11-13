#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_generar_datos_y_grafos.py - CC5212 Procesamiento Masivo de Datos
Etapa 2: Generación de Archivos Limpios y Grafos Comprador-Proveedor

Genera:
1. ordenes_limpias.tsv.bz2: 1.856.075 órdenes limpias con banderas de auditoría.
2. ordenes_muestra.tsv: Muestra de 5.000 órdenes para pruebas locales de Pig.
3. nodos.tsv: 1.165 organismos (1000001..) y 75.603 proveedores (2000001..).
4. aristas.tsv: 476.717 aristas únicas organismo -> proveedor con n_ordenes, monto y log_monto.
5. aristas_muestra.tsv: Muestra de 1.000 aristas para pruebas locales de Giraph.
"""

import os
import sys
import csv
import bz2
import math
import glob
import time
import multiprocessing as mp
from collections import defaultdict

DATASET_DIR = "/home/matias/Desktop/cc5212/dataset"
OUTPUT_DIR = "/home/matias/Desktop/cc5212/proyecto_local/data"
NUM_WORKERS = min(12, os.cpu_count() or 4)

THRESHOLD_SOSPECHOSA = 10_000_000_000.0  # 10.000 millones de pesos
THRESHOLD_SIMBOLICA = 100.0              # 100 pesos

def clean_text(text: str) -> str:
    """Elimina tabuladores y saltos de línea para evitar romper formatos TSV."""
    if not text:
        return ""
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()

def parse_chilean_float(val: str) -> float:
    """Convierte coma decimal a float estándar."""
    if not val:
        return 0.0
    try:
        return float(val.strip().replace(",", "."))
    except (ValueError, TypeError):
        return 0.0

def process_monthly_file(fpath: str) -> dict:
    """Extrae las órdenes del mes de forma limpia y eficiente."""
    fname = os.path.basename(fpath)
    month_num = int(fname.replace("2025-", "").replace(".csv", ""))
    
    orders = {}
    with open(fpath, "r", encoding="latin-1", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        try:
            next(reader)  # Header
        except StopIteration:
            return orders
        
        for r in reader:
            if len(r) < 78:
                continue
            
            codigo = clean_text(r[1])
            item_moneda = clean_text(r[72])
            item_neto = parse_chilean_float(r[77]) if len(r) > 77 else 0.0
            
            if codigo not in orders:
                order_id = clean_text(r[0])
                estado = clean_text(r[14])
                monto_orig = parse_chilean_float(r[26])
                moneda_oc = clean_text(r[27])
                monto_clp = parse_chilean_float(r[28])
                
                org_cod = clean_text(r[37])
                org_nom = clean_text(r[38])
                sector = clean_text(r[39])
                
                rut_suc = clean_text(r[45])
                cod_prov = clean_text(r[47])
                prov_nom = clean_text(r[48])
                prov_id = cod_prov if cod_prov else rut_suc
                
                orders[codigo] = {
                    "id_orden": order_id,
                    "codigo_oc": codigo,
                    "mes": month_num,
                    "estado": estado,
                    "codigo_organismo": org_cod,
                    "nombre_organismo": org_nom,
                    "sector": sector,
                    "id_proveedor": prov_id,
                    "rut_proveedor": rut_suc,
                    "nombre_proveedor": prov_nom,
                    "moneda_oc": moneda_oc,
                    "monto_orig": monto_orig,
                    "monto_bruto_clp": monto_clp,
                    "item_monedas": {item_moneda},
                    "sum_item_neto": item_neto
                }
            else:
                orders[codigo]["item_monedas"].add(item_moneda)
                orders[codigo]["sum_item_neto"] += item_neto

    # Convertir sets a listas para serialización inter-proceso
    for o in orders.values():
        o["item_monedas"] = sorted(list(o["item_monedas"]))
        
    return orders

def main():
    start_time = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print("CC5212 - ETAPA 2: GENERACIÓN DE ARCHIVOS LIMPIOS Y GRAFOS")
    print(f"Salida en: {OUTPUT_DIR}")
    print(f"Procesos concurrentes: {NUM_WORKERS}")
    print("=" * 80)
    
    csv_pattern = os.path.join(DATASET_DIR, "2025-*.csv")
    csv_files = [f for f in glob.glob(csv_pattern) if not os.path.basename(f).startswith(".~lock")]
    csv_files.sort(key=lambda x: int(os.path.basename(x).replace("2025-", "").replace(".csv", "")))
    
    print("\n[1/5] Extrayendo órdenes de los 12 archivos CSV...")
    ctx = mp.get_context("fork")
    with ctx.Pool(NUM_WORKERS) as pool:
        results = pool.map(process_monthly_file, csv_files)
        
    all_orders = {}
    for month_orders in results:
        all_orders.update(month_orders)
        
    total_orders = len(all_orders)
    print(f"  -> Total órdenes únicas extraídas: {total_orders:,}")
    
    # [2/5] Clasificación de banderas de auditoría y cálculo de monto limpio
    print("\n[2/5] Aplicando banderas de auditoría y montos limpios...")
    
    # Regla 1: Corregidas (Cabecera no CLP, items en CLP)
    corr_codigos = set()
    for cod, o in all_orders.items():
        if o["moneda_oc"] != "CLP" and "CLP" in o["item_monedas"]:
            corr_codigos.add(cod)
            
    # Regla 2: Sospechosas (> 10.000M CLP en moneda extranjera y no corregida)
    sosp_codigos = set()
    for cod, o in all_orders.items():
        if o["moneda_oc"] != "CLP" and cod not in corr_codigos:
            if o["monto_bruto_clp"] > THRESHOLD_SOSPECHOSA:
                sosp_codigos.add(cod)
                
    # Asignar flag y monto limpio
    valid_orders_list = []
    flag_counts = defaultdict(int)
    
    for cod, o in all_orders.items():
        estado = o["estado"]
        m_bruto = o["monto_bruto_clp"]
        m_orig = o["monto_orig"]
        
        if estado == "Cancelacion solicitada":
            flag = "CANCELADA"
            m_limpio = 0.0
        elif cod in corr_codigos:
            flag = "CORREGIDA_45"
            m_limpio = m_orig
        elif cod in sosp_codigos:
            flag = "SOSPECHOSA_21"
            m_limpio = 0.0
        elif m_bruto <= THRESHOLD_SIMBOLICA:
            flag = "SIMBOLICA"
            m_limpio = m_bruto
        else:
            flag = "NORMAL"
            m_limpio = m_bruto
            
        o["flag_regla"] = flag
        o["monto_limpio_clp"] = m_limpio
        flag_counts[flag] += 1
        
        if flag != "CANCELADA":
            valid_orders_list.append(o)
            
    print("  -> Distribución de banderas:")
    for flg, cnt in sorted(flag_counts.items(), key=lambda x: -x[1]):
        print(f"     * {flg:15}: {cnt:>10,}")
    print(f"  -> Total órdenes válidas: {len(valid_orders_list):,}")
    
    # [3/5] Generar ordenes_limpias.tsv.bz2 y ordenes_muestra.tsv
    print("\n[3/5] Escribiendo ordenes_limpias.tsv.bz2 y muestra...")
    path_ordenes_bz2 = os.path.join(OUTPUT_DIR, "ordenes_limpias.tsv.bz2")
    path_ordenes_muestra = os.path.join(OUTPUT_DIR, "ordenes_muestra.tsv")
    
    tsv_headers = [
        "id_orden", "codigo_oc", "mes", "estado", "codigo_organismo", "nombre_organismo",
        "sector", "id_proveedor", "rut_proveedor", "nombre_proveedor", "moneda_oc",
        "monto_bruto_clp", "monto_limpio_clp", "flag_regla"
    ]
    
    # Escribir TSV comprimido BZ2 con buffer amplio
    with bz2.open(path_ordenes_bz2, "wt", encoding="utf-8", compresslevel=9) as f_bz2, \
         open(path_ordenes_muestra, "w", encoding="utf-8") as f_muestra:
        
        header_line = "\t".join(tsv_headers) + "\n"
        f_bz2.write(header_line)
        f_muestra.write(header_line)
        
        muestra_counter = 0
        for cod, o in all_orders.items():
            row_vals = [
                o["id_orden"],
                o["codigo_oc"],
                str(o["mes"]),
                o["estado"],
                o["codigo_organismo"],
                o["nombre_organismo"],
                o["sector"],
                o["id_proveedor"],
                o["rut_proveedor"],
                o["nombre_proveedor"],
                o["moneda_oc"],
                f"{o['monto_bruto_clp']:.2f}",
                f"{o['monto_limpio_clp']:.2f}",
                o["flag_regla"]
            ]
            line = "\t".join(row_vals) + "\n"
            f_bz2.write(line)
            
            # Las primeras 5.000 válidas a muestra
            if o["flag_regla"] != "CANCELADA" and muestra_counter < 5000:
                f_muestra.write(line)
                muestra_counter += 1

    print(f"  -> Archivo generado: {path_ordenes_bz2} ({os.path.getsize(path_ordenes_bz2) / 1024 / 1024:.2f} MB)")
    print(f"  -> Archivo generado: {path_ordenes_muestra} ({os.path.getsize(path_ordenes_muestra) / 1024:.2f} KB)")
    
    # [4/5] Generar nodos.tsv
    print("\n[4/5] Mapeando nodos de la red comprador-proveedor...")
    org_dict = {}   # org_cod -> {nombre, sector, rut}
    prov_dict = {}  # prov_id -> {nombre, rut}
    
    for o in valid_orders_list:
        org_cod = o["codigo_organismo"]
        if org_cod not in org_dict:
            org_dict[org_cod] = {
                "nombre": o["nombre_organismo"],
                "sector": o["sector"],
                "rut": ""
            }
        
        prov_id = o["id_proveedor"]
        if prov_id not in prov_dict:
            prov_dict[prov_id] = {
                "nombre": o["nombre_proveedor"],
                "rut": o["rut_proveedor"]
            }
            
    print(f"  -> Organismos únicos identificados: {len(org_dict):,}")
    print(f"  -> Proveedores únicos identificados: {len(prov_dict):,}")
    
    # Asignación de ID enteros únicos:
    # Organismos: 1000001 en adelante
    # Proveedores: 2000001 en adelante
    org_to_id = {}
    prov_to_id = {}
    
    path_nodos = os.path.join(OUTPUT_DIR, "nodos.tsv")
    with open(path_nodos, "w", encoding="utf-8") as f_nodos:
        f_nodos.write("node_id_int\ttipo_nodo\tcodigo_original\trut\tnombre\tsector\n")
        
        cur_org_id = 1000001
        for org_cod, data in sorted(org_dict.items()):
            org_to_id[org_cod] = cur_org_id
            f_nodos.write(f"{cur_org_id}\tORGANISMO\t{org_cod}\t{data['rut']}\t{data['nombre']}\t{data['sector']}\n")
            cur_org_id += 1
            
        cur_prov_id = 2000001
        for prov_cod, data in sorted(prov_dict.items()):
            prov_to_id[prov_cod] = cur_prov_id
            f_nodos.write(f"{cur_prov_id}\tPROVEEDOR\t{prov_cod}\t{data['rut']}\t{data['nombre']}\tN/A\n")
            cur_prov_id += 1
            
    print(f"  -> Archivo generado: {path_nodos} ({os.path.getsize(path_nodos) / 1024 / 1024:.2f} MB)")
    
    # [5/5] Generar aristas.tsv y aristas_muestra.tsv
    print("\n[5/5] Agregando aristas organismo -> proveedor...")
    edge_aggregates = defaultdict(lambda: {"n_ordenes": 0, "monto_total_clp": 0.0})
    
    for o in valid_orders_list:
        u = org_to_id[o["codigo_organismo"]]
        v = prov_to_id[o["id_proveedor"]]
        edge_aggregates[(u, v)]["n_ordenes"] += 1
        edge_aggregates[(u, v)]["monto_total_clp"] += o["monto_limpio_clp"]
        
    total_edges = len(edge_aggregates)
    print(f"  -> Aristas únicas generadas: {total_edges:,}")
    
    path_aristas = os.path.join(OUTPUT_DIR, "aristas.tsv")
    path_aristas_muestra = os.path.join(OUTPUT_DIR, "aristas_muestra.tsv")
    
    with open(path_aristas, "w", encoding="utf-8") as f_aristas, \
         open(path_aristas_muestra, "w", encoding="utf-8") as f_aristas_m:
        
        header_aristas = "org_id_int\tprov_id_int\tn_ordenes\tmonto_total_clp\tlog_monto\n"
        f_aristas.write(header_aristas)
        f_aristas_m.write(header_aristas)
        
        aristas_counter = 0
        for (u, v), e_data in sorted(edge_aggregates.items()):
            n_ord = e_data["n_ordenes"]
            m_tot = e_data["monto_total_clp"]
            log_m = math.log(1.0 + max(0.0, m_tot))
            
            line = f"{u}\t{v}\t{n_ord}\t{m_tot:.2f}\t{log_m:.6f}\n"
            f_aristas.write(line)
            
            if aristas_counter < 1000:
                f_aristas_m.write(line)
                aristas_counter += 1
                
    print(f"  -> Archivo generado: {path_aristas} ({os.path.getsize(path_aristas) / 1024 / 1024:.2f} MB)")
    print(f"  -> Archivo generado: {path_aristas_muestra} ({os.path.getsize(path_aristas_muestra) / 1024:.2f} KB)")
    
    total_duration = time.time() - start_time
    print(f"\n[OK] Etapa 2 completada exitosamente en {total_duration:.2f} segundos.")
    print("=" * 80)

if __name__ == "__main__":
    main()
