"""
Teste de persistência do atualizar_decisao
"""
import sqlite3
from database import buscar_pendentes, atualizar_decisao, flush_decisoes_final, DB_PATH

# Pega 1 arquivo pendente
arquivos = buscar_pendentes()
if not arquivos:
    print("Nenhum pendente")
    exit()

arq = dict(arquivos[0])
print(f"Arquivo: {arq['nome']}")
print(f"Status antes: {arq['status']}, decisao: {arq['decisao']}")

# Tenta atualizar
atualizar_decisao(arq["caminho_original"], {
    "caminho_original": arq["caminho_original"],
    "decisao": "util",
    "categoria": "fotos",
    "motivo": "TESTE",
    "metodo": "heuristica",
    "confianca": 0.99,
    "caminho_destino": "F:\\\\fotos\\\\2024\\\\teste.jpg",
    "status": "processado",
})
flush_decisoes_final()

# Verifica diretamente no SQLite
conn = sqlite3.connect(DB_PATH)
row = conn.execute(
    "SELECT status, decisao, motivo FROM files WHERE caminho_original=?",
    (arq["caminho_original"],)
).fetchone()
conn.close()

print(f"Status depois: {row[0]}, decisao: {row[1]}, motivo: {row[2]}")
if row[2] == "TESTE":
    print("\n✅ COMMIT FUNCIONANDO — o problema está em outro lugar")
else:
    print("\n❌ COMMIT NÃO PERSISTE — banco não está sendo atualizado")
