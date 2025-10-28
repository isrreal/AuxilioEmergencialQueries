from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Responsavel(Base):
    __tablename__ = "responsavel"

    nis_responsavel = Column(String, primary_key = True)
    cpf_responsavel = Column(String)
    nome_responsavel = Column(String)

    beneficiarios = relationship("Beneficiario", back_populates = "responsavel")


class Beneficiario(Base):
    __tablename__ = "beneficiario"

    nis_beneficiario = Column(String, primary_key = True)
    cpf_beneficiario = Column(String)
    nome_beneficiario = Column(String)
    uf = Column(String(2))
    codigo_ibge_municipio = Column(Integer)
    municipio = Column(Text)
    nis_responsavel = Column(String, ForeignKey("responsavel.nis_responsavel"))

    responsavel = relationship("Responsavel", back_populates = "beneficiarios")
    auxilios = relationship("Auxilio", back_populates = "beneficiario")


class Auxilio(Base):
    __tablename__ = "auxilio"

    id = Column(Integer, primary_key = True, autoincrement = True)
    ano_mes = Column(String(6))
    enquadramento = Column(Text)
    parcela = Column(Integer)
    observacao = Column(Text)
    valor = Column(Float)
    nis_beneficiario = Column(String, ForeignKey("beneficiario.nis_beneficiario"))

    beneficiario = relationship("Beneficiario", back_populates = "auxilios")
