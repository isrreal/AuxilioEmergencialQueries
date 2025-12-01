from sqlalchemy import (
    Column, 
    String, 
    Integer, 
    Float, 
    Text, 
    ForeignKey, 
    Boolean,
    Index
)
from sqlalchemy.orm import relationship
from app.core.configs import settings


class Responsavel(settings.DBBaseModel):
    __tablename__ = "responsavel"

    nis_responsavel = Column(String, primary_key = True)
    cpf_responsavel = Column(String)
    nome_responsavel = Column(String)

    # Define o lado "um-para-muitos" da relação com Beneficiario.
    # back_populates conecta este atributo ao atributo "responsavel" na classe Beneficiario,
    # criando um relacionamento bidirecional.
    # Um responsável pode ter vários beneficiários.
    beneficiarios = relationship("Beneficiario", back_populates = "responsavel")


class Beneficiario(settings.DBBaseModel):
    __tablename__ = "beneficiario"

    nis_beneficiario = Column(String, primary_key = True)
    cpf_beneficiario = Column(String)
    nome_beneficiario = Column(String)

    # Criando um índice baseado em UF (B-tree padrão).
    # Útil para filtros exatos e comparações simples.
    uf = Column(String(2), index = True)
    
    codigo_ibge_municipio = Column(Integer)
    municipio = Column(Text)
    nis_responsavel = Column(String, ForeignKey("responsavel.nis_responsavel"))

    responsavel = relationship("Responsavel", back_populates = "beneficiarios")
    auxilios = relationship("Auxilio", back_populates = "beneficiario")

    # Índices adicionais
    __table_args__ = (
        # Índice B-tree para buscas de prefixo: ILIKE 'nome%'
        Index(
            "idx_beneficiario_nome",
            "nome_beneficiario",
            # text_pattern_ops define uma operator class otimizada para operações LIKE/ILIKE
            postgresql_ops = {"nome_beneficiario": "text_pattern_ops"}
        ),

        # Generalized Inverted Index (GIN) é um índice invertido. Uma estrutura de dados.
        # Ele armazena para cada token uma lista (posting list) de TIDs das linhas que contêm aquele token.
        # TID = Tuple ID = endereço físico da linha na heap: (block_number, offset_number)
        # O GIN não é baseado em B-tree: sua estrutura é uma árvore GIN própria,
        # cujos nós internos mapeiam tokens para folhas que armazenam TIDs.
        #
        # Tokens dependem da operator class:
        #   - Para gin_trgm_ops: tokens = trigramas extraídos da string.
        #
        # Cada entrada no índice contém:
        #   token -> posting list (lista ordenada de TIDs)
        #
        # O PostgreSQL tokeniza cada valor antes de indexar. 
        # O GIN acelera buscas aproximadas quando usado com uma operator class que implementa similaridade, como gin_trgm_ops.

        Index(
            "idx_municipio_trgm",
            "municipio",
            postgresql_using = "gin",
            # Operator class específica para trigramas no GIN.
            # Uma operator class é um plugin que ensina o índice como tratar um tipo de dado e quais operadores podem usar esse índice.
            postgresql_ops = {"municipio": "gin_trgm_ops"}
        ),
    )


class Auxilio(settings.DBBaseModel):
    __tablename__ = "auxilio"
    
    id = Column(Integer, primary_key = True, autoincrement = True)
    ano_mes = Column(String(6))
    enquadramento = Column(Text)
    parcela = Column(Integer)
    observacao = Column(Text)
    valor = Column(Float)

    nis_beneficiario = Column(String, ForeignKey("beneficiario.nis_beneficiario"))

    # Cada auxílio pertence a um único beneficiário (muitos-para-um)
    beneficiario = relationship("Beneficiario", back_populates = "auxilios")


class Usuario(settings.DBBaseModel):
    __tablename__ = "usuarios"

    id = Column(
        Integer,
        primary_key = True,
        autoincrement = True
    )
    nome = Column(
        String(256),
        nullable = True
    )
    sobrenome = Column(
        String(256),
        index = True,
        nullable = True
    )
    email = Column(
        String(256),
        index = True,
        nullable = False,
        unique = True
    )
    senha = Column(
        String(256),
        nullable = False
    )
    eh_admin = Column(
        Boolean,
        default = False
    )
