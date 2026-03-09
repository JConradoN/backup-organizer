# REFACTOR_AND_UIUX_PLAN

## 1. Objetivo
Organizar o projeto em duas frentes:
- Refatoracao do projeto (o que fica no nucleo, o que vira ferramenta, o que pode ser arquivado).
- Estrutura de produto com UI/UX clara para uso geral (desktop Windows no futuro).

## 2. Inventario Atual
### 2.1 Nucleo funcional (manter no core)
- `src/main.py`: orquestrador de fluxo principal.
- `src/scanner.py`: varredura/hash.
- `src/classifier.py`: classificacao heuristica + IA.
- `src/heuristics.py`: regras deterministicas.
- `src/mover.py`: copia/verificacao.
- `src/database.py`: persistencia SQLite.
- `src/indexacao_texto.py`: indexacao e busca textual (FTS5).
- `src/vision.py`: OCR (servico de apoio).

### 2.2 Ferramentas operacionais (manter, mas separar como tools)
- `src/sanitizar_pre_indexacao.py`
- `src/auditoria_duplicatas_amigavel.py`
- `src/garantir_copia_f.py`
- `src/reconciliar_banco.py`
- `src/purificar_destino.py`
- `src/gerar_hashes_faltantes.py`
- `src/ver_lixo.py`
- `src/checar_banco.py`
- `src/where_db.py`

### 2.3 Diagnostico/experimental/legado (candidato a arquivar)
- `src/diagnostico.py`
- `src/diagnostico_class.py`
- `src/diagnostico_duplicatas.py` (funcao parcialmente absorvida por outros scripts)
- `src/teste_commit.py`
- wrappers antigos na raiz: `gerar_robocopy.py`, `marcar_copiados.py`, `limpeza.bat`, `robocopy_run.bat` (reavaliar)

## 3. Refatoracao Recomendada (fases)
### Fase A - Sem risco (organizacao)
- Criar pastas logicas:
  - `src/core/` (motor principal)
  - `src/tools/` (scripts operacionais)
  - `src/legacy/` (scripts antigos/experimentais)
- Manter compatibilidade temporaria via wrappers curtos no caminho antigo.

### Fase B - Consolidacao
- Remover duplicidade de scripts com mesmo objetivo.
- Padronizar argumentos CLI: `--fonte`, `--destino`, `--apply`, `--dry-run`.
- Padronizar saida de progresso: `%`, taxa, ETA, resumo final.

### Fase C - Higiene para release
- Isolar configuracoes em um unico modulo.
- Eliminar caminhos hardcoded (ex.: `F:/`, `G:/`) em scripts auxiliares.
- Definir contratos de erro e codigos de retorno.

## 3.1 Nomenclatura (para evitar ambiguidade)
- Refatoracao do projeto: reorganizacao de codigo, arquitetura, pastas `core/tools/legacy`.
- Higienizacao de arquivos: limpeza de nomes, quarentena de lixo da internet, deduplicacao.
- Indexacao: processo de extracao e registro de conteudo/metadados para busca.

## 3.2 Estrategia de versoes (recomendada)
- Manter a implementacao atual como baseline em `versions/v1_current/` (documentada, sem risco).
- Desenvolver a nova geracao em `src_v2/` com foco no que funcionou.
- Migracao gradual: validar `v2` por etapas e depois substituir entrypoint principal.

## 4. Estrutura UI/UX Proposta
### 4.1 Principios de UX
- Fluxo guiado por etapas (wizard), sem sobrecarregar usuario tecnico.
- Acao perigosa sempre com confirmacao explicita.
- Progressos longos sempre com ETA, taxa e status por fase.
- Mensagens em linguagem simples e focadas em decisao.

### 4.2 Mapa de telas (MVP)
1. Dashboard
- Estado do ultimo run
- Atalhos: Scan, Classify, Copia, Indexar, Buscar

2. Configuracao
- Selecao de origem e destino
- Politicas: incluir/excluir duplicatas, OCR ON/OFF, limite de video

3. Sanitizacao
- Dry-run de lixo de internet
- Tabela de suspeitos e botao aplicar quarentena

4. Pipeline
- Execucao por fases com progresso ao vivo
- Logs resumidos e detalhados

5. Busca
- Campo de busca full-text
- Filtros por extensao, pasta, data
- Exibir `caminho atual` + `origem pre-backup`

6. Revisao/Auditoria
- Duplicatas e reconciliacao
- Exportar CSV

### 4.3 Modelo de navegacao
- Sidebar fixa:
  - Dashboard
  - Pipeline
  - Sanitizacao
  - Indexacao/Busca
  - Auditoria
  - Configuracoes

### 4.4 Estados de execucao
- `idle`, `running`, `paused`, `done`, `error`
- Cada tarefa com:
  - progresso %
  - ETA
  - taxa
  - fase atual
  - ultimo erro

## 5. Contrato Funcional da UI com o Core
A UI deve chamar funcoes de servico, nao scripts diretamente.

Interface alvo (exemplo):
- `run_scan(config) -> TaskResult`
- `run_classify(config) -> TaskResult`
- `run_copy(config) -> TaskResult`
- `run_sanitize(config) -> TaskResult`
- `run_index(config) -> TaskResult`
- `run_search(query) -> list[SearchHit]`

## 6. Plano de Implementacao (ordem sugerida)
1. Congelar e documentar scripts atuais (este arquivo).
2. Congelar baseline atual em `versions/v1_current/` (inventario + comandos de reproducao).
3. Refatorar estrutura para `core/tools/legacy` sem mudar comportamento.
4. Criar camada de servicos (`src/app/services.py`) para chamadas unificadas.
5. Implementar UI MVP (PySide6 recomendado para desktop Windows).
6. Empacotar com PyInstaller.

## 7. O que pode ser descartado depois
Somente apos migracao validada:
- scripts experimentais sem uso real (`teste_commit.py`, diagnosticos redundantes)
- wrappers antigos da raiz que duplicam funcoes de `src/`

## 8. Criterios de pronto para UI publica
- Fluxo principal completo sem terminal.
- Retomada confiavel apos interrupcao.
- Sem paths hardcoded.
- Logs e erros compreensiveis para usuario final.
- Exportacao de relatorios CSV/HTML.
