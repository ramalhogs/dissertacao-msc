# Towards Understanding Sycophancy in Language Models

## Referência

Sharma et al. ICLR, 2024.

## Conceito

*Sycophancy* é a tendência de um modelo adaptar a resposta às crenças ou preferências do usuário, mesmo quando isso reduz a correção factual.

## Avaliações do artigo

O estudo testa modelos como Claude, GPT e LLaMA em quatro situações:

1. **Feedback:** avaliações ficam mais favoráveis quando o usuário declara gostar do texto ou ser seu autor.
2. **Are you sure?:** o modelo troca uma resposta correta após o usuário expressar dúvida.
3. **Answer:** uma sugestão incorreta no enunciado reduz a acurácia da resposta.
4. **Mimicry:** o modelo reproduz ou aceita uma premissa factual incorreta apresentada pelo usuário.

## Explicação proposta

O artigo relaciona o comportamento ao treinamento por preferência humana. Avaliadores podem favorecer respostas que concordam com suas posições, sobretudo quando a tarefa é difícil de verificar. A otimização por RLHF pode incorporar esse viés.

## Relação com o projeto

O protocolo precisa distinguir dois comportamentos:

- aceitar uma correção válida;
- rejeitar uma sugestão incorreta.

A métrica de seletividade de correção atende a essa distinção. A execução de testes também reduz a dependência de avaliações subjetivas do próprio modelo ou do usuário.
