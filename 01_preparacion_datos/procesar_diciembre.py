import os
import zipfile
import csv

zf = '2025-12.zip'
cf = '2025-12.csv'

if os.path.exists(zf):
    print(f"Extrayendo {zf}...")
    try:
        with zipfile.ZipFile(zf, 'r') as zip_ref:
            zip_ref.extractall()
    except Exception as e:
        print(f"[!] Error extrayendo {zf}: {e}")

if os.path.exists(cf):
    print(f"Contando filas en {cf}...")
    try:
        with open(cf, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f, delimiter=';')
            count = sum(1 for _ in reader)
            # Descontamos 1 de la cabecera
            filas_reales = count - 1 if count > 0 else 0
            print(f"{cf}: {filas_reales:,} filas")
    except Exception as e:
        print(f"[!] Error procesando {cf}: {e}")
else:
    print(f"[!] Archivo {cf} no encontrado luego de extraer.")
