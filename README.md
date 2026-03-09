# Backup Organizer

[![License: GPL v3 or later](https://img.shields.io/badge/License-GPLv3%2B-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Projeto para organizar arquivos de backups antigos com foco em seguranca operacional:

- fluxo copy-first (sem apagar automaticamente)
- deduplicacao por hash no SQLite
- sanitizacao e auditoria por scripts auxiliares
- indexacao textual (FTS5) com OCR opcional

## Estado atual

O projeto esta funcional em `src/` e possui:

- pipeline principal (`main.py`, `scanner.py`, `classifier.py`, `mover.py`)
- indexacao textual incremental (`src/indexacao_texto.py`)
- OCR por EasyOCR (`src/vision.py`)
- automacao por perfis (`src/automation_pipeline.py`)
- baseline congelada em `versions/v1_current/`
- trilha de migracao para `src_v2/`

Documentacao de apoio:

- `docs/ARCHITECTURE.md`
- `docs/AUTOMATION_STRATEGY.md`
- `docs/SANITIZATION_AND_UIUX_PLAN.md`
- `docs/PROJECT_HISTORY.md`
- `docs/PROJECT_STATUS.md`

## Estrutura relevante

```text
backup-organizer/
├── src/
│   ├── main.py
│   ├── scanner.py
│   ├── classifier.py
│   ├── mover.py
│   ├── database.py
│   ├── indexacao_texto.py
│   ├── vision.py
│   ├── sanitizar_pre_indexacao.py
│   ├── auditoria_duplicatas_amigavel.py
│   └── automation_pipeline.py
├── docs/
├── logs/
├── versions/v1_current/
├── src_v2/
├── monitor_ocr.ps1
└── backup_organizer.db
```

## Ambiente

- Sistema alvo: Windows
- Python: venv local em `venv/`
- Banco principal: `backup_organizer.db`

## Comandos principais

### Painel UI/UX operacional (recomendado)

```powershell
C:/.../venv/Scripts/python.exe -m streamlit run src/interface.py
```

O painel inclui abas de:

- instalacao/verificacao de ambiente
- configuracao de caminhos e parametros
- execucao de modulos em background com log
- navegacao de pastas
- busca textual/tags e status de jobs

Aviso operacional:

- a execucao da analise de OCR pode demorar muito tempo, de acordo com hardware, volume e tamanho dos arquivos.
- a interface possui a aba `HelpMe` com explicacao de cada elemento de tela e fluxo recomendado.

Arquivo de ajuda:

- `docs/HELPME_UI.md`

## Distribuicao para teste em outro computador

Artefatos gerados:

- `dist/BackupOrganizer_Installer.exe` (arquivo unico `.exe`)
- `dist/BackupOrganizer/` (pacote onedir alternativo)
- `dist/BackupOrganizer_Setup.exe` (instalador wizard com atalhos e desinstalacao)
- `dist/BackupOrganizerLite_Setup.exe` (instalador wizard LITE, sem OCR pesado embutido)

Geracao do instalador wizard:

```powershell
./build_setup.ps1
```

Geracao da variante LITE:

```powershell
./build_exe_lite.ps1
./build_setup_lite.ps1
```

Arquivos de build do instalador:

- `installer/BackupOrganizer.iss`
- `build_setup.ps1`
- `installer/BackupOrganizerLite.iss`
- `build_exe_lite.ps1`
- `build_setup_lite.ps1`

Como testar em outra maquina:

1. Copie `dist/BackupOrganizer_Installer.exe`.
2. Execute o arquivo `.exe` no computador de destino.
3. Na primeira execucao, o app prepara os arquivos de runtime ao lado do executavel e abre o painel Streamlit.
4. Na aba `Instalacao`, rode `Verificar ambiente`.

Opcao recomendada para usuario final (wizard):

1. Copie `dist/BackupOrganizer_Setup.exe`.
2. Execute o instalador e avance no assistente.
3. Abra o atalho "Backup Organizer" criado no menu iniciar (ou desktop, se selecionado).
4. Na aba `Instalacao`, rode `Verificar ambiente`.

Opcao recomendada para teste rapido (LITE):

1. Copie `dist/BackupOrganizerLite_Setup.exe`.
2. Execute o instalador e abra o app pelo atalho.
3. Se precisar de OCR local depois, use na aba `Instalacao` o botao `Instalar stack OCR (EasyOCR)`.

Observacoes:

- para OCR e IA local, o computador de destino deve ter ambiente compativel com EasyOCR/torch e Ollama (se desejar resumos via modelo).
- sem Ollama, o sistema pode usar fallback local para `resumo_curto`.
- o instalador pode ficar grande por incluir dependencias de OCR/IA (torch/easyocr).

Comparativo de tamanho observado:

- `BackupOrganizer_Setup.exe`: ~1.64 GB
- `BackupOrganizerLite_Setup.exe`: ~89 MB

### Pipeline principal

```powershell
C:/.../venv/Scripts/python.exe src/main.py --fonte G:/ --destino F:/ --dry-run
C:/.../venv/Scripts/python.exe src/main.py --fonte G:/ --destino F:/
```

### Indexacao e busca

```powershell
# Indexacao sem OCR (incremental)
C:/.../venv/Scripts/python.exe src/indexacao_texto.py --fonte F:/ --job-id daily_sem_ocr --max-video-mb 50

# Indexacao com OCR (pesada)
C:/.../venv/Scripts/python.exe src/indexacao_texto.py --fonte F:/fotos --ocr-imagens --job-id ocr_dir_fotos_v2 --max-video-mb 50 --max-image-mb 15

# Busca full-text
C:/.../venv/Scripts/python.exe src/indexacao_texto.py --buscar "termo"
```

### Automacao por perfil

```powershell
# plano (nao executa)
C:/.../venv/Scripts/python.exe src/automation_pipeline.py --profile daily

# executa
C:/.../venv/Scripts/python.exe src/automation_pipeline.py --profile daily --execute
```

### Monitoramento

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\monitor_ocr.ps1
```

## Notas operacionais importantes

- Use sempre o mesmo `--job-id` para retomar de checkpoint.
- Nao rode duas instancias independentes do mesmo `job-id`.
- `src/indexacao_texto.py` possui lock por job para bloquear duplicata externa.
- Em Windows/EasyOCR pode existir processo filho interno do backend, isso e esperado.

## Versoes

- `versions/v1_current/`: baseline funcional e comandos de reproducao
- `src_v2/`: nova geracao em evolucao (migracao gradual)

## Historico e handoff

- Historico consolidado: `docs/PROJECT_HISTORY.md`
- Status atual e riscos: `docs/PROJECT_STATUS.md`
- Contexto pronto para novo chat: `handoff.md`

## Licenca

Este projeto esta licenciado sob **GNU GPL v3 ou posterior (GPL-3.0-or-later)**.

- Arquivo de licenca: `LICENSE`
- SPDX: `GPL-3.0-or-later`

## Publicacao no GitHub (codigo-fonte)

Checklist recomendado antes de publicar:

1. Revisar se nenhum dado sensivel ficou no projeto (`.env`, chaves, caminhos pessoais, bancos locais).
2. Confirmar que arquivos locais pesados/sensiveis permanecem fora do git (`*.db`, `dist/`, `build/`, `venv/`).
3. Validar README e documentacao de uso/licenca.

Exemplo de publicacao (novo repositorio):

```powershell
git init
git add .
git commit -m "feat: release inicial sob GPL-3.0-or-later"
git branch -M main
git remote add origin https://github.com/<seu-usuario>/backup-organizer.git
git push -u origin main
```

Observacao sobre distribuicao sob GPL:

- ao distribuir binarios/instaladores, mantenha o codigo-fonte correspondente acessivel no repositorio publico e preserve os avisos de licenca.
