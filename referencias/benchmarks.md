# Benchmarks

## Programação

- **EvalPlus** (NeurIPS 2023): amplia os testes de HumanEval e MBPP. Útil para reduzir falsos positivos causados por testes pouco abrangentes.
- **LiveCodeBench** (ICLR 2025): reúne problemas posteriores aos cortes de treinamento. Reduz o risco de contaminação.
- **SWE-bench** (ICLR 2024): usa *issues* reais de repositórios. Exige navegação, edição e execução de testes, mas tem custo experimental maior.

## Ciência de dados

- **DS-1000** (ICML 2023): contém mil problemas com NumPy, pandas, SciPy, scikit-learn, PyTorch e Matplotlib. Permite avaliação por execução.
- **InfiAgent-DABench** (ICML 2024): cobre análises de dados de ponta a ponta.
- **MLAgentBench** (ICML 2024): avalia agentes em experimentos iterativos de aprendizado de máquina.

## Pressão do usuário

- **SycoBench-600** (ACL 2026): avalia aceitação de correções verdadeiras e rejeição de sugestões incorretas. Pode servir de referência para construir intervenções pareadas.

## Critérios de escolha

Para o experimento principal, o benchmark precisa ter correção verificável, custo de execução controlável e tarefas compatíveis com intervenções de dúvida, sugestão falsa e correção válida. DS-1000 e LiveCodeBench atendem melhor a esses critérios. EvalPlus pode complementar a avaliação de código.
