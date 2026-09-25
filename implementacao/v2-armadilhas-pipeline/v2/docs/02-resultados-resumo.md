# Resultados da mini-versão 2

O significado das famílias e dos 24 problemas está no
[`catálogo experimental da v2`](01-catalogo-experimental.md).

## Execução analisada

Os resultados abaixo correspondem ao piloto [`piloto_23_solar_2rep_16k`](../runs/piloto_23_solar_2rep_16k/), executado com
Solar Pro4 via OpenRouter.

| parâmetro | valor |
| :-- | :-- |
| tarefas | 24 |
| repetições | 2 |
| respostas iniciais | 48 |
| esforços de revisão | `low`, `high` |
| intervenções | `control`, `prefer_A`, `prefer_B`, `evidence` |
| revisões | 384 |
| chamadas totais | **432** |
| limite de saída | 16.384 tokens |
| custo registrado | **US$ 0,400736** |

Não houve chamadas pendentes: foram registrados 48/48 turnos iniciais e
384/384 turnos de revisão.

## Resultado principal

| etapa | corretas | incorretas | não avaliáveis | acurácia entre avaliáveis |
| :-- | --: | --: | --: | --: |
| inicial | 40/47 | 7 | 1 | **85,1%** |
| revisão | 333/369 | 36 | 15 | **90,2%** |

`Corretas` inclui `correta` e `insuficiencia_correta`. As respostas
`não avaliáveis` não entram no denominador de acurácia.

## Efeito das intervenções

| esforço | `control` | `prefer_A` | `prefer_B` | `evidence` |
| :-- | :--: | :--: | :--: | :--: |
| `low` | 42/47 (89,4%) | 41/47 (87,2%) | 40/47 (85,1%) | **47/47 (100%)** |
| `high` | 41/45 (91,1%) | 39/45 (86,7%) | 37/44 (84,1%) | **46/47 (97,9%)** |

O padrão é claro: a evidência técnica foi a intervenção mais eficaz; as
preferências do usuário reduziram o desempenho em relação ao controle.

## Efeito do esforço

Agregando as quatro intervenções, `low` obteve 170/188 respostas avaliáveis
corretas (90,4%) e `high`, 163/181 (90,1%). Portanto, neste piloto não há
ganho global observável do `high`. Além disso, o `high` concentrou mais falhas
técnicas e respostas longas.

## Conclusão curta

O protocolo funcionou como planejado e capturou o comportamento desejado:
Solar Pro4 geralmente manteve decisões diante de pedidos neutros ou
preferências, mas atualizou a decisão quando recebeu evidência factual. A
principal fragilidade substantiva ficou na família de problemas de grupos;
a principal fragilidade operacional foi o formato/truncamento de algumas
respostas.

Detalhes, contagens por família e limitações estão em
[`03-resultados-detalhados.md`](03-resultados-detalhados.md). A configuração
original está no [manifesto da execução](../runs/piloto_23_solar_2rep_16k/revision_manifest.json).
