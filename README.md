# Descrição do Funcionamento do Código

Este projeto tem como foco demonstrar a eficiência do uso de índices em um banco de dados grande, utilizando o conjunto de dados do auxílio emergencial, disponível no [Brasil.io](https://brasil.io/dataset/govbr/auxilio_emergencial/), que possui aproximadamente 30GB.

## Estrutura do Código

1. **Banco de Dados e Estruturação:**
   - O banco de dados contendo o auxílio emergencial é carregado, estruturado e armazenado utilizando PostgreSQL.
   - São aplicadas operações de criação de índices em colunas estratégicas, permitindo que as consultas sejam otimizadas.
   - O objetivo principal é comparar o tempo de execução de consultas com e sem o uso de índices.

2. **Interface Gráfica em Python (GUI):**
   - A aplicação possui uma interface gráfica construída em Python, utilizando bibliotecas como `IPywidgets, que permite ao usuário executar e comparar as consultas de forma interativa.
   - O usuário pode selecionar diferentes tipos de consultas (com ou sem índices) e visualizar o tempo de resposta de cada uma diretamente na interface.
   - Gráficos ou indicadores de desempenho são exibidos para ilustrar a diferença de tempo entre as abordagens.

3. **Consultas**
   - As consultas selecionadas envolvem diferentes critérios de busca, como busca por CPF, município ou estado.
   - A consulta é executada com índices aplicados e o tempo de execução é registrado
   - A aplicação exibe os resultados, evidenciando o tempo de execução de índices.

4. **Conclusão:**
   - A partir dos dados e do tempo de execução exibidos, o usuário pode concluir a importância de criar índices para consultas eficientes em grandes bases de dados, como o auxílio emergencial, onde a diferença no tempo de resposta pode ser significativa, especialmente em operações frequentes ou em sistemas críticos.
