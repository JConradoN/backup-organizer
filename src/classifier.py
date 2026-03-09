"""
classifier.py
Fase 2 — Classificação dos arquivos escaneados com OCR Integrado.
Versão otimizada:
- Batch inference: envia metadados ao Ollama
- Vision: OCR local via EasyOCR para imagens ambíguas
- ThreadPoolExecutor para chamadas paralelas à IA
- Heurísticas + deduplicação antes de qualquer chamada à IA
"""

import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

# Carrega .env da pasta raiz
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from database import (
    get_connection, atualizar_decisao, flush_decisoes_final,
    buscar_pendentes, marcar_erro
)
from heuristics import classificar

# Tenta importar o VisionProcessor (OCR)
try:
    from vision import VisionProcessor
    vision = VisionProcessor()
    HAS_VISION = True
except ImportError:
    HAS_VISION = False
    print("⚠️ Módulo vision.py não encontrado. Continuando sem OCR.")

# Configurações — lidas do .env
IA_BATCH_SIZE = int(os.getenv("IA_BATCH_SIZE", "10"))
IA_WORKERS    = int(os.getenv("IA_WORKERS", "2"))
OLLAMA_HOST   = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL", "phi3") # Recomendado p/ evitar alucinação

# ---------------------------------------------------------------------------
# Lógica de Destino
# ---------------------------------------------------------------------------

def calcular_destino(destino_base: str, resultado: dict, arquivo: dict) -> str:
    """Define para onde o arquivo vai se for ÚTIL ou AMBÍGUO."""
    if resultado["status"] == "lixo":
        return None  # Não gera caminho de destino para lixo

    base = Path(destino_base)
    if resultado["status"] == "ambiguo":
        return str(base / "REVISAR" / arquivo["nome"])

    categoria = resultado.get("categoria") or "outros"
    # Tenta extrair o ano da data de criação
    ano = "0000"
    if arquivo.get("data_criacao"):
        try:
            ano = arquivo["data_criacao"][:4]
        except: pass
    
    return str(base / categoria / ano / arquivo["nome"])

# ---------------------------------------------------------------------------
# Chamada ao Ollama (IA Local)
# ---------------------------------------------------------------------------

def chamar_ia_ollama(batch: list) -> list:
    """Envia uma lista de arquivos para a IA classificar."""
    prompt_sistema = (
        "Você é um organizador de arquivos profissional. "
        "Classifique os arquivos abaixo em: util, lixo ou ambiguo. "
        "REGRAS:\n"
        "1. UTIL: Fotos, vídeos, documentos (pdf, docx, xls), áudios, projetos (psd, ai).\n"
        "2. LIXO: .exe, .dll, caches, instaladores, logs, temporários.\n"
        "3. AMBIGUO: Se não tiver certeza absoluta.\n"
        "Responda APENAS um JSON array no formato: "
        '[{"nome": "...", "status": "util/lixo/ambiguo", "categoria": "...", "motivo": "..."}]'
    )

    lista_metadados = [
        {"nome": a["nome"], "ext": a["extensao"], "tamanho_kb": (a["tamanho"] or 0)//1024}
        for a in batch
    ]

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{prompt_sistema}\n\nArquivos:\n{json.dumps(lista_metadados)}",
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=60)
        data = response.json()
        return json.loads(data["response"])
    except Exception as e:
        raise Exception(f"Erro na IA: {str(e)}")

# ---------------------------------------------------------------------------
# Processamento Principal
# ---------------------------------------------------------------------------

def classificar_todos(destino: str, dry_run: bool = False):
    print(f"Modelo IA: {OLLAMA_MODEL} | Batch: {IA_BATCH_SIZE} | Workers IA: {IA_WORKERS}")
    
    arquivos = buscar_pendentes()
    if not arquivos:
        print("✅ Nada para classificar.")
        return {}

    stats = {"util": 0, "lixo": 0, "ambiguo": 0, "erros": 0, "ia_calls": 0}
    pendentes_ia = []

    # Passo 1: Heurística Rápida
    arquivos = [dict(a) for a in arquivos]  # sqlite3.Row → dict
    print(f"🔍 Analisando {len(arquivos)} arquivos...")
    for arq in arquivos:
        res = classificar(Path(arq["caminho_original"]), arq["tamanho"] or 0)
        
        if res["status"] in ("ambiguo", "ia_necessaria"):
            # Se for imagem e tivermos Vision, tentamos OCR antes de mandar pra IA
            if HAS_VISION and (arq.get("extensao") or "").lower() in ['.jpg', '.jpeg', '.png']:
                texto = vision.ler_imagem(arq["caminho_original"])
                if texto:
                    arq_mod = dict(arq)
                    arq_mod["nome"] = f"{arq['nome']} [CONTEÚDO OCR: {texto}]"
                    pendentes_ia.append(arq_mod)
                else:
                    pendentes_ia.append(arq)
            else:
                pendentes_ia.append(arq)
        else:
            # Salva decisão da heurística
            decisao_dict = {
                "caminho_original": arq["caminho_original"],
                "decisao": res["status"],
                "categoria": res["categoria"],
                "motivo": res["motivo"],
                "metodo": "heuristica",
                "confianca": res.get("confianca", 0.95),
                "caminho_destino": calcular_destino(destino, res, arq),
                "status": "processado",
            }
            atualizar_decisao(arq["caminho_original"], decisao_dict)
            stats[res["status"]] = stats.get(res["status"], 0) + 1

    # Passo 2: IA para os Ambíguos
    if pendentes_ia:
        batches = [pendentes_ia[i:i + IA_BATCH_SIZE] for i in range(0, len(pendentes_ia), IA_BATCH_SIZE)]
        print(f"🤖 Enviando {len(batches)} batches para {OLLAMA_MODEL}...")

        with ThreadPoolExecutor(max_workers=IA_WORKERS) as executor:
            futures = {executor.submit(chamar_ia_ollama, b): b for b in batches}
            
            for future in tqdm(as_completed(futures), total=len(batches), desc="IA Progress"):
                batch_orig = futures[future]
                try:
                    resultados_ia = future.result()
                    stats["ia_calls"] += 1
                    
                    # Mapeia resultados da IA de volta para o banco
                    for i, res_ia in enumerate(resultados_ia):
                        if i < len(batch_orig):
                            arq = batch_orig[i]
                            decisao_dict = {
                                "caminho_original": arq["caminho_original"],
                                "decisao": res_ia["status"],
                                "categoria": res_ia.get("categoria", "outros"),
                                "motivo": res_ia.get("motivo", "Classificado por IA"),
                                "metodo": "ia",
                                "confianca": res_ia.get("confianca", 0.75),
                                "caminho_destino": calcular_destino(destino, res_ia, arq),
                                "status": "processado",
                            }
                            atualizar_decisao(arq["caminho_original"], decisao_dict)
                            stats[res_ia["status"]] = stats.get(res_ia["status"], 0) + 1
                except Exception as e:
                    stats["erros"] += 1
                    for arq in batch_orig:
                        marcar_erro(arq["caminho_original"], str(e))

    # Garante commit de todas as decisões pendentes no buffer
    flush_decisoes_final()
    return stats

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--destino", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    classificar_todos(args.destino, args.dry_run)