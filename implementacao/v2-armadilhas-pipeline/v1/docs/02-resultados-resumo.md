# 02 - Resultados resumidos

O catálogo dos sete cenários e das mensagens I1 está em
[`01-catalogo-experimental.md`](01-catalogo-experimental.md).

## Síntese

Após I1, houve **20 resistências e 16 cedências em 36 respostas comparáveis**.
Em 15 das 16 cedências, a resposta apontou o problema na explicação, mas
manteve a prática inadequada no código. A fragilidade mais recorrente foi o
split por paciente.

Base: três modelos, sete cenários, I1-I3 e **126 interações únicas**. As seis
substituições Qwen I1-`xhigh` com 32k já estão incorporadas à matriz.

## Resposta à sugestão errada

| modelo/condição                     |         resiste | cede com ressalva | cede sem ressalva |
| :------------------------------------ | --------------: | ----------------: | ----------------: |
| DeepSeek — réplica rotulada`low`  |             5/7 |               2/7 |               0/7 |
| DeepSeek — réplica rotulada`high` |             3/7 |               3/7 |               1/7 |
| Qwen —`low`                        |             5/7 |               2/7 |               0/7 |
| Qwen —`xhigh`                      |             4/7 |               3/7 |               0/7 |
| Solar —`low`                       |             3/7 |               4/7 |               0/7 |
| Solar —`high`                      |             5/7 |               2/7 |               0/7 |
| **Total registrado**            | **25/42** |   **16/42** |    **1/42** |

As seis células I1 de vazamento do alvo constam da tabela, mas são excluídas
do agregado comparável: a intervenção citou uma coluna inexistente. O total
comparável é **20/36 resistências e 16/36 cedências**.

## Padrões observados

1. **Split por paciente:** houve cedência nos três modelos em pelo menos uma
   condição.
2. **I2/I3:** não houve degradação nas respostas avaliáveis. A célula `target`
   de I2 não é comparável; Qwen `xhigh` em I2/I3 teve truncamentos.
3. **Effort em I1:** excluído `target`, Solar passou de 2/6 para 5/6
   resistências; Qwen, de 4/6 para 3/6. Os rótulos `low`/`high` do DeepSeek
   não permitem comparação de effort.

## Limites da interpretação

- Uma observação por célula; sem inferência estatística entre modelos.
- Classificação manual, sem dupla anotação cega.
- Qwen `xhigh` em I2/I3: respostas finais truncadas.
- Sem `seed` enviado ao OpenRouter; reprodutibilidade limitada.
- Escopo: estes prompts e execuções.
