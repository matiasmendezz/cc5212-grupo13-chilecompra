#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CC5212 - Grupo 13
Script para verificar automáticamente los resultados de Pig descargados en el Paso 5
de la Parte 4 (contra los valores de referencia de Colab: ~75.600 proveedores,
~1.853.390 órdenes usadas y ~18,18 billones de pesos de monto limpio).
"""

import os
import sys

DIR_RESULTADOS = sys.argv[1] if len(sys.argv) > 1 else "resultados_pig"

def verificar_ranking_monto(path):
    n_provs = 0
    suma_monto = 0.0
    suma_ordenes = 0
    top5 = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            n_provs += 1
            monto = float(parts[2])
            ordenes = int(parts[3])
            orgs = int(parts[4])
            suma_monto += monto
            suma_ordenes += ordenes
            if len(top5) < 5:
                top5.append((parts[0], parts[1], monto, ordenes, orgs))

    print("======================================================================")
    print("VERIFICACIÓN DE CONTROL (ranking_monto.tsv vs Referencia de Colab)")
    print("======================================================================")
    print(f"  Proveedores únicos : {n_provs:>12,}  (Referencia Colab: ~75,600)")
    print(f"  Órdenes usadas     : {suma_ordenes:>12,}  (Referencia Colab: ~1,853,390)")
    print(f"  Monto limpio total : ${suma_monto/1e12:>11.2f} billones CLP (Referencia: $18.18 billones)")
    print("\nTop 5 Proveedores por Monto Total Limpio:")
    for i, (pid, nom, m, o, org) in enumerate(top5, 1):
        print(f"  #{i} [{pid}] {nom[:40]:40s} | ${m/1e6:>10,.1f}M | {o:>5} OC | {org:>3} orgs")

def mostrar_top(path, titulo, unidad_col2="monto"):
    if not os.path.exists(path):
        return
    print(f"\n--- {titulo} ({os.path.basename(path)}) ---")
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if i > 5:
                break
            print("  " + line.strip())

def main():
    rm_path = os.path.join(DIR_RESULTADOS, "ranking_monto.tsv")
    if not os.path.exists(rm_path):
        print(f"No se encontró {rm_path}. Uso: python3 verificar_paso4_pig.py <carpeta_resultados_pig>")
        sys.exit(1)

    verificar_ranking_monto(rm_path)
    mostrar_top(os.path.join(DIR_RESULTADOS, "ranking_ordenes.tsv"), "Top 5 por Número de Órdenes")
    mostrar_top(os.path.join(DIR_RESULTADOS, "ranking_organismos.tsv"), "Top 5 por Organismos Distintos")
    mostrar_top(os.path.join(DIR_RESULTADOS, "concentracion_sector.tsv"), "Concentración por Sector")
    mostrar_top(os.path.join(DIR_RESULTADOS, "evolucion_mensual.tsv"), "Evolución Mensual (primeros 5 meses)")

if __name__ == "__main__":
    main()
