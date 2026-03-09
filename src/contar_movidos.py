import sys
from pathlib import Path

# Adiciona o diretório 'src' ao path para encontrar o módulo database
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from database import get_connection

def contar_duplicatas_movidas():
    """
    Conecta ao banco de dados e conta o número de arquivos
    marcados com o status 'duplicata_removida'.
    """
    query = (
        "SELECT COUNT(*) FROM files "
        "WHERE motivo = 'duplicata_removida' OR status = 'duplicata_removida';"
    )

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            # fetchone() retorna uma tupla, pegamos o primeiro elemento
            count = cursor.fetchone()[0]

        print("=" * 50)
        print("📊 Verificação de Duplicatas Movidas")
        print("=" * 50)
        print(f"✅ Total de arquivos duplicados movidos: {count}")
        print("\nEste número é o registro definitivo do trabalho realizado.")

    except Exception as e:
        print(f"❌ Ocorreu um erro ao consultar o banco de dados: {e}")

if __name__ == "__main__":
    contar_duplicatas_movidas()
