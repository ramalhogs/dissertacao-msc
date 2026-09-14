# GenAI as a Power Persuader

## Referência

Randazzo, Joshi, Kellogg, Lifshitz, Dell'Acqua e Lakhani. Harvard Business School Working Paper 26-021, 2025.

## Pergunta

O estudo analisa o que acontece quando profissionais questionam respostas de um LLM durante uma tarefa analítica. A hipótese usual de *human-in-the-loop* é que o questionamento ajuda a detectar erros. O artigo mostra que o modelo também pode reagir tentando preservar a resposta inicial.

## Método

- 72 consultores do Boston Consulting Group.
- Caso de negócio fictício com dados financeiros e entrevistas.
- Plataforma baseada em GPT-4.
- Codificação qualitativa de 4.339 prompts, incluindo 132 validações diretas e 968 respostas persuasivas.

## Achados

Os participantes validaram respostas por checagem de fatos, exposição de contradições e contestação direta. Nas respostas, o modelo combinou táticas de:

- *ethos*: desculpas, reafirmação de rigor e explicações sobre o próprio esforço;
- *logos*: dados, comparações e estruturas formais;
- *pathos*: validação do usuário, espelhamento e linguagem motivacional.

Os autores chamam essa intensificação retórica de *persuasion bombing*. O resultado sugere que questionar o modelo no mesmo diálogo não garante uma revisão objetiva.

## Limitações

- Estudo qualitativo e concentrado em uma única tarefa de consultoria.
- Uso de GPT-4 em uma plataforma específica.
- Persuasão e correção factual não foram separadas por testes determinísticos.

## Relação com o projeto

O artigo motiva a avaliação quantitativa do fenômeno em programação e ciência de dados. Nesses domínios, testes de execução permitem comparar a retórica do modelo com a correção funcional. Também sustenta a separação entre o agente que responde e o mecanismo que verifica a solução.
