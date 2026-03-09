# HANDOFF

## Objetivo
Contexto de continuidade para novo chat, com estado tecnico e operacional consolidado.

## Projeto
- Nome: backup-organizer
- Plataforma principal: Windows
- Stack: Python + SQLite + EasyOCR + FTS5
- Banco principal: `backup_organizer.db`

## Arquivos-chave
- Pipeline core: `src/main.py`
- Indexacao/OCR: `src/indexacao_texto.py`, `src/vision.py`
- Automacao: `src/automation_pipeline.py`
- Monitor OCR: `monitor_ocr.ps1`
- Planejamento: `docs/SANITIZATION_AND_UIUX_PLAN.md`
- Baseline: `versions/v1_current/README.md`
- V2 inicial: `src_v2/README.md`

## O que foi feito na sessao
1. Correcao e validacao de scripts operacionais.
2. Evolucao da indexacao textual com checkpoint (`job_id`), filtros e OCR opcional.
3. Correcao de OCR em paths Unicode no Windows (`np.fromfile + cv2.imdecode`).
4. Criacao de estrategia e runner de automacao por perfis.
5. Investigacao de quedas de desempenho e concorrencia no OCR.
6. Inclusao de lock por `job_id` em `src/indexacao_texto.py` para bloquear instancias externas duplicadas.
7. Ajuste de taxa/ETA apos resume para refletir progresso da execucao atual.
8. Atualizacao da documentacao (`README.md`, `docs/PROJECT_HISTORY.md`, `docs/PROJECT_STATUS.md`).

## Estado operacional esperado
- OCR roda com checkpoint por `job_id`.
- Evitar multiplas execucoes independentes do mesmo job.
- Ler progresso via `text_index_jobs`.

## Estado Atual (2026-03-08)
- Job principal em foco: `ocr_dir_fotos_v2`.
- Sintoma recorrente observado: tentativa de resume retorna `Exit Code 1` repetidamente.
- Tentativas de encerramento de processo por `Stop-Process` foram executadas varias vezes; em varios momentos nao havia processo OCR ativo visivel para o `job_id`.
- Snapshot do job no banco continuou acessivel, indicando que o checkpoint existe e pode ser inspecionado a cada tentativa.
- Busca textual (`--buscar`) segue funcional no ambiente.

Hipoteses operacionais priorizadas:
1. Falha de inicializacao antes do loop principal (ambiente/dependencia/arquivo problemático) com retorno nao detalhado no terminal.
2. Estado residual de lock/processo em janela curta entre tentativas.
3. Erro pontual de leitura em lote inicial sem log suficiente no comando atual.

Proximo passo recomendado (ordem):
1. Rodar `monitor_ocr.ps1 -Once` para confirmar processo e snapshot de jobs no mesmo instante.
2. Relancar o comando do `ocr_dir_fotos_v2` e capturar saida completa em log de arquivo.
3. Se o erro persistir, executar `--reset-job` apenas para esse `job_id` como ultimo recurso.

## Comandos de continuidade
```powershell
# Retomar OCR do checkpoint atual
C:/Users/morph/dev-tools/backup-organizer/venv/Scripts/python.exe src/indexacao_texto.py --fonte F:/fotos --ocr-imagens --job-id ocr_dir_fotos_v2 --max-video-mb 50 --max-image-mb 15

# Snapshot rapido do status do job
C:/Users/morph/dev-tools/backup-organizer/venv/Scripts/python.exe -c "import sqlite3; c=sqlite3.connect('backup_organizer.db'); c.row_factory=sqlite3.Row; print(dict(c.execute(\"SELECT job_id,status,processed_count,total_count,updated_em FROM text_index_jobs WHERE job_id='ocr_dir_fotos_v2'\").fetchone() or {}))"

# Monitor de OCR
pwsh -NoProfile -ExecutionPolicy Bypass -File .\monitor_ocr.ps1
```

## Atencoes para o proximo chat
1. Confirmar se existe processo ativo antes de iniciar novo OCR.
2. Se houver comportamento de duplicata, inspecionar PID pai/filho antes de matar processo.
3. Usar logs e banco para validar progresso real (nao apenas % da GPU).
4. Manter historico de alteracoes de parametros para comparacao de desempenho.
