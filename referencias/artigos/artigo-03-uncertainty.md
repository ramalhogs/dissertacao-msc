# Can LLMs Express Their Uncertainty?

## Referência

Lin, Hilton, Evans et al. ICLR, 2024.

## Pergunta

O artigo investiga se LLMs conseguem informar a probabilidade de suas respostas estarem corretas e se essa confiança é calibrada.

## Métodos comparados

- **Confiança verbalizada:** o modelo declara uma probabilidade junto com a resposta.
- **Probabilidade de tokens:** usa os *logits* do modelo, quando disponíveis.
- **Consistência entre amostras:** estima a confiança pela frequência de respostas semanticamente equivalentes.

## Achados

- Os modelos podem declarar alta confiança em respostas incorretas.
- Exemplos *few-shot* calibrados melhoram a confiança verbalizada.
- A calibração piora diante de perguntas enganosas ou sugestões incorretas.
- A confiança verbalizada é útil em APIs sem acesso aos *logits*, mas precisa de validação externa.

## Métricas

- **Expected Calibration Error (ECE):** diferença entre confiança e acurácia em faixas de probabilidade.
- **Brier Score:** perda quadrática entre a probabilidade prevista $p$ e o resultado $y \in \{0,1\}$.

$$
\text{Brier Score} = \frac{1}{N} \sum_{i=1}^N (p_i - y_i)^2
$$

- **AUROC:** capacidade da confiança de separar respostas corretas e incorretas.

## Relação com o projeto

ECE e Brier Score podem medir se a confiança acompanha a correção funcional do código. Também interessa observar como essas métricas mudam após dúvida, sugestão incorreta ou correção válida do usuário.
