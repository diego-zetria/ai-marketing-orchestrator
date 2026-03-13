# PyMuPDF4LLM - PDF Text Extraction

## Resumo

| Campo | Valor |
|---|---|
| **Biblioteca** | [PyMuPDF4LLM](https://github.com/pymupdf/RAG) |
| **Licenca** | AGPL-3.0 (server-side OK) |
| **Mantida por** | Artifex Software |
| **Versao minima** | `>=0.0.17` |
| **Adicionada em** | 2026-03-10 (substituiu Docling) |
| **Usada em** | `src/bot/pdf_extractor.py` |

## Por que PyMuPDF4LLM?

- Converte PDF para **Markdown otimizado para LLMs** (mesmo output que Docling)
- ~15-20 MB vs 1+ GB do Docling (inclui PyTorch, modelos HuggingFace, etc.)
- Extremamente rapido (0.12s em benchmarks)
- Suporte a tabelas, imagens, OCR opcional (Tesseract)
- Sem dependencias de sistema pesadas (removemos libgl1, libglib2.0, libxcb1, etc. do Dockerfile)
- Build Docker e startup do container significativamente mais rapidos

## Historico

Anteriormente usavamos [Docling](https://github.com/docling-project/docling) (MIT, Linux Foundation). Migramos em 2026-03-10 porque:
- Docling puxa PyTorch, HuggingFace transformers, modelos de ML
- Imagem Docker ficava pesada (1+ GB so de deps)
- Container demorava para iniciar
- Para o caso de uso do bot (briefings PDF simples), era overkill

## Como usamos

O bot recebe PDFs de briefing dos clientes via Telegram. O PyMuPDF4LLM extrai o texto como Markdown, que e enviado ao agente de IA para analise e criacao de tasks no ClickUp.

### Fluxo

```
Telegram (PDF) -> download bytes -> PyMuPDF4LLM -> Markdown -> Agno Agent -> ClickUp
```

### Codigo principal

```python
# src/bot/pdf_extractor.py

import pymupdf
import pymupdf4llm

def _extract_sync(pdf_bytes: bytes, filename: str) -> str:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    return pymupdf4llm.to_markdown(doc)
```

### Detalhes de implementacao

- **Imports lazy**: os imports ficam dentro da funcao `_extract_sync()` (nao no topo do modulo). Isso evita que a dependencia quebre a coleta de testes.
- **Async wrapper**: `_extract_sync` roda em `asyncio.to_thread()` para nao bloquear o event loop do bot.
- **Limite de tamanho**: 20MB (limite do Telegram Bot API para downloads).

## Tipos de PDF suportados

| Tipo | Suporte | Notas |
|---|---|---|
| Texto selecionavel | Sim | Caso principal dos briefings Agency |
| PDF escaneado (OCR) | Opcional | Requer Tesseract instalado |
| PDF com tabelas | Sim | PyMuPDF detecta celulas e preserva estrutura |
| PDF protegido | Nao | Requer senha - fora do escopo atual |

## Testes

Os testes mockam `_extract_sync` para evitar dependencia no ambiente de CI:

- `tests/test_pdf_extractor.py` — 6 testes unitarios
- `tests/test_handlers_pdf.py` — 7 testes do handler de documento

## Links

- Repositorio: https://github.com/pymupdf/RAG
- PyMuPDF: https://pymupdf.readthedocs.io/
- PyPI: https://pypi.org/project/pymupdf4llm/
