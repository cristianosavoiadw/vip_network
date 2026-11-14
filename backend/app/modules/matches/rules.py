"""Reciprocity rules (scope §9.1, SKILL §4). Pure functions, no database.

``reciprocity(mine, theirs)`` takes the intent of the like just sent and the intent of the
other company's active like (or ``None``) and says what the pair becomes:

- buy×sell / sell×buy → commercial match (MATCH_CONFIRMED)
- part×part → partnership match (MATCH_CONFIRMED)
- sell×sell → mutual interest ``mutual_sell`` (never an automatic match)
- buy×buy → mutual interest ``mutual_buy`` (catalogs are checked before any match)
- anything with ``net`` or other incompatible pairs → mutual interest ``relationship``
"""

from __future__ import annotations

from dataclasses import dataclass

INTENT_SHORT = {"buy": "Compra", "sell": "Venda", "part": "Parceria", "net": "Relacionamento"}
INTENT_LABEL = {
    "buy": "Quero comprar",
    "sell": "Quero vender",
    "part": "Parceria",
    "net": "Relacionamento",
}
# the side of the other company: if I want to buy, they would be selling
FLIP = {"buy": "sell", "sell": "buy", "part": "part", "net": "net"}

MATCH_KINDS = ("commercial", "partnership")
MUTUAL_KINDS = ("mutual_sell", "mutual_buy", "relationship")
CONFIRMED_STATUSES = ("MATCH_CONFIRMED", "CONNECTION_ACCEPTED", "IN_CONVERSATION")

MSG_MATCH = "É MATCH! As duas empresas demonstraram interesse em fazer negócios."
MSG_MUTUAL_SELL = (
    "Vocês dois querem vender um para o outro. Isso não vira match de compra e venda "
    "automaticamente; registramos o interesse mútuo e sugerimos uma conversa se houver "
    "complementaridade."
)
MSG_MUTUAL_BUY = (
    "Vocês dois querem comprar um do outro. Vamos conferir se as ofertas e as necessidades se "
    "encaixam antes de confirmar o match."
)
MSG_RELATIONSHIP = (
    "Interesse recíproco registrado. Ainda não é um match comercial porque as intenções não se "
    "completam."
)


@dataclass(frozen=True)
class Reciprocity:
    kind: str  # unilateral | match | mutual
    match_kind: str | None = (
        None  # commercial | partnership | mutual_sell | mutual_buy | relationship
    )
    status: str | None = None  # MATCH_CONFIRMED | MUTUAL_INTEREST
    message: str = ""

    @property
    def is_match(self) -> bool:
        return self.kind == "match"


def reciprocity(mine: str, theirs: str | None) -> Reciprocity:
    if theirs is None:
        return Reciprocity("unilateral")
    if (mine, theirs) in (("buy", "sell"), ("sell", "buy")):
        return Reciprocity("match", "commercial", "MATCH_CONFIRMED", MSG_MATCH)
    if mine == "part" and theirs == "part":
        return Reciprocity("match", "partnership", "MATCH_CONFIRMED", MSG_MATCH)
    if mine == "sell" and theirs == "sell":
        return Reciprocity("mutual", "mutual_sell", "MUTUAL_INTEREST", MSG_MUTUAL_SELL)
    if mine == "buy" and theirs == "buy":
        return Reciprocity("mutual", "mutual_buy", "MUTUAL_INTEREST", MSG_MUTUAL_BUY)
    return Reciprocity("mutual", "relationship", "MUTUAL_INTEREST", MSG_RELATIONSHIP)


def unilateral_message(target_name: str, intent: str, *, recommended: bool = False) -> str:
    if recommended:
        return (
            f"Curtida enviada. A {target_name} foi recomendada pela IA; quando ela demonstrar "
            "interesse compatível, vira match."
        )
    return (
        f"Curtida enviada. A {target_name} verá que sua empresa tem interesse: "
        f"{INTENT_SHORT.get(intent, 'Relacionamento').lower()}."
    )


def type_label(kind: str, *, i_am_buyer: bool | None = None) -> str:
    """How the kind of a match reads for one side (the mock's "Tipo de oportunidade")."""
    if kind == "commercial":
        return "Comercial: você compra" if i_am_buyer else "Comercial: você vende"
    return {
        "partnership": "Parceria",
        "mutual_sell": "Interesse mútuo de venda",
        "mutual_buy": "Interesse mútuo de compra",
        "relationship": "Relacionamento",
    }.get(kind, "Relacionamento")


def match_departments(kind: str, *, is_buyer: bool | None) -> tuple[str, ...]:
    """Who hears about a match in one company (scope §9.2)."""
    if kind == "commercial":
        return ("diretoria", "compras") if is_buyer else ("diretoria", "comercial")
    return ("diretoria",)
