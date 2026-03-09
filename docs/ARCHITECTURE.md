# 🏗️ Decisões de Arquitetura — Backup Organizer

## Por que Python no Windows (não WSL2)?

Os HDs USB são montados pelo Windows (`D:\`, `E:\`). O WSL2 acessa drives USB via
`/mnt/d/` com overhead significativo em operações de I/O massivo. Para processar
20.000+ arquivos/hora, rodar direto no Windows é 3-5x mais rápido para leitura USB.

## Por que SQLite?

- Zero configuração, zero servidor
- Suporta WAL mode para escrita concorrente
- Permite retomada após falha (estado persistido por arquivo)
- Portável: o `.db` pode ser aberto no DB Browser for SQLite para auditoria visual

## Por que Ollama (não OpenAI API)?

- Custo zero — sem taxa por token
- Privacidade — dados nunca saem da máquina local
- O PRD especifica < 10% de uso da IA, então latência local é aceitável
- GTX 1650 (4GB VRAM) consegue rodar `llama3.1` com performance adequada

## Por que Copy-First e não Move?

Regra de ouro para operações em dados legados:
**nunca destrua o original antes de confirmar a cópia.**
O usuário revisa os logs e deleta manualmente — dando controle total ao humano.

## Por que heurísticas antes da IA?

Custo computacional e tempo. Extensões como `.jpg`, `.dll` e `.tmp` têm
classificação óbvia e determinística. Chamar uma LLM para classificar
`foto.jpg` seria desperdício. A IA é reservada para casos genuinamente ambíguos.

## Estrutura temporal (Ano/Mês)

Evita pastas com milhares de arquivos que travam o Explorer do Windows.
Usa `data_criacao` do arquivo como referência. Se indisponível, usa `0000/00`.
