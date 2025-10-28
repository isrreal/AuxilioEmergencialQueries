from pydantic import BaseModel, ConfigDict
from typing import Optional, List


# ---------------------------
# Base Schemas
# ---------------------------

class ResponsavelBase(BaseModel):
    nis_responsavel: str
    cpf_responsavel: Optional[str] = None
    nome_responsavel: Optional[str] = None


class BeneficiarioBase(BaseModel):
    nis_beneficiario: str
    cpf_beneficiario: Optional[str] = None
    nome_beneficiario: Optional[str] = None
    uf: Optional[str] = None
    codigo_ibge_municipio: Optional[int] = None
    municipio: Optional[str] = None
    nis_responsavel: Optional[str] = None


class AuxilioBase(BaseModel):
    ano_mes: Optional[str] = None
    enquadramento: Optional[str] = None
    parcela: Optional[int] = None
    observacao: Optional[str] = None
    valor: Optional[float] = None
    nis_beneficiario: Optional[str] = None


# ---------------------------
# Create Schemas (para POST)
# ---------------------------

class ResponsavelCreate(ResponsavelBase):
    pass


class BeneficiarioCreate(BeneficiarioBase):
    pass


class AuxilioCreate(AuxilioBase):
    pass


# ---------------------------
# Response Schemas (com ORM)
# ---------------------------

class AuxilioResponse(AuxilioBase):
    id: int

    # Pydantic v2
    model_config = ConfigDict(from_attributes=True)
    
    # OU se estiver usando Pydantic v1, use:
    # class Config:
    #     orm_mode = True


class BeneficiarioResponse(BeneficiarioBase):
    auxilios: List[AuxilioResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ResponsavelResponse(ResponsavelBase):
    beneficiarios: List[BeneficiarioResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------
# Schemas adicionais úteis
# ---------------------------

class AuxilioSummary(BaseModel):
    """Resumo de auxílios (sem relações)."""
    id: int
    ano_mes: Optional[str] = None
    valor: Optional[float] = None
    parcela: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class BeneficiarioSummary(BaseModel):
    """Resumo de beneficiário (sem relações completas)."""
    nis_beneficiario: str
    nome_beneficiario: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    total_auxilios: int = 0
    valor_total: float = 0.0
    
    model_config = ConfigDict(from_attributes=True)


class ResponsavelSummary(BaseModel):
    """Resumo de responsável (sem relações completas)."""
    nis_responsavel: str
    nome_responsavel: Optional[str] = None
    total_beneficiarios: int = 0
    
    model_config = ConfigDict(from_attributes = True)