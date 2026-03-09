# 🤖 Guia para Continuar com VS Code + GitHub Copilot

Use este arquivo como referência ao continuar o desenvolvimento no VS Code.
Cole os prompts abaixo diretamente no Copilot Chat.

---

## 📋 Contexto para o Copilot

Cole no início de qualquer sessão:

```
Este é o projeto backup-organizer, um sistema Python para organizar HDs antigos.
Arquitetura: scanner.py → classifier.py (heuristics.py + IA Ollama) → mover.py
Banco: SQLite via database.py
Princípio: Copy-First, nunca deletar automaticamente.
```

---

## 🧪 Testes Unitários (tests/)

### Prompt para gerar testes do heuristics.py:
```
Gere testes unitários com pytest para o arquivo heuristics.py.
Teste os seguintes cenários:
- Extensão .jpg → deve retornar status='util', categoria='fotos'
- Extensão .dll → deve retornar status='lixo'
- Arquivo sem extensão → deve retornar status='ambiguo'
- Extensão .xyz desconhecida → deve retornar status='ia_necessaria'
- Arquivo com nome 'thumbs.db' → deve retornar status='lixo'
- Arquivo pequeno < 1KB com extensão desconhecida → deve retornar status='lixo'
```

### Prompt para gerar testes do database.py:
```
Gere testes unitários com pytest para database.py.
Use um banco SQLite em memória (':memory:') para os testes.
Teste: init_db(), inserir_arquivo(), atualizar_decisao(), hash_ja_existe(), resumo().
```

### Prompt para gerar testes do mover.py:
```
Gere testes unitários para mover.py usando tmp_path do pytest.
Teste: verificar_copia() com arquivo válido, copiar_arquivo() com conflito de nome.
```

---

## 📈 Fase 4 — Interface CLI com Rich (roadmap)

### Prompt:
```
Adicione uma interface visual ao main.py usando a biblioteca Rich.
Substitua o tqdm por rich.progress.Progress com colunas personalizadas.
Adicione um painel de resumo final com rich.table.Table mostrando
decisão, total e percentual de cada categoria.
```

---

## 📊 Fase 5 — Relatório HTML

### Prompt:
```
Crie um arquivo report.py que leia o banco SQLite backup_organizer.db
e gere um relatório HTML com:
- Resumo geral (total, úteis, lixo, ambíguos, duplicatas)
- Gráfico de pizza por categoria (use apenas HTML/CSS inline, sem JS externo)
- Tabela de erros com caminho e motivo
- Lista dos 20 maiores arquivos encontrados
Salvar em logs/relatorio_AAAAMM.html
```

---

## 🔄 Fase 6 — Feedback e ajuste de heurísticas

### Prompt:
```
Crie um arquivo feedback.py com uma função corrigir_decisao(caminho_original, nova_decisao).
Ela deve atualizar o banco SQLite e salvar um log de correções em logs/feedback.jsonl
para análise futura de padrões e ajuste automático das heurísticas.
```

---

## 🐛 Debugging comum

### Ollama não responde:
```
O classificador retorna 'ambiguo' com motivo 'Erro na IA: Connection refused'.
Verifique se o Ollama está rodando: tasklist | findstr ollama
Se não estiver, abra o Ollama no Windows antes de rodar o script.
```

### Performance lenta no USB:
```
Para melhorar performance de leitura em HDs USB, adicione processamento
paralelo ao scanner.py usando concurrent.futures.ThreadPoolExecutor
com max_workers=4. Atenção: manter thread-safety no SQLite com locks.
```
