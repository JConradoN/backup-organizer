# v1_current (Baseline)

Este diretorio representa a baseline funcional atual do projeto.

## Objetivo
Preservar o conhecimento e os comandos da versao atual antes da evolucao para `src_v2`.

## Fluxos validados
- Scan: `src/scanner.py`
- Classificacao: `src/classifier.py`
- Copia copy-first: `src/mover.py`
- Indexacao e busca: `src/indexacao_texto.py`
- Higienizacao pre-indexacao: `src/sanitizar_pre_indexacao.py`

## Comandos principais (v1)
```bash
python src/main.py --fonte G:\ --destino F:\ --dry-run
python src/main.py --fonte G:\ --destino F:\
python src/indexacao_texto.py --fonte F:/ --max-video-mb 50
python src/indexacao_texto.py --buscar "conrado" --limite 10
```

## Observacoes
- Evitar alterar scripts legados sem necessidade.
- Toda evolucao nova deve priorizar `src_v2/`.
