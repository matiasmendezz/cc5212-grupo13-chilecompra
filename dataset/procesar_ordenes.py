import os
import zipfile
import csv
import glob

print("1. Descomprimiendo archivos ZIP...")
zip_files = glob.glob('*.zip')
zip_files.sort()

for zf in zip_files:
    print(f"   Extrayendo {zf}...")
    try:
        with zipfile.ZipFile(zf, 'r') as zip_ref:
            zip_ref.extractall()
    except Exception as e:
        print(f"   [!] Error extrayendo {zf}: {e}")

print("\n2. Contando filas por archivo CSV...")
csv_files = glob.glob('*.csv')
csv_files.sort()

total_rows = 0

for cf in csv_files:
    # Skip any lock files created by LibreOffice/Excel
    if cf.startswith('.~lock'):
        continue
        
    try:
        with open(cf, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f, delimiter=';')
            count = sum(1 for _ in reader)
            # Descontamos 1 de la cabecera
            filas_reales = count - 1 if count > 0 else 0
            print(f"   {cf}: {filas_reales:,} filas")
            total_rows += filas_reales
    except Exception as e:
        print(f"   [!] Error procesando {cf}: {e}")

print(f"\n3. TOTAL de filas reales: {total_rows:,}")
