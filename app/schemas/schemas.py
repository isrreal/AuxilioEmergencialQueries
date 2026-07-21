from typing import List

from pydantic import BaseModel, ConfigDict


class ResponsavelBase(BaseModel):
    nis_responsavel: str
    cpf_responsavel: str | None = None
    nome_responsavel: str | None = None


class BeneficiarioBase(BaseModel):
    nis_beneficiario: str
    cpf_beneficiario: str | None = None
    nome_beneficiario: str | None = None
    uf: str | None = None
    codigo_ibge_municipio: int | None = None
    municipio: str | None = None
    nis_responsavel: str | None = None


class AuxilioBase(BaseModel):
    ano_mes: str | None = None
    enquadramento: str | None = None
    parcela: int | None = None
    observacao: str | None = None
    valor: float | None = None
    nis_beneficiario: str | None = None

class BeneficiarioCreate(BeneficiarioBase):
    """
    Schema para a criação de um novo beneficiário.
    Herda de BeneficiarioBase mas torna campos-chave obrigatórios.
    """
    
    nis_responsavel: str

class AuxilioListResponse(BaseModel):
    """Auxílio para listagem (SEM relacionamentos)."""
    id: int
    ano_mes: str | None = None
    enquadramento: str | None = None
    parcela: int | None = None
    observacao: str | None = None
    valor: float | None = None
    nis_beneficiario: str | None = None
    
    model_config = ConfigDict(from_attributes = True)


class BeneficiarioListResponse(BaseModel):
    """Beneficiário para listagem (SEM relacionamentos)."""
    nis_beneficiario: str
    cpf_beneficiario: str | None = None
    nome_beneficiario: str | None = None
    uf: str | None = None
    codigo_ibge_municipio: int | None = None
    municipio: str | None = None
    nis_responsavel: str | None = None
    
    model_config = ConfigDict(from_attributes = True)


class ResponsavelListResponse(BaseModel):
    """Responsável para listagem (SEM relacionamentos)."""
    nis_responsavel: str
    cpf_responsavel: str | None = None
    nome_responsavel: str | None = None
    
    model_config = ConfigDict(from_attributes = True)


class AuxilioDetailResponse(AuxilioBase):
    """Detalhes de UM auxílio (com beneficiário)."""
    id: int
    beneficiario: BeneficiarioListResponse | None = None  
    
    model_config = ConfigDict(from_attributes = True)


class BeneficiarioDetailResponse(BeneficiarioBase):
    """Detalhes de UM beneficiário (com auxílios)."""
    auxilios: List[AuxilioListResponse] = []
    responsavel: ResponsavelListResponse | None = None  
    
    model_config = ConfigDict(from_attributes = True)


class ResponsavelDetailResponse(ResponsavelBase):
    """Detalhes de UM responsável (com beneficiários)."""
    beneficiarios: List[BeneficiarioListResponse] = []
    
    model_config = ConfigDict(from_attributes = True)


class TotalGastoResponse(BaseModel):
    total: float | None 

    model_config = ConfigDict(from_attributes = True)

class BeneficiarioComValorResponse(BaseModel):
    """Schema para beneficiários com valor específico de auxílio"""
    nome: str
    cpf: str
    municipio: str
    estado: str
    valor: float


class BeneficiarioResponsavelResponse(BaseModel):
    """Schema para beneficiários que são também responsáveis"""
    nome_beneficiario: str
    cpf_beneficiario: str
    municipio: str
    uf: str
    nis_responsavel: str


class ContagemResponse(BaseModel):
    """Schema para retornar contagem de registros"""
    quantidade: int