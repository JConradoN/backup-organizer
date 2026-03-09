# AUTOMATION_STRATEGY

## Objetivo
Automatizar os fluxos validados sem retrabalho e com recuperacao facil em caso de interrupcao.

## Scripts envolvidos
- `src/sanitizar_pre_indexacao.py`
- `src/indexacao_texto.py`
- `src/auditoria_duplicatas_amigavel.py`
- (opcional) `src/garantir_copia_f.py`

## Principios
- Execucao por etapas, com logs por etapa.
- Primeira validacao em dry-run sempre que houver mudanca de regra.
- Indexacao incremental com `job_id` e checkpoint.
- OCR em lotes/noturno (mais pesado).
- Auditoria periodica para garantir consistencia de duplicatas.

## Perfis recomendados

### 1) Diario (rapido)
1. Sanitizacao dry-run (sem mover):
   - `python src/sanitizar_pre_indexacao.py --fonte F:/`
2. Indexacao incremental sem OCR:
   - `python src/indexacao_texto.py --fonte F:/ --job-id diario_sem_ocr --max-video-mb 50`
3. Busca/saude (opcional):
   - consultas de amostra no FTS.

### 2) Noturno OCR (lento)
1. Indexacao OCR com checkpoint:
   - `python src/indexacao_texto.py --fonte F:/ --ocr-imagens --job-id ocr_noturno --max-video-mb 50`
2. (Opcional) processamento em lote:
   - `--batch-size N --batch-number K`
3. Auditoria amigavel de duplicatas:
   - `python src/auditoria_duplicatas_amigavel.py`

### 3) Limpeza aplicada (manual/assistida)
1. Sanitizacao com aplicacao real:
   - `python src/sanitizar_pre_indexacao.py --fonte F:/ --apply`
2. Reindexar sem OCR (para refletir mudancas):
   - `python src/indexacao_texto.py --fonte F:/ --job-id diario_sem_ocr --max-video-mb 50`

## Recuperacao e retomada
- Se o processo cair no meio, rerun com o mesmo `--job-id`.
- Para reiniciar do zero o job:
  - `--reset-job`
- Para desabilitar retomada (execucao limpa sem checkpoint):
  - `--sem-resume`

## Observabilidade
- Progresso a cada 30s no indexador: `%`, taxa, ETA.
- Relatorios CSV:
  - `logs/relatorio_sanitizacao_pre_indexacao.csv`
  - `logs/relatorio_duplicatas_amigavel.csv`

## Agendamento Windows (futuro)
- Tarefa 1 (diaria): perfil `daily`
- Tarefa 2 (madrugada): perfil `nightly-ocr`
- Runner unico recomendado: `src/automation_pipeline.py`

## Politica de seguranca
- Nao deletar arquivo em automacao.
- Quarentena em vez de exclusao.
- Mudancas estruturais sempre com modo dry-run antes de apply.
