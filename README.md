# Descrição do Funcionamento do Código

Este projeto tem como foco demonstrar a eficiência do uso de índices em um banco de dados grande, utilizando o conjunto de dados do auxílio emergencial, disponível no [Brasil.io](https://brasil.io/dataset/govbr/auxilio_emergencial/), que possui aproximadamente 30GB.




## Inicialização do Banco de Dados e Normalização da Tabela Auxílio Emergencial

O código SQL fornecido tem o objetivo de criar e normalizar a estrutura de um banco de dados baseado nos dados do auxílio emergencial. A normalização segue os princípios de divisão da tabela original `auxilio_emergencial` em várias tabelas menores para evitar redundâncias e facilitar consultas mais eficientes. 

### Criação de Índices

Para otimizar as consultas no banco de dados, são criados índices baseados em árvores B nas colunas mais frequentemente consultadas, como:

- **CPF e NIS** dos beneficiários e responsáveis, otimizando buscas por CPF/NIS e junções entre tabelas.
- **Localização (código IBGE e UF)**, para consultas relacionadas à região geográfica.
- **Ano e mês** dos auxílios, facilitando a consulta por períodos de tempo específicos.

```sql
-- Índice para a tabela de beneficiários, com base em CPF (consultas por CPF são comuns)
CREATE INDEX idx_beneficiario_cpf ON beneficiario USING BTREE (cpf_beneficiario);

-- Índice para a tabela de beneficiários, com base no município e UF (para consultas por localização)
CREATE INDEX idx_beneficiario_localizacao ON beneficiario USING BTREE (codigo_ibge_municipio, uf);

-- Índice para a tabela de auxílios, com base no NIS do beneficiário (para junções frequentes entre auxilio e beneficiário)
CREATE INDEX idx_auxilio_nis_beneficiario ON auxilio USING BTREE (nis_beneficiario);

-- Índice para a tabela de auxílios, com base no enquadramento e parcela (consultas específicas de auxílio)
CREATE INDEX idx_auxilio_enquadramento_parcela ON auxilio USING BTREE (enquadramento, parcela);

-- Índice para a tabela de responsáveis, com base no CPF do responsável
CREATE INDEX idx_responsavel_cpf ON responsavel USING BTREE (cpf_responsavel);

-- Índice para a tabela de responsáveis, com base no nome do responsável
CREATE INDEX idx_responsavel_nome ON responsavel USING BTREE (nome_responsavel);

-- Índice para a tabela de auxílios, com base no ano e mês (para consultas por período)
CREATE INDEX idx_auxilio_ano_mes ON auxilio USING BTREE (ano_mes);
```
### Normalização das Tabelas

Para garantir que os dados sejam armazenados de forma eficiente e para facilitar consultas específicas, a tabela `auxilio_emergencial` foi dividida em três tabelas normalizadas: `responsavel`, `beneficiario` e `auxilio`.

#### Tabela `auxilio_emergencial`

Armazena os dados brutos sobre os benefícios concedidos, contendo informações como o mês e ano de concessão, o município, os detalhes do beneficiário e do responsável, a parcela e o valor do auxílio.
```sql
CREATE TABLE auxilio_emergencial(
  ano_mes VARCHAR(6),
  uf VARCHAR(2),
  codigo_ibge_municipio integer,
  municipio text,
  nis_beneficiario text,
  cpf_beneficiario text,
  beneficiario text,
  nis_responsavel text, 
  cpf_responsavel text,
  responsavel text,
  enquadramento text,
  parcela integer,
  observacao text,
  valor FLOAT
);
```

#### Tabela `responsavel`
Armazena os dados dos responsáveis pelo auxílio, garantindo que cada responsável seja inserido uma única vez com base no seu **NIS**.

```sql
CREATE TABLE IF NOT EXISTS responsavel (
  nis_responsavel text PRIMARY KEY,
  cpf_responsavel text,
  nome_responsavel text
);

INSERT INTO responsavel(nis_responsavel, cpf_responsavel, nome_responsavel)
SELECT
  DISTINCT ON (nis_responsavel) nis_responsavel,
  cpf_responsavel,
  responsavel
FROM auxilio_emergencial
WHERE nis_responsavel != '-2';

INSERT INTO responsavel VALUES ('-2',' ','responsavel indefinido');

```

#### Tabela `beneficiario`
Contém os dados dos beneficiários, associando-os aos seus respectivos responsáveis. Essa tabela usa o **NIS** como chave primária e mantém a integridade referencial com a tabela `responsavel`.

```sql
CREATE TABLE IF NOT EXISTS beneficiario (
  nis_beneficiario text PRIMARY KEY,
  cpf_beneficiario text, 
  nome_beneficiario text,
  uf VARCHAR(2),
  codigo_ibge_municipio integer,
  municipio text,
  nis_responsavel text,
  FOREIGN KEY (nis_responsavel) REFERENCES responsavel(nis_responsavel)
);

INSERT INTO beneficiario(nis_beneficiario, cpf_beneficiario, nome_beneficiario, uf, codigo_ibge_municipio, municipio, nis_responsavel)
SELECT
  DISTINCT ON (nis_beneficiario) nis_beneficiario,
  cpf_beneficiario,
  beneficiario,
  uf,
  codigo_ibge_municipio,
  municipio,
  nis_responsavel
FROM auxilio_emergencial
WHERE nis_beneficiario IS NOT NULL;

```

#### Tabela `auxilio`
Essa tabela armazena as informações detalhadas sobre os auxílios recebidos pelos beneficiários, como o valor do auxílio, o enquadramento, a parcela, e a observação. Cada auxílio está relacionado a um beneficiário por meio do campo `nis_beneficiario`, que é uma chave estrangeira referenciando a tabela `beneficiario`.

```sql
CREATE TABLE IF NOT EXISTS auxilio (
  ano_mes VARCHAR(6),
  enquadramento text,
  parcela integer,
  observacao text,
  valor FLOAT,
  nis_beneficiario text,
  FOREIGN KEY (nis_beneficiario) REFERENCES beneficiario(nis_beneficiario)
);

INSERT INTO auxilio (ano_mes, enquadramento, parcela, observacao, valor, nis_beneficiario)
SELECT ano_mes, enquadramento, parcela, observacao, valor, nis_beneficiario
FROM auxilio_emergencial
WHERE nis_beneficiario IS NOT NULL;

```
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
