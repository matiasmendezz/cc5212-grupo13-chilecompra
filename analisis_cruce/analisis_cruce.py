#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CC5212 - Procesamiento Masivo de Datos (Grupo 13)
Analisis del cruce Pig + PageRank.

Lee los archivos que escribe cruzar_resultados_cluster.py (tabla_maestra.csv, perfil1.csv,
perfil2.csv) y calcula:
  - Correlacion de Spearman entre monto y PageRank (y entre n. de organismos y PageRank)
  - Concentracion del gasto entre proveedores (top 1 %, 5 %, 10 % y Gini)
  - Detalle de los perfiles: monto por orden, percentil de PageRank, organismos
  - Solapamiento de los perfiles entre dos variantes de PageRank (opcional)
  - Grafico de dispersion ranking por monto vs ranking por PageRank

Uso:
  python analisis_cruce.py cruce_B_etapa3 --etiqueta "B bidireccional" --salida analisis_B
  python analisis_cruce.py cruce_B_etapa3 --alt cruce_A_etapa3 --salida analisis_B
"""

import argparse
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # sin ventana: solo guarda el PNG
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def leer(directorio, nombre):
    ruta = Path(directorio) / nombre
    return pd.read_csv(ruta, encoding="utf-8-sig")


def spearman(a, b):
    """Spearman = correlacion de Pearson entre rangos promedio (maneja empates). No requiere scipy."""
    return a.rank(method="average").corr(b.rank(method="average"))


def gini(valores):
    x = np.sort(np.asarray(valores, dtype=float))
    x = x[x >= 0]
    n = len(x)
    total = x.sum()
    if n == 0 or total == 0:
        return float("nan")
    i = np.arange(1, n + 1)
    return float((2 * np.sum(i * x)) / (n * total) - (n + 1) / n)


def main():
    ap = argparse.ArgumentParser(description="Analisis del cruce Pig + PageRank.")
    ap.add_argument("dir", help="carpeta con tabla_maestra.csv, perfil1.csv y perfil2.csv")
    ap.add_argument("--alt", help="carpeta de otra variante, para comparar los perfiles")
    ap.add_argument("--etiqueta", default="PageRank", help="nombre de la variante en el grafico")
    ap.add_argument("--salida", default="analisis", help="carpeta de salida")
    args = ap.parse_args()

    tabla = leer(args.dir, "tabla_maestra.csv")
    p1 = leer(args.dir, "perfil1.csv")
    p2 = leer(args.dir, "perfil2.csv")
    n = len(tabla)
    lineas = []

    def out(texto=""):
        print(texto)
        lineas.append(texto)

    out(f"=== ANALISIS ({args.etiqueta}) | {n:,} proveedores ===")

    # ---------- 1. Correlaciones ----------
    # Spearman sobre los valores (maneja empates con rangos promedio)
    rho_monto = spearman(tabla["monto_clp"], tabla["pagerank"])
    rho_orgs = spearman(tabla["n_orgs"], tabla["pagerank"])
    rho_ord = spearman(tabla["n_ordenes"], tabla["pagerank"])
    out("\n--- Correlacion de Spearman con el PageRank ---")
    out(f"monto total        vs PageRank: {rho_monto:+.3f}")
    out(f"n. de organismos   vs PageRank: {rho_orgs:+.3f}")
    out(f"n. de ordenes      vs PageRank: {rho_ord:+.3f}")
    out("(cerca de 0 = casi no se parecen; cerca de 1 = el PageRank repite ese ranking)")

    # ---------- 2. Concentracion del gasto ----------
    montos = np.sort(tabla["monto_clp"].to_numpy(dtype=float))[::-1]
    total = montos.sum()
    out("\n--- Concentracion del gasto entre proveedores ---")
    out(f"Monto total: {total:,.0f} CLP")
    for pct in (0.01, 0.05, 0.10):
        k = max(1, math.ceil(pct * n))
        out(f"El {pct*100:>4.0f} % superior ({k:,} proveedores) acumula "
            f"{montos[:k].sum() / total * 100:5.1f} % del monto")
    out(f"Indice de Gini del monto: {gini(montos):.3f}")

    # ---------- 3. Perfil 1 ----------
    out(f"\n--- Perfil 1: alto monto / bajo PageRank ({len(p1)} proveedores) ---")
    if len(p1):
        p1 = p1.copy()
        p1["monto_por_orden"] = p1["monto_clp"] / p1["n_ordenes"].replace(0, np.nan)
        p1["pct_rank_pr"] = p1["rank_pr"] / n * 100   # 100 = ultimo puesto de PageRank
        out(f"Percentil de PageRank (100 = el mas bajo): mediana {p1['pct_rank_pr'].median():.1f}, "
            f"minimo {p1['pct_rank_pr'].min():.1f}")
        out(f"Organismos distintos: mediana {p1['n_orgs'].median():.0f} | "
            f"ordenes: mediana {p1['n_ordenes'].median():.0f}")
        out(f"Monto por orden: mediana {p1['monto_por_orden'].median():,.0f} CLP")
        out("Top 10 por monto:")
        for _, r in p1.sort_values("rank_monto").head(10).iterrows():
            out(f"  #{int(r['rank_monto']):<4} {r['nombre'][:40]:40} | {r['monto_clp']/1e9:7.1f} mil M | "
                f"{int(r['n_ordenes']):>4} OCs | {int(r['n_orgs'])} org | "
                f"{r['monto_por_orden']/1e9:6.2f} mil M/orden | pct PR {r['pct_rank_pr']:.0f}")

    # ---------- 4. Perfil 2 ----------
    out(f"\n--- Perfil 2: bajo monto / alto PageRank ({len(p2)} proveedores) ---")
    if len(p2):
        p2 = p2.copy()
        p2["monto_por_orden"] = p2["monto_clp"] / p2["n_ordenes"].replace(0, np.nan)
        p2["pct_rank_monto"] = p2["rank_monto"] / n * 100
        out(f"Organismos distintos: mediana {p2['n_orgs'].median():.0f}, maximo {p2['n_orgs'].max():.0f}")
        out(f"Monto total: mediana {p2['monto_clp'].median()/1e6:,.1f} millones CLP")
        out(f"Percentil por monto (100 = el mas bajo): mediana {p2['pct_rank_monto'].median():.1f}")
        out(f"Monto por orden: mediana {p2['monto_por_orden'].median():,.0f} CLP")
        out("Top 10 por PageRank:")
        for _, r in p2.sort_values("rank_pr").head(10).iterrows():
            out(f"  PR #{int(r['rank_pr']):<4} {r['nombre'][:40]:40} | {r['monto_clp']/1e6:8.1f} M | "
                f"{int(r['n_ordenes']):>4} OCs | {int(r['n_orgs'])} org | pct monto {r['pct_rank_monto']:.0f}")

    # ---------- 5. Comparacion entre variantes ----------
    if args.alt:
        a1 = leer(args.alt, "perfil1.csv")
        a2 = leer(args.alt, "perfil2.csv")
        s1, s1a = set(p1["nodo"]), set(a1["nodo"])
        s2, s2a = set(p2["nodo"]), set(a2["nodo"])
        out(f"\n--- Solapamiento con la otra variante ({args.alt}) ---")
        out(f"Perfil 1: {len(s1)} aca | {len(s1a)} alla | en comun {len(s1 & s1a)}")
        out(f"Perfil 2: {len(s2)} aca | {len(s2a)} alla | en comun {len(s2 & s2a)}")
        alt_tabla = leer(args.alt, "tabla_maestra.csv")
        union = tabla[["nodo", "rank_pr", "pagerank"]].merge(
            alt_tabla[["nodo", "rank_pr", "pagerank"]], on="nodo", suffixes=("", "_alt"))
        rho = spearman(union["pagerank"], union["pagerank_alt"])
        out(f"Spearman entre los dos PageRank: {rho:+.3f}")

    # ---------- 6. Grafico ----------
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    if len(p1):
        p1.to_csv(salida / "perfil1_detalle.csv", index=False, encoding="utf-8-sig")
    if len(p2):
        p2.to_csv(salida / "perfil2_detalle.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    hb = ax.hexbin(np.log10(tabla["rank_monto"]), np.log10(tabla["rank_pr"]),
                   gridsize=60, cmap="Greys", mincnt=1, bins="log")
    if len(p1):
        ax.scatter(np.log10(p1["rank_monto"]), np.log10(p1["rank_pr"]), s=18, c="tab:red",
                   label=f"Perfil 1 ({len(p1)})", edgecolors="white", linewidths=0.3)
    if len(p2):
        ax.scatter(np.log10(p2["rank_monto"]), np.log10(p2["rank_pr"]), s=18, c="tab:blue",
                   label=f"Perfil 2 ({len(p2)})", edgecolors="white", linewidths=0.3)
    ax.set_xlabel("Ranking por monto (log10; 0 = el de mayor monto)")
    ax.set_ylabel(f"Ranking por PageRank, {args.etiqueta} (log10; 0 = el mas central)")
    ax.set_title(f"Monto vs PageRank (Spearman = {rho_monto:+.2f})")
    ax.legend(loc="lower left")
    fig.colorbar(hb, ax=ax, label="proveedores (escala log)")
    fig.tight_layout()
    fig.savefig(salida / "dispersion_monto_vs_pagerank.png", dpi=150)

    (salida / "resumen.txt").write_text("\n".join(lineas), encoding="utf-8")
    out(f"\nArchivos escritos en: {salida.resolve()}")


if __name__ == "__main__":
    main()
