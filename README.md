# Auxílio Emergencial - Sistema de Benchmark de Consultas

Sistema completo para análise de desempenho de consultas em banco de dados PostgreSQL utilizando índices otimizados. O projeto demonstra o impacto de diferentes estratégias de indexação em consultas reais de um dataset de Auxílio Emergencial com **257 milhões de registros**.

## 🎯 Objetivo

Demonstrar na prática como índices de banco de dados (B-Tree, GIN, TRGM) podem melhorar significativamente - ou não - o desempenho de consultas SQL complexas, através de benchmarks comparativos entre cenários com e sem indexação em um dataset real de grande volume.

## 🏗️ Arquitetura

O projeto é composto por três serviços containerizados:

- **PostgreSQL 15**: Banco de dados com extensão `pg_trgm` para buscas textuais
- **FastAPI**: API REST para gerenciar índices e executar consultas
- **Streamlit**: Dashboard interativo para visualização dos benchmarks

```
┌─────────────────┐
│   Streamlit     │
│   Dashboard     │
│   (Port 8501)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    FastAPI      │
│      API        │
│   (Port 8000)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PostgreSQL    │
│   Database      │
│   (Port 5430)   │
└─────────────────┘
```

## 🚀 Tecnologias Utilizadas

- **Backend**: FastAPI, SQLAlchemy (async), Pydantic
- **Frontend**: Streamlit, Pandas, Requests
- **Banco de Dados**: PostgreSQL 15 Alpine
- **Containerização**: Docker, Docker Compose
- **Autenticação**: JWT (OAuth2)
- **Processamento**: Asyncio, AsyncPG (bulk insert)

## 📊 Cenários de Benchmark

### 1. 💰 Gasto Total por UF
- **Índices**: B-Tree em `beneficiario(uf, nis)` e `auxilio(nis, valor)`
- **Operação**: `JOIN` + `SUM` com filtro por estado
- **Caso de Uso**: Calcular investimento total por região

### 2. 🏙️ Contagem por Município
- **Índices**: GIN com `pg_trgm` em `municipio`
- **Operação**: `COUNT DISTINCT` com `ILIKE '%termo%'`
- **Caso de Uso**: Busca textual aproximada em nomes de cidades

### 3. 🔠 Busca por Nome
- **Índices**: B-Tree com `text_pattern_ops`
- **Operação**: `SELECT` com `ILIKE 'termo%'`
- **Caso de Uso**: Autocomplete e buscas por prefixo

### 4. 🎁 Múltiplas Parcelas
- **Índices**: Compostos em `auxilio(nis, parcela)` e `beneficiario(uf, nis)`
- **Operação**: `JOIN` com filtro numérico
- **Caso de Uso**: Identificar beneficiários com critérios específicos

### 5. 👥 Beneficiários-Responsáveis
- **Índices**: Múltiplos B-Tree para JOIN triplo
- **Operação**: `JOIN` entre 3 tabelas com `DISTINCT`
- **Caso de Uso**: Análise de relações familiares no programa

## 📁 Estrutura do Projeto

```
.
├── docker-compose.yml          # Orquestração dos serviços
├── Dockerfile                  # Imagem Python para API e Dashboard
├── .env                        # Variáveis de ambiente (não versionado)
├── dashboard.py                # Interface Streamlit
├── insert.py                   # Script de importação do CSV (257M linhas)
├── dataset/                    # Dados CSV (não versionado)
│   └── auxilio_emergencial.csv
├── app/
│   ├── main.py                # Inicialização FastAPI
│   ├── api/
│   │   └── v1/
│   │       ├── api.py         # Router principal
│   │       └── endpoints/
│   │           └── consultas_routes.py  # Rotas de benchmark
│   ├── core/
│   │   ├── auth.py            # Autenticação JWT
│   │   ├── deps.py            # Dependências (DB session)
│   │   ├── config.py          # Configurações
│   │   ├── database.py        # Engine e Session AsyncPG
│   │   └── security.py        # Hashing de senhas
│   ├── models/
│   │   ├── models.py          # Modelos SQLAlchemy
│   │   └── __all_models.py    # Import de todos os models
│   └── schemas/
│       └── schemas.py         # Schemas Pydantic
└── README.md
```

## ⚙️ Configuração e Execução

### Pré-requisitos

- Docker e Docker Compose instalados
- Dataset CSV (`auxilio_emergencial.csv`) na pasta `./dataset/`
- Arquivo `.env` configurado
- **Mínimo 8GB RAM** e **50GB de espaço em disco** para o dataset completo

### Arquivo `.env`

```env
# PostgreSQL
POSTGRES_USER=seu_usuario
POSTGRES_PASSWORD=sua_senha
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/emergencial_aid_db

# Segurança
JWT_SECRET=sua_chave_secreta_jwt_muito_segura

# Admin
ADMIN_USER=admin@example.com
ADMIN_PASSWORD=senha_admin_segura
```

### Iniciar o Projeto

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/AuxilioEmergencialQueries.git
cd AuxilioEmergencialQueries

# Configure o .env
cp .env.example .env
# Edite o .env com suas credenciais

# Inicie apenas o banco de dados primeiro
docker-compose up -d db

# Aguarde o banco estar pronto
docker-compose logs -f db
# Aguarde até ver "database system is ready to accept connections"
```

### Importar os Dados

**⚠️ IMPORTANTE**: A importação do dataset completo pode levar **várias horas** (estimativa: 2-26h dependendo do hardware).

```bash
# Execute o script de importação dentro do container
docker-compose run --rm api python insert.py

# Ou execute localmente se preferir
python insert.py
```

**Detalhes da Importação:**
- **257.170.290 registros** processados em chunks de 100.000
- Utiliza **asyncpg COPY** para inserção em massa (bulk insert)
- Remove duplicatas automaticamente
- Cria usuário admin automaticamente
- Progress bar com `tqdm` para acompanhamento

**Estrutura dos dados importados:**
- **Responsável**: ~66 milhões de registros únicos
- **Beneficiário**: ~67 milhões de registros únicos
- **Auxílio**: ~257 milhões de registros (histórico de parcelas)

### Iniciar os Serviços

```bash
# Após a importação, inicie todos os serviços
docker-compose up -d

# Acompanhe os logs
docker-compose logs -f api app_runner
```

### Acessar as Interfaces

- **Dashboard Streamlit**: http://localhost:8501
- **API FastAPI**: http://localhost:8000
- **Documentação API**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5430

## 🔍 Como Usar

### Dashboard Streamlit

1. Acesse http://localhost:8501
2. Escolha uma aba de benchmark
3. Configure os parâmetros da consulta (UF, município, nome, etc.)
4. Clique em "Comparar"
5. Aguarde o processo completo (4 etapas):
   - Apagar índices
   - Medir consulta SEM índice
   - Criar índices (pode demorar)
   - Medir consulta COM índice
6. Visualize os resultados: tempo, ganho percentual, gráfico e amostra de dados

### API Endpoints

**Autenticação:**
```http
POST /api/v1/login
Content-Type: application/x-www-form-urlencoded

username=admin@example.com&password=senha_admin_segura
```

**Gerenciamento de Índices:**
```http
POST /api/v1/consultas/setup/gasto-uf/criar-indices
POST /api/v1/consultas/setup/gasto-uf/apagar-indices
POST /api/v1/consultas/setup/contagem-municipio/criar-indices
POST /api/v1/consultas/setup/contagem-municipio/apagar-indices
POST /api/v1/consultas/setup/por-nome/criar-indices
POST /api/v1/consultas/setup/por-nome/apagar-indices
POST /api/v1/consultas/setup/multiplas-parcelas/criar-indices
POST /api/v1/consultas/setup/multiplas-parcelas/apagar-indices
POST /api/v1/consultas/setup/beneficiarios-responsaveis/criar-indices
POST /api/v1/consultas/setup/beneficiarios-responsaveis/apagar-indices
```

**Execução de Consultas:**
```http
GET /api/v1/consultas/executar/total-gasto-por-uf?uf=CE
GET /api/v1/consultas/executar/quantidade-beneficiarios-municipio?uf=CE&municipio=FORTALEZA
GET /api/v1/consultas/executar/beneficiarios-por-nome?nome=MARIA&limit=50
GET /api/v1/consultas/executar/beneficiarios-multiplas-parcelas?uf=SP&min_parcela=1&limit=100
GET /api/v1/consultas/executar/beneficiarios-responsaveis?uf=RJ&limit=50
GET /api/v1/consultas/executar/buscar-beneficiario/{nis}
GET /api/v1/consultas/executar/listar-beneficiarios?uf=CE&limit=1000
```

## 📈 Resultados Esperados

Os benchmarks em um dataset com **257 milhões de registros** demonstram:

### Sem Dataset Completo (Testes)
- **Buscas por PK**: ~0.001s (instantâneo)
- **Buscas textuais sem índice**: 5-30s
- **Buscas textuais com GIN/TRGM**: 0.2-1s
- **Agregações sem índice**: 10-60s
- **Agregações com índice**: 1-5s

### Com Dataset Completo (257M registros)
- **Buscas por PK**: ~0.001-0.005s (instantâneo)
- **Buscas textuais sem índice**: 60-600s (1-10 minutos) ou **TIMEOUT**
- **Buscas textuais com GIN/TRGM**: 2-15s
- **Agregações sem índice**: 120-900s (2-15 minutos) ou **TIMEOUT**
- **Agregações com índice**: 5-30s
- **JOINs complexos sem índice**: **TIMEOUT** (>10 minutos)
- **JOINs complexos com índice**: 10-60s

**Ganhos típicos**: **90-99% de redução** no tempo de resposta com índices otimizados.

### Tempo de Criação de Índices

Em um dataset com 257M de registros:
- **B-Tree simples**: 2-5 minutos
- **B-Tree composto**: 5-10 minutos
- **GIN com TRGM**: 15-30 minutos
- **Múltiplos índices**: 30-60 minutos

## 🗄️ Modelo de Dados

```sql
-- Tabela: responsavel
CREATE TABLE responsavel (
    nis_responsavel VARCHAR PRIMARY KEY,
    cpf_responsavel VARCHAR,
    nome_responsavel VARCHAR
);

-- Tabela: beneficiario
CREATE TABLE beneficiario (
    nis_beneficiario VARCHAR PRIMARY KEY,
    cpf_beneficiario VARCHAR,
    nome_beneficiario VARCHAR,
    uf VARCHAR(2),
    codigo_ibge_municipio INTEGER,
    municipio VARCHAR,
    nis_responsavel VARCHAR REFERENCES responsavel(nis_responsavel)
);

-- Tabela: auxilio
CREATE TABLE auxilio (
    id SERIAL PRIMARY KEY,
    ano_mes VARCHAR,
    enquadramento VARCHAR,
    parcela INTEGER,
    observacao TEXT,
    valor NUMERIC(10,2),
    nis_beneficiario VARCHAR REFERENCES beneficiario(nis_beneficiario)
);
```

## 🛡️ Segurança

- Autenticação JWT para rotas protegidas
- Variáveis sensíveis em `.env` (não versionado)
- Hashing de senhas com bcrypt
- Rate limiting configurável (600s timeout padrão)
- Validação de inputs com Pydantic
- Usuário admin criado automaticamente no `insert.py`

## 🐛 Troubleshooting

### Container do PostgreSQL não inicia
```bash
docker-compose down -v
docker-compose up -d db
docker-compose logs -f db
```

### Erro durante a importação (insert.py)
```bash
# Verifique se o CSV está no local correto
ls -lh dataset/auxilio_emergencial.csv

# Verifique os logs do container
docker-compose logs db

# Limpe o banco e reimporte
docker-compose down -v
docker-compose up -d db
docker-compose run --rm api python insert.py
```

### Timeout nas consultas
- Aumente o `timeout` em `dashboard.py` (linha com `requests.get(..., timeout=600)`)
- Verifique se os índices foram criados: acesse http://localhost:8000/docs
- Monitore recursos do container: `docker stats`
- Para o dataset completo, consultas sem índice podem **nunca terminar**

### Erro de conexão com API
```bash
# Verifique se os containers estão rodando
docker-compose ps

# Reinicie o serviço
docker-compose restart api

# Verifique logs
docker-compose logs api
```

### Banco de dados lento após importação
```bash
# Execute VACUUM e ANALYZE
docker-compose exec db psql -U seu_usuario -d emergencial_aid_db -c "VACUUM ANALYZE;"
```

### Erro de memória durante importação
- Reduza o `chunk_size` em `insert.py` (de 100000 para 50000)
- Aumente a memória disponível para o Docker
- Considere importar parcialmente modificando `total_rows_to_process`

## 🔧 Configurações Avançadas

### Otimizar PostgreSQL para Grandes Volumes

Edite o `docker-compose.yml` e adicione:

```yaml
services:
  db:
    environment:
      # ... outras configs
    command: >
      postgres
      -c shared_buffers=2GB
      -c effective_cache_size=6GB
      -c maintenance_work_mem=512MB
      -c checkpoint_completion_target=0.9
      -c wal_buffers=16MB
      -c default_statistics_target=100
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
      -c work_mem=10MB
      -c min_wal_size=1GB
      -c max_wal_size=4GB
```

### Importação Parcial (Teste)

Para testar com menos dados, edite `insert.py`:

```python
# Linha ~48
total_rows_to_process = 1_000_000  # Ao invés de 257_170_290
```

## 📝 Licença

Este projeto é disponibilizado para fins educacionais e de demonstração.

## 👥 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/NovaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona NovaFeature'`)
4. Push para a branch (`git push origin feature/NovaFeature`)
5. Abra um Pull Request

### Ideias para Contribuição

- Adicionar novos cenários de benchmark
- Implementar cache de resultados
- Criar visualizações mais avançadas
- Adicionar testes automatizados
- Otimizar queries existentes
- Documentar mais patterns de indexação

## 📚 Recursos Úteis

- [Documentação PostgreSQL - Índices](https://www.postgresql.org/docs/current/indexes.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [pg_trgm Extension](https://www.postgresql.org/docs/current/pgtrgm.html)

## 📞 Contato

Para dúvidas ou sugestões, abra uma issue no repositório.

---

**Desenvolvido com ⚙️ para demonstrar o poder da indexação em bancos de dados com grandes volumes**

*Dataset: 257.170.290 registros | 3 tabelas | 5 cenários de benchmark*
