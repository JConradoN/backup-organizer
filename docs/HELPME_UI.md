# HelpMe - Backup Organizer

Este painel foi desenhado para centralizar instalacao, configuracao, execucao, busca e monitoramento.

## Fluxo recomendado (primeiro uso)

1. Abra a aba `Instalacao` e clique em `Verificar ambiente`.
2. Se faltar algo, clique em `Instalar/atualizar dependencias (pip)`.
3. Va para `Configuracao` e salve `Fonte`, `Destino`, `Job ID` e parametros.
4. Va para `Execucao` e rode primeiro um teste curto (com lote pequeno quando possivel).
5. Acompanhe progresso em `Jobs` e logs em `Logs`.
6. Consulte resultados em `Busca`.

## Aviso importante sobre OCR

A analise de OCR pode demorar muito tempo, dependendo de:

- quantidade total de arquivos
- tamanho/resolucao das imagens
- CPU/GPU disponivel
- perfil de OCR selecionado (`stable`, `balanced`, `throughput`)

Use `stable` para maior previsibilidade e `throughput` para maior velocidade quando o hardware suportar.

## Aba Inicio

- Mostra visao geral e metricas rapidas do banco.
- Indicadores uteis:
  - total de arquivos (`files`)
  - total indexado (`text_index`)
  - quantidade com resumo
  - jobs em execucao

## Aba Instalacao

- `Verificar ambiente`:
  - valida Python
  - valida banco SQLite
  - valida dependencias principais
  - valida conectividade com Ollama
- `Instalar/atualizar dependencias (pip)`:
  - roda instalacao via `requirements.txt`
- `Instalar stack OCR (EasyOCR)`:
  - instala PyTorch CPU + EasyOCR + OpenCV para habilitar OCR na variante Lite apos a instalacao
  - pode demorar varios minutos
- `Verificar Ollama`:
  - testa endpoint configurado em `Ollama URL`

## Aba Configuracao

Campos principais:

- `Fonte`: pasta principal para leitura/varredura.
- `Destino`: pasta de saida para pipeline principal.
- `Job ID`: checkpoint de execucao da indexacao.
- `OCR profile`: equilibrio entre estabilidade e throughput.
- `Max video (MB)`: limite para tratamento de videos pesados.
- `Max imagem OCR (MB)`: limite de tamanho para OCR em imagem.
- `Modelo de resumo (Ollama)` e `Ollama URL`.

Botoes:

- `Salvar configuracao`: grava em `logs/ui_config.json`.
- `Abrir no Explorer`: abre caminho atual.
- `Subir nivel`: sobe para pasta pai no navegador.
- `Usar como Fonte` / `Usar como Destino`: aplica rapidamente o caminho navegado.
- `Entrar`: entra na pasta selecionada da listagem.

## Aba Execucao

### 1) Indexacao textual / OCR

- Executa `src/indexacao_texto.py` em background.
- Opcoes:
  - `Ativar OCR`
  - `Gerar resumo IA`
  - `Reset job`
  - `Sem resume checkpoint`
- Resultado: cria log em `logs/run_indexacao_texto_*.log`.

### 2) Backfill de resumos

- Executa preenchimento de `resumo_curto` para registros ja indexados.
- `Limite (0=todos)` controla o volume por rodada.
- `Usar fallback local` gera resumo mesmo sem Ollama.

### 3) Pipeline principal

- Executa `src/main.py` em background.
- `Dry run` recomendado para validar regra sem mover/copiados finais.

## Aba Busca

### Busca Textual

- Busca FTS por `Termo`.
- Filtros:
  - extensao
  - pasta
  - faixa de data
  - texto no resumo (`Filtro no resumo`)
- Acoes por linha:
  - `Abrir`: abre arquivo no app padrao.
  - `Explorer`: localiza arquivo no Explorer.

### Busca por Tags

- Filtros por `decisao`, `categoria`, `metodo`, `extensao`, `status`.
- Acoes de abertura iguais a busca textual.

## Aba Jobs

- Mostra status atual da tabela `text_index_jobs`.
- Campos importantes:
  - `status`
  - `processed_count / total_count`
  - `updated_em`

## Aba Logs

- Exibe jobs iniciados pela UI nesta sessao.
- Mostra PID, status, codigo de saida e caminho do log.
- Permite visualizar as ultimas linhas do log selecionado.

## Aba HelpMe

- Exibe este guia.
- Atualize este arquivo sempre que adicionar novos controles.

## Dicas de operacao segura

- Evite rodar dois processos para o mesmo `Job ID` ao mesmo tempo.
- Em OCR pesado, prefira execucoes por lote e monitore consumo.
- Mantenha backups do `backup_organizer.db` antes de mudancas grandes.
