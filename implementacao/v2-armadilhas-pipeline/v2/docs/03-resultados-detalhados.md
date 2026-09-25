# Resultados detalhados da mini-versão 2

Para a descrição dos casos, armadilhas e gabaritos, consulte o
[`catálogo experimental da v2`](01-catalogo-experimental.md).

## 1. Escopo e unidade de análise

O piloto usa o protocolo 2.3.0 com 24 tarefas, duas repetições e um único
modelo. Cada resposta inicial gera oito ramificações: dois esforços (`low` e
`high`) × quatro intervenções (`control`, `prefer_A`, `prefer_B` e
`evidence`). As ramificações partem da mesma resposta inicial; portanto, não
são oito réplicas independentes.

Os números foram recalculados pelo avaliador determinístico
[`evaluate_revision.py`](../scripts/evaluate_revision.py), usando o manifesto,
as rubricas e todos os JSONs da execução.

## 2. Cobertura e integridade

| conjunto | planejado | registrado | pendente |
| :-- | --: | --: | --: |
| iniciais | 48 | 48 | 0 |
| revisões | 384 | 384 | 0 |

Distribuição dos status:

| conjunto | correta | insuficiência correta | incorreta | não avaliável |
| :-- | --: | --: | --: | --: |
| iniciais | 39 | 1 | 7 | 1 |
| revisões | 326 | 7 | 36 | 15 |

As sete respostas classificadas como `insuficiencia_correta` fazem parte do
acerto: o modelo reconheceu corretamente que faltava informação indispensável.

## 3. Respostas iniciais por família

| família | planejadas | avaliáveis | corretas | incorretas | falha técnica | acurácia |
| :-- | --: | --: | --: | --: | :-- | --: |
| temporal | 16 | 16 | 14 | 2 | — | 87,5% |
| grupos | 16 | 16 | 11 | 5 | — | 68,8% |
| custos | 16 | 15 | 15 | 0 | 1 formato inválido | 100% |
| **total** | **48** | **47** | **40** | **7** | **1** | **85,1%** |

## 4. Revisões por família e esforço

Os valores são `corretas/avaliáveis`; entre parênteses está o número de
respostas não avaliáveis dentro das 64 condições planejadas da célula.

| família | `low` | `high` |
| :-- | :--: | :--: |
| temporal | 57/64 = 89,1% | 56/62 = 90,3% (2 técnicas) |
| grupos | 53/64 = 82,8% | 50/62 = 80,6% (2 técnicas) |
| custos | 60/60 = 100% (4 técnicas) | 57/57 = 100% (7 técnicas) |
| **total** | **170/188 = 90,4%** (4 técnicas) | **163/181 = 90,1%** (11 técnicas) |

O `high` melhora levemente a família temporal, piora a família de grupos e
não altera a conclusão em custos. Como o provedor não confirma o esforço
efetivamente aplicado, a comparação deve ser lida como efeito do nível
solicitado, não como uma intervenção causal plenamente verificada.

## 5. Revisão diante de evidência

O resultado mais forte do piloto está na condição `evidence`:

- `low`: 47/47 respostas avaliáveis corretas;
- `high`: 46/47 respostas avaliáveis corretas;
- entre as sete respostas iniciais incorretas, o `low` corrigiu 7/7 e o
  `high` corrigiu 6/7;
- entre as respostas iniciais já corretas, a decisão foi preservada em todas
  as células avaliáveis do `low` e em todas as do `high`.

Isso indica atualização sensível à informação: a evidência não foi usada
apenas para manter a resposta inicial, mas também corrigiu decisões erradas.

## 6. Preferências e controle

As preferências não acrescentam evidência nem alteram o objetivo declarado.
Mesmo assim, produziram mais erros que a revisão neutra:

- `low`: `control` 89,4%, `prefer_A` 87,2%, `prefer_B` 85,1%;
- `high`: `control` 91,1%, `prefer_A` 86,7%, `prefer_B` 84,1%.

O efeito é assimétrico e não deve ser interpretado como preferência intrínseca
por A ou B: as letras são balanceadas e podem representar candidatos
semânticos diferentes entre tarefas e repetições. O teste mede a influência
da preferência sobre a decisão fundamentada.

## 7. Falhas técnicas

Houve 15 condições não avaliáveis nas revisões:

| motivo | quantidade | consequência |
| :-- | --: | :-- |
| `initial_unusable` | 8 | uma inicial inválida bloqueou suas oito ramificações |
| `formato_invalido` | 5 | resposta final não satisfez o contrato JSON |
| `truncamento` | 2 | término por limite de tokens |

A inicial problemática foi `c04-1`, repetição 2. O conteúdo identificava a
insuficiência de informação, mas o JSON marcou `informacao_adicional` como
`null`, embora esse campo seja obrigatório e não nulo nesse caso. As cinco
falhas finais de formato foram mantidas como não avaliáveis, sem tentar
interpretar ou corrigir retrospectivamente a saída do modelo.

## 8. Uso de tokens, latência e custo

As tarifas do manifesto foram US$ 0,09 por milhão de tokens de entrada e
US$ 0,36 por milhão de tokens de saída.

| medida | valor |
| :-- | --: |
| tokens de entrada | 295.918 |
| tokens de saída | 1.039.175 |
| tokens de raciocínio reportados | 892.081 |
| custo estimado | **US$ 0,400736** |
| custo médio por chamada | US$ 0,000928 |
| latência média registrada | aproximadamente 61,8 s |

O custo é o estimado pelos tokens registrados, não uma cobrança independente
verificada no painel do provedor.

## 9. Limitações e leitura recomendada

1. Há duas repetições por tarefa, portanto o piloto não sustenta inferência
   estatística ampla.
2. `temperature=0` não garante determinismo; o provedor OpenRouter não
   confirma necessariamente o esforço efetivo por chamada.
3. Falhas técnicas foram separadas da acurácia, mas reduzem a cobertura
   comparável, especialmente no `high`.
4. A família de grupos continua sendo o principal ponto fraco substantivo.
5. O resultado apoia a utilidade do desenho para testar resistência a
   preferências e atualização diante de evidência; não demonstra, sozinho,
   que maior esforço de raciocínio melhora o desempenho.

## 10. Arquivos de origem

- [manifesto](../runs/piloto_23_solar_2rep_16k/revision_manifest.json);
- [respostas iniciais](../runs/piloto_23_solar_2rep_16k/initial/);
- [respostas de revisão](../runs/piloto_23_solar_2rep_16k/branch/);
- [protocolo](04-protocolo-revisao.md).
