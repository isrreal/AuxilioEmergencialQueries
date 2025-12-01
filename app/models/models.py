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
    # criando um relacionamento bidirecional: ambos os lados permanecem sincronizados.
    # um responsável tem vários beneficiários
    beneficiarios = relationship("Beneficiario", back_populates = "responsavel")


class Beneficiario(settings.DBBaseModel):
    __tablename__ = "beneficiario"

    nis_beneficiario = Column(String, primary_key = True)
    cpf_beneficiario = Column(String)
    nome_beneficiario = Column(String)
    # Criando um índice baseado em UF.
    uf = Column(String(2), index = True)
    codigo_ibge_municipio = Column(Integer)
    municipio = Column(Text)
    nis_responsavel = Column(String, ForeignKey("responsavel.nis_responsavel"))

    responsavel = relationship("Responsavel", back_populates = "beneficiarios")
    auxilios = relationship("Auxilio", back_populates = "beneficiario")

    # índices compostos

    __table_args__ = (
        # Para ILIKE 'nome%'.
        # Índice baseado em árvore B para serem otimizadas para buscas por "range"
        Index(
            "idx_beneficiario_nome",
            "nome_beneficiario",
            postgresql_ops = {"nome_beneficiario": "text_pattern_ops"}
        ),

        # Para ILIKE '%termo%' com TRGM
        # Generalized Inversed ? (GIN), é um índice útil para buscas em estruturas dentro de outras estruturas (como arrays)
        Index(
            "idx_municipio_trgm",
            "municipio",
            postgresql_using = "gin",
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

    beneficiario = relationship("Beneficiario", back_populates = "auxilios")

class Usuario(settings.DBBaseModel):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key = True, autoincrement = True)
    nome = Column(String(256), nullable = True)
    sobrenome = Column(String(256), index = True, nullable = True)
    email = Column(String(256), index = True, nullable = False, unique = True)
    senha = Column(String(256), nullable = False)
    eh_admin = Column(Boolean, default = False)
