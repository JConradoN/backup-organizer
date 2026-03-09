# PROJECT_STATUS

## Status executivo
- Projeto funcional e em uso real no Windows.
- Pipeline principal estavel (scan/classify/copy).
- Indexacao textual funcional com OCR opcional e checkpoint.
- Automacao por perfis implementada.

## Componentes principais
- Core operacional: `src/main.py`, `src/scanner.py`, `src/classifier.py`, `src/mover.py`, `src/database.py`
- Indexacao/busca: `src/indexacao_texto.py`
- OCR: `src/vision.py`
- Ferramentas de auditoria/sanitizacao: scripts em `src/`
- Automacao: `src/automation_pipeline.py`

## Estado atual de versoes
- Baseline congelada: `versions/v1_current/`
- Evolucao planejada: `src_v2/`

## Riscos e pontos de atencao
1. Concorrencia indevida no mesmo job OCR
- Mitigado com lock por `job_id`, mas o backend OCR pode abrir processo filho interno.

2. Variacao de desempenho em OCR
- Taxa varia por tipo/tamanho de imagem e I/O do disco USB.
- ETA deve ser lido como estimativa, nao garantia.

3. Sensibilidade operacional
- Comandos manuais repetidos podem iniciar/encerrar processos fora de ordem.

## Regras operacionais recomendadas
1. Usar sempre o mesmo `job_id` para retomar.
2. Evitar iniciar multiplas instancias independentes do mesmo job.
3. Monitorar por progresso no banco (`text_index_jobs`) e nao so GPU.
4. Registrar runs em logs antes de mudancas de parametro.

## Comandos de saude rapidos
```powershell
# Snapshot do job
C:/.../venv/Scripts/python.exe -c "import sqlite3; c=sqlite3.connect('backup_organizer.db'); c.row_factory=sqlite3.Row; print(dict(c.execute(\"SELECT job_id,status,processed_count,total_count,updated_em FROM text_index_jobs WHERE job_id='ocr_dir_fotos_v2'\").fetchone() or {}))"

# Processo ativo do OCR
Get-CimInstance Win32_Process | ? { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'indexacao_texto.py' -and $_.CommandLine -match 'ocr_dir_fotos_v2' }
```

## Proximos passos recomendados
1. Consolidar runbook unico de OCR (start/stop/status).
2. Encapsular monitoramento em um comando unico com saida padrao.
3. Migrar gradualmente para `src_v2` mantendo compatibilidade.
