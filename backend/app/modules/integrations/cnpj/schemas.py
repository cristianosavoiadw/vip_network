"""Normalized company record, whichever provider answered."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class Address(BaseModel):
    street: str = ""
    number: str = ""
    complement: str = ""
    district: str = ""
    city: str = ""
    state: str = ""  # UF
    zip: str = ""  # 8 digits


class Partner(BaseModel):
    name: str
    role: str = ""


class CompanyInfo(BaseModel):
    cnpj: str = Field(description="14 digits")
    cnpj_formatted: str
    legal_name: str
    trade_name: str = ""
    cnae_code: str = ""
    cnae_description: str = ""
    legal_nature: str = ""
    size_code: str = ""  # Receita: 00 | 01 ME | 03 EPP | 05 demais
    size_label: str = ""
    share_capital: float | None = None
    is_active: bool = True
    status_text: str = ""
    founded: date | None = None
    address: Address = Field(default_factory=Address)
    email: str = ""
    phone: str = ""
    admin_partner: str = ""
    partners: list[Partner] = Field(default_factory=list)
    source: str  # aiware | cnpja
    fetched_at: datetime


SIZE_LABELS = {
    "00": "Não informado",
    "01": "Microempresa (ME)",
    "03": "Empresa de Pequeno Porte (EPP)",
    "05": "Demais",
}
