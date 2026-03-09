# RESUMO_EXPLICATIVO_TECNICO

## 1. Objetivo deste documento
Explicar para um tecnico de TI o que cada etapa do sistema faz, do scan inicial ate busca textual, com foco em operacao real, seguranca e rastreabilidade.

## 2. Visao geral do sistema
O projeto `backup-organizer` organiza acervo de arquivos em tres trilhas principais:

1. Pipeline de organizacao de backup (Scan -> Classify -> Copy-First)
2. Indexacao textual (FTS5 + OCR opcional)
3. Auditoria/operacao (monitoramento, conciliacao, sanitizacao)

Banco principal: `backup_organizer.db`

Componentes principais:
- `src/main.py`: orquestrador do pipeline
- `src/scanner.py`: varredura e fingerprint dos arquivos
- `src/classifier.py`: decisao util/lixo/ambiguo com heuristica + IA
- `src/mover.py`: copia segura para destino (copy-first)
- `src/indexacao_texto.py`: indexacao e busca full-text
- `src/vision.py`: OCR local para imagens
- `src/database.py`: persistencia SQLite

## 3. Etapas do pipeline principal

### 3.1 Fase 1 - Scan (`src/scanner.py`)
Objetivo: cadastrar arquivos de origem no banco, com metadados e hash quando aplicavel.

O que faz tecnicamente:
1. Inicializa banco e carrega cache de arquivos ja conhecidos.
2. Percorre diretorios da origem.
3. Classifica extensoes em grupos (lixo direto, sem hash, com hash).
4. Calcula hash SHA-256 quando necessario:
- Arquivos grandes podem usar fast hash (inicio + fim + tamanho) para acelerar.
5. Insere em lote no SQLite (`BATCH_SIZE`) para reduzir custo de I/O.
6. Marca duplicidade por combinacao hash+tamanho no fluxo de scan.

Resultado no banco (`files`):
- `caminho_original`, `nome`, `extensao`, `tamanho`, `hash_sha256`, datas, `status='pendente'`.

### 3.2 Fase 2 - Classificacao (`src/classifier.py`)
Objetivo: decidir destino logico do arquivo (`util`, `lixo`, `ambiguo`).

O que faz tecnicamente:
1. Busca pendentes (`status='pendente'`).
2. Aplica heuristica local (`src/heuristics.py`) primeiro (mais rapido e deterministico).
3. Se ambiguo:
- para imagem, tenta OCR local (`vision.py`) para enriquecer contexto;
- envia lote para IA local (Ollama) quando necessario.
4. Salva decisao no banco com trilha de auditoria:
- `decisao`, `categoria`, `metodo` (heuristica/ia), `confianca`, `motivo`, `caminho_destino`.
5. Atualiza `status='processado'` para itens decididos.

### 3.3 Fase 3 - Copia (`src/mover.py`)
Objetivo: copiar arquivos classificados sem apagar origem automaticamente.

O que faz tecnicamente:
1. Busca registros `processado` com `decisao` util/ambiguo e `caminho_destino`.
2. Copia com `copy2` preservando metadados.
3. Evita sobrescrita por renomeacao em conflito.
4. Verifica integridade:
- se existe hash no banco, calcula hash no destino e compara;
- sem hash (ex.: alguns midia), valida por tamanho.
5. Se validado, marca `status='copiado'`.
6. Se falhar, remove destino parcial e marca `status='erro'`.

Garantia operacional:
- Modelo copy-first: o sistema nao deleta origem automaticamente.

## 4. Indexacao textual e OCR (`src/indexacao_texto.py`)
Objetivo: permitir busca por conteudo textual (texto nativo + OCR), nao apenas por nome de arquivo.

O que faz tecnicamente:
1. Cria/atualiza estrutura FTS5:
- `text_index`
- `text_index_fts`
- `text_index_jobs` (checkpoint por job)
2. Descobre candidatos por extensao suportada:
- texto, PDF, DOCX, imagem (com `--ocr-imagens`), videos grandes como metadado.
3. Extrai conteudo por origem:
- `texto`, `pdf`, `docx`, `ocr`, `metadata`.
4. Atualiza indice incrementalmente (skip quando tamanho+mtime nao mudaram).
5. Mantem checkpoint por `job_id`:
- `processed_count`, `total_count`, `last_path_norm`, `status`.
6. Possui lock por `job_id` para evitar execucoes concorrentes independentes.

Busca:
- `--buscar "termo"`
- filtros opcionais por pasta, extensao e periodo.

## 5. Banco de dados e rastreabilidade

### 5.1 Tabela `files`
Campos relevantes para operacao:
- Identidade: `caminho_original`, `nome`, `extensao`
- Integridade: `hash_sha256`, `tamanho`
- Decisao: `decisao`, `categoria`, `metodo`, `confianca`, `motivo`
- Destino: `caminho_destino`
- Estado: `status` (`pendente`, `processado`, `copiado`, `erro`)

### 5.2 Tabelas de texto
- `text_index`: documento textual consolidado por caminho
- `text_index_fts`: indice full-text
- `text_index_jobs`: checkpoint e progresso de indexacao

## 6. Interface de busca (planejada)
Havera interface para busca de arquivos por:
1. Tags tecnicas (categoria, decisao, extensao, pasta, periodo)
2. Texto indexado (conteudo extraido de documento/OCR)
3. Texto enriquecido por IA (descricoes/indicadores gerados no processo)

Referencias de produto/UI:
- `docs/SANITIZATION_AND_UIUX_PLAN.md` (mapa de telas e contratos)

Escopo esperado da tela de busca:
- campo de busca full-text
- filtros por tag
- lista de resultados com caminho atual e origem
- ordenacao por relevancia/data

## 7. Exemplo pratico de busca e resultado

Comando de busca:
```powershell
C:/Users/morph/dev-tools/backup-organizer/venv/Scripts/python.exe src/indexacao_texto.py --buscar "Joao Conrado Vasconcelos Nogueira"
```

Formato esperado de saida (exemplo):
```text
Busca por: Joao Conrado Vasconcelos Nogueira
============================================================
Arquivo : F:\fotos\2023\documento_123.jpg
Origem  : G:\backup_antigo\fotos\documento_123.jpg
Ext     : .jpg | Origem: ocr
Trecho  : ... [Joao Conrado Vasconcelos Nogueira] ...
Indexado: 2026-03-08T12:34:56
------------------------------------------------------------
```

Interpretacao tecnica do resultado:
- `Arquivo`: local atual no destino indexado
- `Origem`: referencia para caminho pre-backup (quando mapeado)
- `Origem: ocr`: texto veio de OCR, nao de texto nativo
- `Trecho`: snippet retornado pelo FTS5 com highlight do termo

## 8. Comandos operacionais recomendados

Pipeline completo (simulacao):
```powershell
C:/.../venv/Scripts/python.exe src/main.py --fonte G:/ --destino F:/ --dry-run
```

Pipeline completo (execucao):
```powershell
C:/.../venv/Scripts/python.exe src/main.py --fonte G:/ --destino F:/
```

Indexacao OCR com checkpoint:
```powershell
C:/.../venv/Scripts/python.exe src/indexacao_texto.py --fonte F:/fotos --ocr-imagens --job-id ocr_dir_fotos_v2 --max-video-mb 50 --max-image-mb 15
```

Busca textual:
```powershell
C:/.../venv/Scripts/python.exe src/indexacao_texto.py --buscar "nota fiscal"
```

## 9. Observacoes finais para TI
1. O sistema prioriza seguranca operacional (copy-first, sem delete automatico).
2. A performance depende de I/O de disco, tipo de arquivo e janela de checkpoint.
3. ETA de OCR oscila por natureza da carga e deve ser tratado como estimativa.
4. Para retomada confiavel, manter sempre o mesmo `job_id`.
