# RUNBOOK_OCR

## Objetivo
Runbook operacional para executar OCR com checkpoint, monitorar progresso e recuperar falhas sem perder estado.

## Escopo
- Script principal: `src/indexacao_texto.py`
- Monitor: `monitor_ocr.ps1`
- Banco: `backup_organizer.db` (tabela `text_index_jobs`)

## Pre-requisitos
1. Estar na raiz do projeto: `C:\Users\morph\dev-tools\backup-organizer`
2. Usar Python da venv:
```powershell
$py = "C:/Users/morph/dev-tools/backup-organizer/venv/Scripts/python.exe"
```
3. Validar help do comando:
```powershell
& $py src/indexacao_texto.py --help
```

## Convencao de job_id
- Padrao recomendado: `ocr_dir_<pasta>_v2`
- Exemplo para `F:/fotos`: `ocr_dir_fotos_v2`
- Regra: manter o mesmo `job_id` para retomar checkpoint.

## Procedimento padrao (start/resume)
1. Iniciar ou retomar OCR da pasta alvo:
```powershell
& $py src/indexacao_texto.py --fonte F:/fotos --ocr-imagens --job-id ocr_dir_fotos_v2 --max-video-mb 50 --max-image-mb 15
```
2. Em caso de interrupcao, repetir exatamente o mesmo comando para retomar.

## Monitoramento operacional
1. Monitor continuo (processos + jobs):
```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\monitor_ocr.ps1
```
2. Snapshot unico (sem loop):
```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\monitor_ocr.ps1 -Once -JobLike "ocr_dir_%"
```
3. Snapshot direto do job no banco:
```powershell
& $py -c "import sqlite3; c=sqlite3.connect('backup_organizer.db'); c.row_factory=sqlite3.Row; print(dict(c.execute(\"SELECT job_id,status,processed_count,total_count,updated_em FROM text_index_jobs WHERE job_id='ocr_dir_fotos_v2'\").fetchone() or {}))"
```

## Stop controlado
1. Encontrar processo ativo do job:
```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'indexacao_texto.py' -and $_.CommandLine -match '--job-id\s+ocr_dir_fotos_v2' }
```
2. Encerrar processo do job (apenas se necessario):
```powershell
$targets = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'indexacao_texto.py' -and $_.CommandLine -match '--job-id\s+ocr_dir_fotos_v2' }
if($targets){ $targets | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "Encerrado PID $($_.ProcessId)" } } else { Write-Host 'Nenhum OCR ativo para o job.' }
```
3. Retomar com o mesmo comando de start/resume.

## Recuperacao de falhas (RC=1)
Quando `indexacao_texto.py` retorna `Exit Code 1`, usar este checklist:

1. Validar lock/logica de processo unico
- O script usa lock por `job_id` (`logs/locks/indexacao_<job_id>.lock`).
- Se houver outra instancia ativa, a instancia nova deve encerrar.

2. Confirmar se ainda existe processo ativo do mesmo `job_id`
```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'indexacao_texto.py' -and $_.CommandLine -match '--job-id\s+ocr_dir_fotos_v2' }
```

3. Se existir processo zombie/antigo, encerrar e relancar
- Use o bloco de `Stop controlado`.
- Relance o comando de start/resume.

4. Validar estado do checkpoint no banco
```powershell
& $py -c "import sqlite3; c=sqlite3.connect('backup_organizer.db'); c.row_factory=sqlite3.Row; print(dict(c.execute(\"SELECT job_id,fonte,status,processed_count,total_count,updated_em FROM text_index_jobs WHERE job_id='ocr_dir_fotos_v2'\").fetchone() or {}))"
```

5. Resetar job apenas em ultimo caso
- Use quando checkpoint estiver inconsistente e voce aceitar reprocessar o job.
```powershell
& $py src/indexacao_texto.py --fonte F:/fotos --ocr-imagens --job-id ocr_dir_fotos_v2 --reset-job --max-video-mb 50 --max-image-mb 15
```

## Boas praticas
1. Nao rodar duas instancias independentes para o mesmo `job_id`.
2. Monitorar progresso no banco, nao apenas uso de GPU.
3. Tratar ETA como estimativa (varia por I/O, tamanho e qualidade das imagens).
4. Registrar parametros usados em cada run para comparar performance.

## Operacao em multiplas pastas
Exemplo sequencial por pasta (uma de cada vez):
```powershell
$py='C:/Users/morph/dev-tools/backup-organizer/venv/Scripts/python.exe'
$dirs=@('F:/fotos','F:/musica','F:/outros','F:/projetos','F:/quarentena_lixo_internet','F:/videos')
foreach($dir in $dirs){
  $name=[IO.Path]::GetFileName($dir).ToLower()
  $safe=($name -replace '[^a-z0-9]+','_').Trim('_')
  if([string]::IsNullOrWhiteSpace($safe)){ $safe='root' }
  $job="ocr_dir_${safe}_v2"
  Write-Host "\n============================================================"
  Write-Host "OCR por pasta:" $dir "| job:" $job
  & $py src/indexacao_texto.py --fonte $dir --ocr-imagens --job-id $job --max-video-mb 50 --max-image-mb 15
  if($LASTEXITCODE -ne 0){ throw "Falha em $dir (RC=$LASTEXITCODE)" }
}
```

## Definicao de pronto
- `text_index_jobs.status = 'done'`
- `processed_count == total_count`
- Busca retorna resultados esperados, por exemplo:
```powershell
& $py src/indexacao_texto.py --buscar "Joao Conrado Vasconcelos Nogueira"
```
