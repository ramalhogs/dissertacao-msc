# Inferência estatística e modelagem

## Ideia central

O estudo não deve se limitar a ranquear modelos — por exemplo, afirmar que um modelo teve 85% de acerto e outro 82%. A proposta é estimar como diferentes fatores alteram a probabilidade de uma resposta estar correta e quantificar a incerteza dessas estimativas.

Para cada observação, pode-se definir:

$$
Y_i = 1 \quad \text{se a solução atende ao critério objetivo de correção, e } 0 \text{ caso contrário.}
$$

Uma formulação inicial para a probabilidade de acerto é:

$$
P(Y_i=1) = f(\text{modelo},\text{tarefa},\text{dificuldade},\text{intervenção},\text{confiança},\text{turnos},\text{arquitetura}).
$$

Assim, o foco passa a ser, por exemplo, estimar o efeito da sugestão incorreta do usuário sobre a probabilidade de correção, e não apenas comparar médias entre modelos.

## Modelo estatístico candidato

Como o desfecho principal é binário, o ponto de partida pode ser uma regressão logística. Como as mesmas tarefas podem ser aplicadas a vários modelos e sob várias condições, é importante considerar a dependência entre observações. Um modelo hierárquico ou logístico de efeitos mistos pode incluir:

- efeitos fixos para modelo, tipo de intervenção, arquitetura, dificuldade, temperatura e número de turnos;
- efeitos aleatórios para tarefa/questão e, se necessário, para modelo;
- interação entre modelo e intervenção;
- interação entre intervenção e arquitetura de mitigação.

Uma forma simplificada seria:

$$
\operatorname{logit}\big(P(Y_i=1)\big) = \beta_0 + \beta_1\text{Intervenção}_i + \beta_2\text{Arquitetura}_i + \beta_3(\text{Intervenção}\times\text{Arquitetura})_i + u_{\text{tarefa}} + v_{\text{modelo}}.
$$

Os coeficientes devem ser convertidos em probabilidades previstas, diferenças de risco ou razões de chances, que são mais interpretáveis no contexto da dissertação.

## Perguntas estatísticas possíveis

1. Qual é a mudança estimada na probabilidade de correção após uma intervenção incorreta?
2. A arquitetura verificadora reduz a taxa de sycophancy e o persuasion bombing?
3. O efeito da intervenção varia entre modelos ou níveis de dificuldade?
4. A confiança verbalizada prevê corretamente o acerto depois da pressão do usuário?
5. O aumento no número de turnos intensifica a perda de correção ou de calibração?

## Incerteza e robustez

Os resultados devem ser acompanhados por intervalos de confiança ou intervalos de credibilidade, tamanho de efeito e testes de hipóteses previamente definidos. Bootstrap pode ser usado como análise de robustez, especialmente para SR, PBR e CS.

Uma análise bayesiana é uma alternativa possível, sobretudo se houver poucos modelos, muitas fontes de variação ou interesse em estimar diretamente a probabilidade de que uma arquitetura tenha efeito benéfico. A escolha entre abordagem frequentista e bayesiana deve ser discutida com o orientador e mantida compatível com o tamanho e o desenho amostral.

## Cuidados metodológicos

- Definir previamente o desfecho primário e os efeitos principais, para evitar testar muitas hipóteses depois de observar os resultados.
- Distinguir significância estatística de relevância prática.
- Tratar tarefa, modelo e condição experimental como unidades diferentes do desenho, evitando erros de pseudorreplicação.
- Usar métricas pareadas quando a mesma tarefa for submetida a várias condições.
- Reportar também resultados descritivos, mas usar a inferência para sustentar as conclusões causais ou comparativas.
