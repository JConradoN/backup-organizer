# PROJECT_HISTORY

## Objetivo deste arquivo
Registrar a evolucao pratica do projeto, com foco em decisoes tecnicas, problemas reais e correcoes aplicadas.

## Linha do tempo resumida

1. Base funcional consolidada
- Pipeline principal em `src/main.py` com fases de scan, classificacao e copy-first.
- Persistencia em SQLite (`src/database.py`, tabela `files`).

2. Correcoes operacionais de scripts
- Correcao de erro de sintaxe em `src/contar_movidos.py`.
- Ajuste de semantica de duplicatas: uso de `motivo='duplicata_removida'` em vez de tentar gravar status invalido para o schema.

3. Reconciliacao de banco e caminhos
- Evolucao de `src/diagnostico_duplicatas.py` para reconciliar caminhos higienizados e atualizar destino/duplicatas.

4. Auditoria de duplicatas em `F:/`
- Criados scripts e relatorios para validar que duplicatas possuem copia valida fora de `duplicatas_detectadas`.
- Eliminacao de falso positivo por prefixo de hash: validacao passou para hash completo.

5. Garantia de copia valida
- Criado `src/garantir_copia_f.py` e depois reescrito para criterio robusto por hash exato.

6. Indexacao textual (FTS5)
- Criado `src/indexacao_texto.py` com:
  - texto plano, PDF, DOCX
  - OCR opcional
  - busca com filtros (`--pasta`, `--ext`, `--desde`, `--ate`)
  - checkpoint por `job_id`
  - progresso periodico com taxa e ETA
  - metadados para videos grandes
- Adicao de dependencias opcionais no `requirements.txt` (`pypdf`, `python-docx`).

7. OCR e Unicode no Windows
- `src/vision.py` atualizado para leitura de paths Unicode com `np.fromfile + cv2.imdecode`.
- Testes com nomes acentuados confirmaram estabilidade.

8. Automacao
- Criado `src/automation_pipeline.py` com perfis:
  - `daily`
  - `nightly-ocr`
  - `cleanup-apply`
- Estrategia documentada em `docs/AUTOMATION_STRATEGY.md`.

9. Planejamento de produto e refatoracao
- Criado `docs/SANITIZATION_AND_UIUX_PLAN.md` (plano de migracao e UI/UX).
- Baseline em `versions/v1_current/` e inicio de `src_v2/`.

10. Ajustes recentes de estabilidade em OCR
- Reuso de instancia OCR no processo para reduzir overhead.
- Melhorias de logs/ruido OpenCV.
- Lock por `job_id` em `src/indexacao_texto.py` para bloquear duplicatas externas.
- Correcao de metrica de progresso apos resume: taxa/ETA agora usam itens processados na execucao atual.

## O que funcionou bem
- Checkpoint por `job_id` para retomada.
- Validacao por hash completo para duplicatas.
- Fluxo copy-first (seguranca operacional).
- OCR com suporte a path Unicode no Windows.

## O que falhou ou gerou ruido
- Execucoes concorrentes do mesmo `job_id` prejudicaram taxa/ETA.
- Metrica de progresso inicialmente inflada apos resume (corrigida).
- OCR em lote grande e sensivel a variacao de I/O em disco USB.

## Decisoes que devem ser mantidas
- Nao apagar automaticamente em automacao.
- Preferir dry-run antes de apply em fluxos sensiveis.
- Usar lock por `job_id` para evitar corrida de processo.
- Usar monitoramento por checkpoint em vez de confiar apenas em % de GPU.
