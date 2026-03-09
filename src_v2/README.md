# src_v2

Nova geracao do fluxo principal, com foco em simplicidade e no que funcionou.

## Arquivo principal
- `main.py`

## Principios
- Nao reescrever tudo de uma vez.
- Reusar modulos maduros de `src/` enquanto a arquitetura v2 estabiliza.
- Eliminar dependencias de scripts experimentais no entrypoint.

## Uso rapido
```bash
python src_v2/main.py --fonte G:\ --destino F:\ --dry-run
python src_v2/main.py --fonte G:\ --destino F:\ --indexar --max-video-mb 50
python src_v2/main.py --resumo
```
