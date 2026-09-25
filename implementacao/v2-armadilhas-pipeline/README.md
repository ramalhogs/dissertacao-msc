# Armadilhas em pipelines de machine learning

O projeto contém duas mini-versões independentes. Cada uma mantém seu próprio
corpus, código, scripts, testes, documentação e resultados. Assim, os
resultados históricos não se misturam ao protocolo prospectivo.

## Mini-versão 1 — coleta histórica

Diretório: [`v1/`](v1/)

É a coleta observacional dos sete cenários clássicos de armadilhas em
pipelines, com intervenções `I1`, `I2` e `I3`.

- [`v1/docs/`](v1/docs/): catálogo experimental, desenho e relatórios históricos;
- [`v1/problems/`](v1/problems/): cenários;
- [`v1/scripts/`](v1/scripts/): coleta observacional;
- [`v1/src/`](v1/src/): cliente, orquestração e gravação;
- [`v1/runs/`](v1/runs/): runs DeepSeek, Qwen e Solar da primeira etapa;
- [`v1/tests/`](v1/tests/): reservado para testes da mini-versão 1.

## Mini-versão 2 — protocolo prospectivo

Diretório: [`v2/`](v2/)

É o teste pareado com 24 tarefas, duas repetições, dois esforços de revisão e
quatro intervenções (`control`, `prefer_A`, `prefer_B`, `evidence`). Uma
resposta inicial alimenta todas as ramificações correspondentes.

- [`v2/docs/`](v2/docs/): catálogo experimental, protocolo, resumo e relatório detalhado dos resultados;
- [`v2/problems/`](v2/problems/): 24 tarefas e rubricas;
- [`v2/scripts/`](v2/scripts/): coleta e avaliação;
- [`v2/src/`](v2/src/): cliente e lógica do protocolo;
- [`v2/runs/`](v2/runs/): resultados do piloto Solar;
- [`v2/tests/`](v2/tests/): testes automatizados do protocolo.

## Arquivos comuns

`requirements.txt`, `.env.example` e `.gitignore` permanecem na raiz porque
são infraestrutura compartilhada; os scripts procuram o `.env` nesta raiz.

```bash
cd implementacao/v2-armadilhas-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Para executar a mini-versão 1:

```bash
cd v1
python scripts/run_collection.py --help
```

Para executar a mini-versão 2:

```bash
cd v2
python scripts/run_revision.py --help
python scripts/evaluate_revision.py runs/piloto_23_solar_2rep_16k
```
