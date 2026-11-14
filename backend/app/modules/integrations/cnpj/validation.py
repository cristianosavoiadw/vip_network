"""CNPJ digits, check digits and formatting."""

from __future__ import annotations

import re

_NON_DIGITS = re.compile(r"\D+")
_WEIGHTS_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def only_digits(value: str | None) -> str:
    return _NON_DIGITS.sub("", value or "")


def _check_digit(digits: str, weights: tuple[int, ...]) -> int:
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    rest = total % 11
    return 0 if rest < 2 else 11 - rest


def is_valid_cnpj(value: str | None) -> bool:
    """14 digits, not all equal, and both check digits match."""
    d = only_digits(value)
    if len(d) != 14 or len(set(d)) == 1:
        return False
    return _check_digit(d[:12], _WEIGHTS_1) == int(d[12]) and _check_digit(
        d[:13], _WEIGHTS_2
    ) == int(d[13])


def format_cnpj(value: str) -> str:
    d = only_digits(value)
    if len(d) != 14:
        return value
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


# The RF (Rec. Fed.) "qualificação" of a partner, which our own base gives as a code
# ("49") and the public API as text ("Sócio-Administrador"). Only the codes we are sure of;
# any other shows as "Qualificação NN".
PARTNER_ROLES = {
    "05": "Administrador",
    "08": "Conselheiro de Administração",
    "10": "Diretor",
    "16": "Presidente",
    "17": "Procurador",
    "22": "Sócio",
    "28": "Sócio-Gerente",
    "49": "Sócio-Administrador",
    "50": "Empresário",
    "65": "Titular Pessoa Física Residente ou Domiciliado no Brasil",
}


def partner_role(value: str) -> str:
    """The role's text, whether it came as a code or already as text."""
    v = (value or "").strip()
    if v.isdigit():
        return PARTNER_ROLES.get(v.zfill(2), f"Qualificação {v}")
    return v
