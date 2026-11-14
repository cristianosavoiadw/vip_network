"""Department-based access (scope §13). Checked in the backend on every company route.

The account owner (CEO / Proprietário) reaches every area. Everyone else reaches the areas of
their departments; a person can be in more than one. Custom departments reach the common areas
only until the owner grants more (``Department`` grants are a later step).
"""

from __future__ import annotations

BUILTIN_DEPARTMENTS: tuple[tuple[str, str], ...] = (
    ("diretoria", "Diretoria / CEO"),
    ("comercial", "Comercial"),
    ("compras", "Compras"),
    ("financeiro", "Financeiro"),
    ("rh", "Recursos Humanos"),
)

ALL = ("diretoria", "comercial", "compras", "financeiro", "rh")
BUSINESS = ("diretoria", "comercial", "compras")

# area -> departments that reach it (the owner reaches all)
AREAS: dict[str, tuple[str, ...]] = {
    "overview": ALL,
    "discover": ("diretoria", "comercial", "compras", "rh"),
    "likes": ("diretoria", "comercial", "compras", "rh"),
    "matches": BUSINESS,
    "network": BUSINESS,
    "opportunities": BUSINESS,
    "purchases": ("diretoria", "compras"),
    "sales": ("diretoria", "comercial"),
    "messages": ("diretoria", "comercial", "compras", "rh"),
    "events": ALL,
    "intelligence": BUSINESS,
    "mentorship": ("diretoria",),
    "company": ("diretoria", "comercial"),
    "team": ("diretoria",),
    "billing": ("diretoria", "financeiro"),
    "invites": ("diretoria",),
}

# which departments hear about a received like, by the intent the other company declared
# (§8.2–8.4): someone wants to buy from us → Comercial; wants to sell to us → Compras.
LIKE_AUDIENCE: dict[str, tuple[str, ...]] = {
    "buy": ("diretoria", "comercial"),
    "sell": ("diretoria", "compras"),
    "part": ("diretoria",),
    "net": ("diretoria",),
}


def areas_for(departments: list[str], *, is_owner: bool) -> list[str]:
    if is_owner:
        return list(AREAS)
    depts = set(departments)
    return [area for area, allowed in AREAS.items() if depts.intersection(allowed)] or [
        "overview",
        "events",
    ]


def can(departments: list[str], area: str, *, is_owner: bool) -> bool:
    return area in areas_for(departments, is_owner=is_owner)


def sees_intent(departments: list[str], intent: str, *, is_owner: bool) -> bool:
    """Whether this person sees likes of this intent (received or sent)."""
    if is_owner:
        return True
    return bool(set(departments).intersection(LIKE_AUDIENCE.get(intent, ("diretoria",)))) or (
        "rh" in departments and intent == "net"
    )
