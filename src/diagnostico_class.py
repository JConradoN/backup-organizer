"""
Diagnóstico: testa classificação em 10 arquivos pendentes
e mostra por que o classifier termina sem processar.
"""
from pathlib import Path
from database import buscar_pendentes, get_connection
from heuristics import classificar

arquivos = buscar_pendentes()
print(f"Total pendentes: {len(arquivos)}")

amostra = [dict(a) for a in arquivos[:20]]
stats = {}
for arq in amostra:
    res = classificar(Path(arq["caminho_original"]), arq["tamanho"] or 0)
    s = res["status"]
    stats[s] = stats.get(s, 0) + 1
    print(f"  {s:<15} {arq['extensao'] or '(sem ext)':<12} {arq['nome'][:50]}")

print(f"\nResumo dos 20 primeiros: {stats}")
