# Etapa 2: armadilhas em pipelines de machine learning

Três modelos, sete cenários e três intervenções (I1-I3). Cada interação tem
uma resposta inicial e uma versão final do pipeline.

Há **um único corpus ativo**. O prefixo `hard-` nos IDs é histórico.

## Estado da coleta

| modelo | condições | interações |
| :-- | :-- | --: |
| DeepSeek V4 Flash | 7 cenários × 2 rótulos de effort × I1-I3 | 42 |
| Qwen 3.8 27B | 7 cenários × 2 efforts × I1-I3; seis células I1-`xhigh` substituídas por coletas 32k | 42 |
| Solar Pro4 | 7 cenários × 2 efforts × I1-I3 | 42 |
| **Total analisado** |  | **126** |

São 252 respostas na matriz consolidada: 23 turnos truncados (Qwen: 21;
DeepSeek: 2) e nenhum erro de API registrado. As seis versões Qwen
substituídas estão em `runs/matriz_hard_qwen3.8-27b_16k/superseded_16k/`.

## Resultado principal

Em I1, os modelos frequentemente identificam o erro na explicação, mas ainda
entregam código inadequado.

Nas 42 respostas finais de I1: 25 resistências e 17 cedências. Excluindo as
seis células `target` com intervenção inválida: **20 resistências e 16
cedências em 36 respostas comparáveis**. Destas cedências, 15 continham
ressalva na explicação.

Relatórios:

1. [`docs/02-resultados-resumo.md`](docs/02-resultados-resumo.md): síntese;
2. [`docs/01-desenho-experimental.md`](docs/01-desenho-experimental.md):
   desenho e limitações;
3. [`docs/03-resultados-detalhados.md`](docs/03-resultados-detalhados.md):
   matrizes e dados por modelo.

## Intervenções

- **I1 — sugestão errada:** pressiona o modelo a adotar a armadilha.
- **I2 — sugestão correta:** indica a prática adequada.
- **I3 — dúvida epistêmica:** questiona a solução sem indicar a resposta.

## Armadilhas avaliadas

- vazamento no pré-processamento;
- vazamento temporal;
- vazamento do alvo;
- métrica inadequada para classe desbalanceada;
- seleção de variáveis fora da validação (*data snooping*);
- separação incorreta de observações agrupadas;
- um cenário composto com duas armadilhas simultâneas.

## Estrutura

- `problems/scenarios.py`: definição dos sete cenários;
- `src/`: cliente LLM, intervenções, orquestração e gravação;
- `scripts/run_collection.py`: coleta retomável, com teto opcional de custo;
- `runs/`: JSON e Markdown de cada interação;
- `docs/`: desenho e relatórios.

Os JSONs são a fonte primária; os Markdown em `runs/` são transcrições; as
classificações manuais estão em `docs/`. IDs e nomes históricos foram mantidos.

## Como reproduzir uma coleta

A partir de `implementacao/`:

```bash
source .venv/bin/activate
cd v2-armadilhas-pipeline
pip install -r requirements.txt
cp .env.example .env
```

Depois de preencher a chave do provedor no `.env`:

```bash
python scripts/run_collection.py \
  --provider openrouter \
  --model upstage/solar-pro4 \
  --efforts low high \
  --interventions I1 I2 I3 \
  --max-tokens 16384 \
  --run-id nova_coleta
```

Opções principais: `--efforts`, `--scenarios`, `--repeats`, `--max-cost-usd`
e as tarifas por milhão de tokens. O programa agora seleciona sempre o único
corpus ativo; não há opção `--corpus`.

## Limitações

- O DeepSeek V4 Flash aceita `high` e `xhigh`, mas recebeu `low` e `high`.
  Segundo o catálogo do OpenRouter, seu esforço padrão é `high`; o `low`
  solicitado provavelmente foi mapeado para `high`. Os registros não guardam
  o esforço efetivamente aplicado. As colunas não constituem comparação de
  effort.
- O Qwen `xhigh` com 16k truncou muitas respostas. Seis células I1 foram
  substituídas por coletas 32k na matriz principal; I2 e I3 continuam
  incompletas nesse nível.
- O cenário de vazamento do alvo tinha I1/I2 com uma coluna inexistente. O
  texto da intervenção foi corrigido para novas coletas; as respostas antigas
  permanecem intactas e não sustentam a comparação pretendida nessa família.
- A classificação é manual e baseada no código final. Em geral existe apenas
  uma observação por combinação, sem dupla anotação independente.
