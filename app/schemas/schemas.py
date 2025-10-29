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
# Response Schemas SIMPLES (para listagens)
# ---------------------------

class AuxilioListResponse(BaseModel):
    """Auxílio para listagem (SEM relacionamentos)."""
    id: int
    ano_mes: Optional[str] = None
    enquadramento: Optional[str] = None
    parcela: Optional[int] = None
    observacao: Optional[str] = None
    valor: Optional[float] = None
    nis_beneficiario: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class BeneficiarioListResponse(BaseModel):
    """Beneficiário para listagem (SEM relacionamentos)."""
    nis_beneficiario: str
    cpf_beneficiario: Optional[str] = None
    nome_beneficiario: Optional[str] = None
    uf: Optional[str] = None
    codigo_ibge_municipio: Optional[int] = None
    municipio: Optional[str] = None
    nis_responsavel: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ResponsavelListResponse(BaseModel):
    """Responsável para listagem (SEM relacionamentos)."""
    nis_responsavel: str
    cpf_responsavel: Optional[str] = None
    nome_responsavel: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ---------------------------
# Response Schemas COMPLETOS (para detalhes de 1 registro)
# ---------------------------

class AuxilioDetailResponse(AuxilioBase):
    """Detalhes de UM auxílio (com beneficiário)."""
    id: int
    beneficiario: Optional[BeneficiarioListResponse] = None  # ← Shallow
    
    model_config = ConfigDict(from_attributes=True)


class BeneficiarioDetailResponse(BeneficiarioBase):
    """Detalhes de UM beneficiário (com auxílios)."""
    auxilios: List[AuxilioListResponse] = []  # ← Shallow
    responsavel: Optional[ResponsavelListResponse] = None  # ← Shallow
    
    model_config = ConfigDict(from_attributes=True)


class ResponsavelDetailResponse(ResponsavelBase):
    """Detalhes de UM responsável (com beneficiários)."""
    beneficiarios: List[BeneficiarioListResponse] = []  
    model_config = ConfigDict(from_attributes=True)