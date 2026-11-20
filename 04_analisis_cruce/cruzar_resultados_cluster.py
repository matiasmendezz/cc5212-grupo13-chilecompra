#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CC5212 - Procesamiento Masivo de Datos (Grupo 13)
Cruce de las salidas del clúster (Pig + Giraph) para buscar los dos perfiles:

  Entrada 1: nodos.tsv           nodo \t tipo_nodo \t nombre \t dato        (con cabecera)
  Entrada 2: ranking_monto.tsv   id \t nombre \t monto \t n_ordenes \t n_organismos   (salida de Pig)
  Entrada 3: pagerank.tsv        PROV_xxxx \t pagerank   (salida de Giraph, ordenada o no)

El id de Pig (ej. 27693) se une con el nodo del grafo agregando el prefijo "PROV_".

Criterios de los perfiles (--criterio):
  original : top 50 en monto con PageRank pasado el puesto 500 / top 30 en PageRank con monto pasado el 150
  etapa3   : los de 03_rankings_y_pagerank.py
             perfil 1: rank_monto <= 250 y n_orgs <= 3, ordenado por mayor disparidad
             perfil 2: rank_pr <= 150, rank_monto > 500 y n_orgs >= 25, ordenado por mayor ventaja de red
Cualquier umbral pasado por linea de comandos reemplaza al del criterio elegido.

Genera (en la carpeta --salida): tabla_maestra.csv, perfil1.csv, perfil2.csv
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

PREFIJO_PROV = "PROV_"

PRESETS = {
    "original": dict(p1_top_monto=50, p1_min_pr=500, p1_max_orgs=None,
                     p2_top_pr=30, p2_min_monto=150, p2_min_orgs=None,
                     orden="rank"),
    "etapa3": dict(p1_top_monto=250, p1_min_pr=None, p1_max_orgs=3,
                   p2_top_pr=150, p2_min_monto=500, p2_min_orgs=25,
                   orden="disparidad"),
}


def cargar_nodos(path):
    """Devuelve ({nodo: {nombre, dato}} solo de proveedores, Counter de tipos vistos)."""
    nodos = {}
    tipos = Counter()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3 or parts[0] == "nodo":  # cabecera o linea rara
                continue
            tipos[parts[1].strip().lower()] += 1
            if parts[1].strip().lower() != "proveedor":
                continue
            nodos[parts[0]] = {
                "nombre": parts[2],
                "dato": parts[3] if len(parts) > 3 else "",
            }
    return nodos, tipos


def cargar_pagerank(path):
    """Devuelve {nodo: pagerank}. Los ids son texto (ORG_xxxx / PROV_xxxx)."""
    pr = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            try:
                pr[parts[0]] = float(parts[1])
            except ValueError:
                continue
    return pr


def cargar_pig_ranking(path):
    """
    Lee ranking_monto: id \t nombre \t monto \t n_ordenes \t n_organismos
    Devuelve ({PROV_id: datos}, cantidad_de_lineas_descartadas).
    """
    fin = {}
    malas = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                malas += 1
                continue
            pid, nombre, monto, n_ord, n_org = parts
            clave = pid if pid.startswith(PREFIJO_PROV) else PREFIJO_PROV + pid
            try:
                # el monto puede venir vacio (suma null) o en notacion cientifica
                monto_f = float(monto) if monto.strip() else 0.0
                fin[clave] = {
                    "nombre": nombre,
                    "monto_clp": monto_f,
                    "n_ordenes": int(float(n_ord)),
                    "n_orgs": int(float(n_org)),
                }
            except ValueError:
                malas += 1
    return fin, malas


def escribir_csv(path, filas):
    campos = ["nodo", "nombre", "monto_clp", "n_ordenes", "n_orgs",
              "pagerank", "rank_monto", "rank_pr", "disparidad"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for r in filas:
            w.writerow({k: r[k] for k in campos})


def main():
    ap = argparse.ArgumentParser(description="Cruza ranking por monto (Pig) con PageRank (Giraph).")
    ap.add_argument("nodos")
    ap.add_argument("ranking_monto")
    ap.add_argument("pagerank")
    ap.add_argument("--salida", default=".", help="carpeta donde escribir los CSV")
    ap.add_argument("--criterio", choices=sorted(PRESETS), default="original",
                    help="conjunto de umbrales para los perfiles (por defecto: original)")
    ap.add_argument("--p1-top-monto", type=int, help="perfil 1: ranking por monto <= N")
    ap.add_argument("--p1-min-pr", type=int, help="perfil 1: ranking PageRank > N")
    ap.add_argument("--p1-max-orgs", type=int, help="perfil 1: organismos distintos <= N")
    ap.add_argument("--p2-top-pr", type=int, help="perfil 2: ranking PageRank <= N")
    ap.add_argument("--p2-min-monto", type=int, help="perfil 2: ranking por monto > N")
    ap.add_argument("--p2-min-orgs", type=int, help="perfil 2: organismos distintos >= N")
    args = ap.parse_args()

    # umbrales efectivos: preset elegido, reemplazado por lo que se pase explicitamente
    cfg = dict(PRESETS[args.criterio])
    for k in ("p1_top_monto", "p1_min_pr", "p1_max_orgs", "p2_top_pr", "p2_min_monto", "p2_min_orgs"):
        v = getattr(args, k)
        if v is not None:
            cfg[k] = v

    nodos, tipos = cargar_nodos(args.nodos)
    fin, malas = cargar_pig_ranking(args.ranking_monto)
    pr = cargar_pagerank(args.pagerank)
    pr_prov = {k: v for k, v in pr.items() if k.startswith(PREFIJO_PROV)}

    # ---------- Diagnostico: sirve para validar antes de interpretar ----------
    print("=== DIAGNOSTICO ===")
    print(f"Tipos de nodo en nodos.tsv: {dict(tipos)}")
    print(f"Proveedores en nodos.tsv:        {len(nodos):,}")
    print(f"Proveedores en Pig:              {len(fin):,}  (control Colab: ~75.600)")
    print(f"Proveedores con PageRank:        {len(pr_prov):,}")
    print(f"Lineas de Pig descartadas:       {malas}")
    sin_pr = [k for k in fin if k not in pr_prov]
    sin_nodo = [k for k in fin if k not in nodos]
    print(f"En Pig pero sin PageRank:        {len(sin_pr):,}")
    print(f"En Pig pero sin nodo en nodos:   {len(sin_nodo):,}")
    print(f"Suma de ordenes (Pig):           {sum(v['n_ordenes'] for v in fin.values()):,}  (control: 1.853.390)")
    print(f"Suma de monto limpio (Pig):      {sum(v['monto_clp'] for v in fin.values()):,.0f}  (control: ~18,18 billones)")
    print(f"Suma de PageRank (todos nodos):  {sum(pr.values()):.6f}  (debe ser ~1)")
    if pr_prov:
        distintos = len(set(round(v, 15) for v in pr_prov.values()))
        print(f"Valores distintos de PageRank entre proveedores: {distintos:,} de {len(pr_prov):,}  "
              f"(pocos = muchos empates; los puestos dentro de un empate son arbitrarios)")

    # Los nombres de Pig y de nodos.tsv deberian coincidir para un mismo id
    comunes = [k for k in fin if k in nodos]
    if comunes:
        iguales = sum(1 for k in comunes
                      if fin[k]["nombre"].strip().lower() == nodos[k]["nombre"].strip().lower())
        print(f"Nombre Pig == nombre nodos:      {iguales:,} de {len(comunes):,}  "
              f"(si es muy bajo, el prefijo PROV_ no es la union correcta)")

    # ---------- Tabla maestra ----------
    consolidado = []
    for clave, f_row in fin.items():
        if clave not in pr_prov:
            continue  # sin PageRank no se puede comparar
        consolidado.append({
            "nodo": clave,
            "nombre": f_row["nombre"],
            "monto_clp": f_row["monto_clp"],
            "n_ordenes": f_row["n_ordenes"],
            "n_orgs": f_row["n_orgs"],
            "pagerank": pr_prov[clave],
        })

    if not consolidado:
        print("\nNo se pudo unir ningun proveedor. Revisa el diagnostico de arriba.")
        sys.exit(1)

    # Desempate determinista por nombre de nodo (no por monto, para no sesgar los perfiles)
    consolidado.sort(key=lambda x: (-x["monto_clp"], x["nodo"]))
    for i, r in enumerate(consolidado, 1):
        r["rank_monto"] = i
    consolidado.sort(key=lambda x: (-x["pagerank"], x["nodo"]))
    for i, r in enumerate(consolidado, 1):
        r["rank_pr"] = i
        r["disparidad"] = r["rank_pr"] - r["rank_monto"]  # alto = mucho monto, poco PageRank

    # ---------- Perfiles ----------
    def cumple_p1(r):
        return (r["rank_monto"] <= cfg["p1_top_monto"]
                and (cfg["p1_min_pr"] is None or r["rank_pr"] > cfg["p1_min_pr"])
                and (cfg["p1_max_orgs"] is None or r["n_orgs"] <= cfg["p1_max_orgs"]))

    def cumple_p2(r):
        return (r["rank_pr"] <= cfg["p2_top_pr"]
                and r["rank_monto"] > cfg["p2_min_monto"]
                and (cfg["p2_min_orgs"] is None or r["n_orgs"] >= cfg["p2_min_orgs"]))

    perfil_1 = [r for r in consolidado if cumple_p1(r)]
    perfil_2 = [r for r in consolidado if cumple_p2(r)]
    if cfg["orden"] == "disparidad":
        perfil_1.sort(key=lambda x: -x["disparidad"])
        perfil_2.sort(key=lambda x: x["disparidad"])      # mas negativo = mayor ventaja de red
    else:
        perfil_1.sort(key=lambda x: x["rank_monto"])
        perfil_2.sort(key=lambda x: x["rank_pr"])

    print(f"\nCriterio: {args.criterio} | umbrales efectivos: {cfg}")
    print(f"Proveedores unidos (Pig + PageRank): {len(consolidado):,}")
    print(f"Perfil 1: {len(perfil_1)} candidatos | Perfil 2: {len(perfil_2)} candidatos "
          f"(Colab dirigido: 142 y 10; dependen del criterio y de la variante)")

    print("\n=== PERFIL 1 (ALTO MONTO / BAJO PAGERANK) ===")
    for r in perfil_1[:10]:
        print(f"RankMonto #{r['rank_monto']:<5} | RankPR #{r['rank_pr']:<6} | "
              f"Orgs: {r['n_orgs']:<4} | OCs: {r['n_ordenes']:<6} | "
              f"${r['monto_clp']/1e6:,.1f}M | {r['nombre']}")

    print("\n=== PERFIL 2 (BAJO MONTO / ALTO PAGERANK) ===")
    for r in perfil_2[:10]:
        print(f"RankPR #{r['rank_pr']:<5} | RankMonto #{r['rank_monto']:<6} | "
              f"Orgs: {r['n_orgs']:<4} | OCs: {r['n_ordenes']:<6} | "
              f"${r['monto_clp']/1e6:,.1f}M | {r['nombre']}")

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    escribir_csv(salida / "tabla_maestra.csv", consolidado)
    escribir_csv(salida / "perfil1.csv", perfil_1)
    escribir_csv(salida / "perfil2.csv", perfil_2)
    print(f"\nArchivos escritos en: {salida.resolve()}")


if __name__ == "__main__":
    main()
