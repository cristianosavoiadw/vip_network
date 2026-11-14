"""``manage.py seed --demo``: the world of the approved mock with real rows, for local
development. Idempotent: every run removes the previous demo world (companies with the demo
CNPJs, users ``@demo.vipnetwork.com.br``, demo invites and events) and creates it again with
dates relative to now. Never runs in production.
"""

from __future__ import annotations

import random
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User
from app.modules.billing.models import PRICES_CENTS, Invoice, Purchase, Subscription, TrialClaim
from app.modules.billing.service import add_months
from app.modules.boosts.models import PACKAGES, BoostCampaign, OrgDayStat
from app.modules.catalog.models import Offer, PurchaseNeed
from app.modules.connections.models import Connection
from app.modules.discovery.models import OrgBlock, Report
from app.modules.events.models import Event, EventRegistration
from app.modules.integrations.cnpj.validation import format_cnpj
from app.modules.intelligence.models import Recommendation
from app.modules.invites.models import Invite
from app.modules.likes.models import Like
from app.modules.mail.models import EmailMessage
from app.modules.matches.models import Match
from app.modules.messaging.models import Conversation, Message
from app.modules.opportunities.models import Opportunity
from app.modules.organizations.models import AccessRequest, Department, Organization
from app.modules.organizations.permissions import BUILTIN_DEPARTMENTS
from app.modules.weos.models import AIJob

DOMAIN = "demo.vipnetwork.com.br"
PASSWORD = "demo12345"
ADMIN_EMAIL = f"admin@{DOMAIN}"
SP = ZoneInfo("America/Sao_Paulo")
EVENT_SLUGS = ("demo-jantar-negocios-sp", "demo-rodada-industria-joinville", "demo-cafe-logistica")
INVITE_CODES = (
    "VIP-EQ01-FND7",
    "VIP-EQ02-VRTC",
    "VIP-AE7K-2Q9M",
    "VIP-7QK2-H4MD",
    "VIP-K9DW-1MPE",
    "VIP-M3TR-9XLA",
)


def cnpj_from(seed: int) -> str:
    """A valid CNPJ (matriz 0001) with computed check digits."""
    base = [int(c) for c in f"{seed:08d}"] + [0, 0, 0, 1]
    for weights in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        r = sum(d * w for d, w in zip(base, weights, strict=False)) % 11
        base.append(0 if r < 2 else 11 - r)
    return "".join(map(str, base))


# key: name, legal name, color, segment, sector, city, state, description, offers, verified,
#      owner (name, job, e-mail local part), months since entry
ORGS: dict[str, dict[str, Any]] = {
    "andrade": dict(
        name="Andrade Embalagens",
        legal="ANDRADE EMBALAGENS PLÁSTICAS LTDA",
        color="#0F2A55",
        segment="Embalagens plásticas",
        sector="industria",
        city=("Diadema", "SP"),
        desc="Fabricante de embalagens plásticas térmicas, bandejas e frascos para indústria "
        "alimentícia, farmacêutica e eletrônica.",
        offers=[
            ("Embalagens térmicas para congelados", "Embalagens"),
            ("Bandejas para hortifrúti", "Embalagens"),
            ("Frascos PET 100 ml", "Embalagens"),
            ("Embalagens antiestáticas", "Embalagens"),
        ],
        verified=True,
        owner=("Marina Andrade", "CEO", "marina"),
        age_days=25,
    ),
    "metaltech": dict(
        name="MetalTech Indústria",
        legal="METALTECH INDÚSTRIA METALÚRGICA LTDA",
        color="#2F4B7C",
        segment="Indústria e Manufatura",
        sector="industria",
        city=("Joinville", "SC"),
        desc="Usinagem CNC, estampagem e componentes metálicos sob medida para linhas de produção.",
        offers=[
            ("Componentes usinados", "Usinagem"),
            ("Estampagem de chapas", "Metalurgia"),
            ("Manutenção de moldes", ""),
        ],
        verified=True,
        owner=("Rafael Moura", "Diretor", "rafael.metaltech"),
        age_days=160,
    ),
    "alfa": dict(
        name="Alfa Resinas & Filmes",
        legal="ALFA RESINAS E FILMES DISTRIBUIDORA LTDA",
        color="#1F6F5C",
        segment="Matérias-primas plásticas",
        sector="industria",
        city=("Guarulhos", "SP"),
        desc="Distribuidora de resinas PEAD e PP e de filme stretch, com entrega semanal na "
        "Grande São Paulo.",
        offers=[
            ("Filme stretch industrial", "Filme stretch"),
            ("Resina PEAD sopro", "Resinas"),
            ("Resina PP injeção", "Resinas"),
        ],
        verified=True,
        owner=("Juliana Prado", "CEO", "juliana.alfa"),
        age_days=130,
    ),
    "tecnova": dict(
        name="TecNova Sistemas",
        legal="TECNOVA SISTEMAS DE AUTOMAÇÃO LTDA",
        color="#3A3F9E",
        segment="Tecnologia e Automação",
        sector="tecnologia",
        city=("Curitiba", "PR"),
        desc="Automação de linhas industriais, visão computacional e manutenção preditiva.",
        offers=[
            ("Automação de linhas", "Automação"),
            ("Inspeção por câmera", "Automação"),
            ("Contratos de manutenção", ""),
        ],
        verified=True,
        owner=("Bruno Teixeira", "Sócio", "bruno.tecnova"),
        age_days=3,
    ),
    "rotasul": dict(
        name="Rota Sul Transportes",
        legal="ROTA SUL TRANSPORTES E LOGÍSTICA LTDA",
        color="#8A4B1E",
        segment="Transporte e Logística",
        sector="logistica",
        city=("Porto Alegre", "RS"),
        desc="Frete fracionado e dedicado entre Sul e Sudeste, com rastreio em tempo real.",
        offers=[
            ("Frete fracionado Sul–Sudeste", "Frete"),
            ("Carga dedicada", "Frete"),
            ("Armazenagem cross-docking", "Armazenagem"),
        ],
        verified=False,
        owner=("Fábio Rocha", "Diretor comercial", "fabio.rotasul"),
        age_days=70,
    ),
    "ecolog": dict(
        name="EcoLog Soluções Ambientais",
        legal="ECOLOG SOLUÇÕES AMBIENTAIS LTDA",
        color="#2E7D4F",
        segment="Logística reversa",
        sector="logistica",
        city=("Campinas", "SP"),
        desc="Logística reversa de embalagens e certificação de reciclagem para indústria e varejo.",
        offers=[
            ("Logística reversa", "Ambiental"),
            ("Certificado de reciclagem", "Ambiental"),
            ("Coleta de aparas", "Ambiental"),
        ],
        verified=True,
        owner=("Camila Nunes", "CEO", "camila.ecolog"),
        age_days=100,
    ),
    "vertice": dict(
        name="Vértice Distribuidora",
        legal="VÉRTICE DISTRIBUIDORA DE INSUMOS LTDA",
        color="#6B2E6F",
        segment="Distribuição atacadista",
        sector="servicos",
        city=("Recife", "PE"),
        desc="Distribuição de insumos para food service e varejo em todo o Nordeste.",
        offers=[
            ("Distribuição regional", "Distribuição"),
            ("Armazém em Recife", "Armazenagem"),
            ("Força de vendas", "Distribuição"),
        ],
        verified=True,
        owner=("André Cavalcanti", "Diretor", "andre.vertice"),
        age_days=340,
    ),
    "prime": dict(
        name="Prime Eventos Corporativos",
        legal="PRIME EVENTOS CORPORATIVOS LTDA",
        color="#7A2533",
        segment="Eventos e Hospitalidade",
        sector="servicos",
        city=("São Paulo", "SP"),
        desc="Convenções, feiras e jantares corporativos com produção completa.",
        offers=[
            ("Produção de eventos", "Eventos"),
            ("Estandes para feiras", "Eventos"),
            ("Brindes corporativos", ""),
        ],
        verified=False,
        owner=("Larissa Campos", "Sócia", "larissa.prime"),
        age_days=12,
    ),
    "bompreco": dict(
        name="Supermercados Bom Preço",
        legal="SUPERMERCADOS BOM PREÇO LTDA",
        color="#B0472A",
        segment="Varejo alimentar",
        sector="varejo",
        city=("Santo André", "SP"),
        desc="Rede com 14 lojas no ABC paulista.",
        offers=[("Varejo alimentar", "Varejo")],
        verified=True,
        owner=("Sérgio Almeida", "Diretor de compras", "sergio.bompreco"),
        age_days=95,
    ),
    "vidaplena": dict(
        name="Farmácias Vida Plena",
        legal="FARMÁCIAS VIDA PLENA LTDA",
        color="#1D7C8C",
        segment="Varejo farmacêutico",
        sector="saude",
        city=("Campinas", "SP"),
        desc="Rede de farmácias com manipulação própria.",
        offers=[("Manipulação", "Farmácia"), ("Varejo farmacêutico", "Farmácia")],
        verified=True,
        owner=("Carlos Mendes", "Gerente de compras", "carlos.vidaplena"),
        age_days=65,
    ),
    "conecta": dict(
        name="Conecta RH",
        legal="CONECTA RH RECRUTAMENTO LTDA",
        color="#4B5A75",
        segment="Recrutamento e Treinamento",
        sector="servicos",
        city=("São Paulo", "SP"),
        desc="Recrutamento operacional e treinamento de líderes de produção.",
        offers=[("Recrutamento operacional", "RH"), ("Treinamento de líderes", "RH")],
        verified=True,
        owner=("Patrícia Lopes", "CEO", "patricia.conecta"),
        age_days=5,
    ),
    "central": dict(
        name="Mercado Central Atacado",
        legal="MERCADO CENTRAL ATACADO LTDA",
        color="#946B12",
        segment="Atacado",
        sector="varejo",
        city=("São Bernardo do Campo", "SP"),
        desc="Atacarejo com 6 unidades.",
        offers=[("Atacado", "Varejo")],
        verified=False,
        owner=("Marcos Ferreira", "Diretor", "marcos.central"),
        age_days=45,
    ),
    "horizonte": dict(
        name="Grupo Horizonte Alimentos",
        legal="GRUPO HORIZONTE ALIMENTOS S.A.",
        color="#25507A",
        segment="Alimentos congelados",
        sector="industria",
        city=("Jundiaí", "SP"),
        desc="Fabricante de pratos prontos congelados.",
        offers=[("Congelados", "Alimentos")],
        verified=True,
        owner=("Ricardo Lima", "Diretor", "ricardo.horizonte"),
        age_days=74,
    ),
    "plastimax": dict(
        name="Plastimax Moldados",
        legal="PLASTIMAX MOLDADOS PLÁSTICOS LTDA",
        color="#5B3E8E",
        segment="Peças plásticas",
        sector="industria",
        city=("Mauá", "SP"),
        desc="Injeção de tampas e lacres.",
        offers=[("Tampas e lacres", "")],
        verified=False,
        owner=("Eduardo Pires", "Sócio", "eduardo.plastimax"),
        age_days=40,
    ),
    "lumen": dict(
        name="Lumen Energia Solar",
        legal="LUMEN ENERGIA SOLAR LTDA",
        color="#C07A12",
        segment="Energia",
        sector="servicos",
        city=("Ribeirão Preto", "SP"),
        desc="Usinas solares por assinatura para indústrias.",
        offers=[("Energia por assinatura", "Energia")],
        verified=True,
        owner=("Gustavo Reis", "CEO", "gustavo.lumen"),
        age_days=150,
    ),
    "casanobre": dict(
        name="Casa Nobre Hotéis",
        legal="CASA NOBRE HOTÉIS LTDA",
        color="#5C4A2E",
        segment="Hotelaria",
        sector="servicos",
        city=("São Paulo", "SP"),
        desc="Rede de hotéis executivos.",
        offers=[("Hotelaria", "Hotelaria")],
        verified=True,
        owner=("Helena Duarte", "Diretora de compras", "helena.casanobre"),
        age_days=21,
    ),
}
DEMO_CNPJS = {key: cnpj_from(41_230_000 + i * 7_919) for i, key in enumerate(ORGS)}
EXTRA_CNPJS = {  # companies invited but not (yet) in the network
    "serraazul": cnpj_from(41_990_101),
    "cleanpro": cnpj_from(41_990_202),
}


@dataclass
class World:
    session: AsyncSession
    now: datetime
    orgs: dict[str, Organization] = field(default_factory=dict)
    owners: dict[str, User] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)
    password_hash: str = ""

    def ago(self, days: float = 0, hours: float = 0) -> datetime:
        return self.now - timedelta(days=days, hours=hours)


def _pair(a: Organization, b: Organization) -> tuple[uuid.UUID, uuid.UUID]:
    return (a.id, b.id) if str(a.id) < str(b.id) else (b.id, a.id)


# ------------------------------------------------------------------ clear


async def clear(session: AsyncSession) -> None:
    """Remove the demo world (and only it)."""
    cnpjs = list(DEMO_CNPJS.values()) + list(EXTRA_CNPJS.values())
    org_ids = list(
        (
            await session.execute(
                select(Organization.id).where(Organization.cnpj.in_(DEMO_CNPJS.values()))
            )
        ).scalars()
    )
    await session.execute(
        delete(Invite).where(
            or_(
                Invite.code.in_(INVITE_CODES),
                Invite.cnpj.in_(cnpjs),
                Invite.inviter_org_id.in_(org_ids),
            )
        )
    )
    await session.execute(delete(Event).where(Event.slug.in_(EVENT_SLUGS)))
    await session.execute(delete(EmailMessage).where(EmailMessage.to_email.like(f"%@{DOMAIN}")))
    await session.execute(delete(TrialClaim).where(TrialClaim.cnpj.in_(cnpjs)))
    if org_ids:
        await session.execute(delete(AuditLog).where(AuditLog.org_id.in_(org_ids)))
        await session.execute(
            delete(Conversation).where(
                or_(Conversation.org_low_id.in_(org_ids), Conversation.org_high_id.in_(org_ids))
            )
        )
        await session.execute(
            delete(Opportunity).where(
                or_(Opportunity.buyer_org_id.in_(org_ids), Opportunity.seller_org_id.in_(org_ids))
            )
        )
    await session.execute(delete(User).where(User.email.like(f"%@{DOMAIN}")))
    if org_ids:
        await session.execute(delete(Organization).where(Organization.id.in_(org_ids)))
    await session.flush()


# ------------------------------------------------------------------ builders


async def _user(
    w: World,
    org: Organization | None,
    name: str,
    local: str,
    *,
    job: str = "",
    owner: bool = False,
    departments: list[str] | None = None,
    kind: str = "member",
    admin_role: str = "",
) -> User:
    user = User(
        email=f"{local}@{DOMAIN}",
        password_hash=w.password_hash,
        kind=kind,
        status="active",
        full_name=name,
        job_title=job,
        org_id=org.id if org else None,
        is_org_owner=owner,
        departments=departments or (["diretoria"] if owner else []),
        cnpj_relation="socio" if owner else "",
        admin_role=admin_role,
        email_verified_at=w.ago(30),
        last_login_at=w.ago(hours=random.randint(1, 72)),
    )
    w.session.add(user)
    await w.session.flush()
    w.users[local] = user
    return user


async def _orgs(w: World) -> None:
    for key, o in ORGS.items():
        cnpj = DEMO_CNPJS[key]
        city, state = o["city"]
        entered = w.ago(o["age_days"])
        org = Organization(
            cnpj=cnpj,
            slug=f"demo-{key}",
            legal_name=o["legal"],
            trade_name=o["name"],
            status="active",
            official={
                "cnpj": format_cnpj(cnpj),
                "legal_name": o["legal"],
                "trade_name": o["name"],
                "cnae_description": o["segment"],
                "size": "Empresa de Pequeno Porte (EPP)",
                "status": "Ativa",
                "city": city,
                "state": state,
                "source": "demo",
            },
            official_fetched_at=entered,
            city=city,
            state=state,
            size="Empresa de Pequeno Porte (EPP)",
            opened_on=date(2004 + len(key) % 15, 3, 14),
            sector=o["sector"],
            segment=o["segment"],
            description=o["desc"],
            coverage="Brasil",
            color=o["color"],
            goals=["vender", "comprar"],
            verified=o["verified"],
            discoverable=True,
            onboarding_step=10,
            onboarding_completed_at=entered + timedelta(hours=2),
            created_at=entered,
            entry="subscription",
        )
        w.session.add(org)
        await w.session.flush()
        w.orgs[key] = org
        for slug, dname in BUILTIN_DEPARTMENTS:
            w.session.add(Department(org_id=org.id, slug=slug, name=dname, builtin=True))
        name, job, local = o["owner"]
        w.owners[key] = await _user(w, org, name, local, job=job, owner=True)
        for offer, category in o["offers"]:
            w.session.add(
                Offer(
                    org_id=org.id,
                    kind="service" if o["sector"] in ("servicos", "logistica") else "product",
                    name=offer,
                    category=category,
                    description=f"{offer} — {o['name']}.",
                    price_on_request=offer not in OFFER_PRICES,
                    price_cents=OFFER_PRICES.get(offer, (None, ""))[0],
                    unit=OFFER_PRICES.get(offer, (None, ""))[1],
                    coverage="Brasil",
                    status="published",
                )
            )
    # Andrade's team and the people of the conversations
    a = w.orgs["andrade"]
    await _user(w, a, "João Silva", "joao", job="Comprador", departments=["compras"])
    await _user(w, a, "Renata Costa", "renata", job="Gerente comercial", departments=["comercial"])
    await _user(
        w, w.orgs["horizonte"], "Paula Reis", "paula", job="Compras", departments=["compras"]
    )


# public prices of the demo offers that compete with Andrade's purchases (the rest is
# "sob consulta"): stretch film R$ 95 vs R$ 120 paid = R$ 25.000/month as in the mock
OFFER_PRICES: dict[str, tuple[int, str]] = {
    "Filme stretch industrial": (9_500, "bobina"),
    "Frete fracionado Sul–Sudeste": (350_000, "carga"),
    "Energia por assinatura": (5_780_000, "mês"),
    "Bandejas para hortifrúti": (38, "un."),
    "Frascos PET 100 ml": (62, "un."),
}


async def _needs(w: World) -> None:
    """What Andrade buys: private (never shown to another company or to the team panel)."""
    a = w.orgs["andrade"].id
    for name, category, price, unit, volume, qty, supplier in (
        (
            "Filme stretch",
            "Filme stretch",
            12_000,
            "bobina",
            "1.000 bobinas/mês",
            1000,
            "Fornecedor atual",
        ),
        ("Resina PEAD sopro", "Resinas", 980, "kg", "12 t/mês", 12_000, "Distribuidora regional"),
        ("Frete Diadema–Porto Alegre", "Frete", 420_000, "carga", "6 cargas/mês", 6, ""),
        (
            "Energia elétrica da fábrica",
            "Energia",
            6_800_000,
            "mês",
            "1 conta/mês",
            1,
            "Distribuidora local",
        ),
        ("Recrutamento operacional", "RH", None, "vaga", "8 vagas/trimestre", None, ""),
    ):
        w.session.add(
            PurchaseNeed(
                org_id=a,
                name=name,
                category=category,
                price_paid_cents=price,
                unit=unit,
                volume=volume,
                volume_qty=qty,
                frequency="mensal",
                current_supplier=supplier,
                delivery_region="Diadema, SP",
                goal="reduce_cost",
                visibility="private",
            )
        )
    w.session.add(
        PurchaseNeed(
            org_id=w.orgs["bompreco"].id,
            name="Bandejas para hortifrúti",
            category="Embalagens",
            spec="Bandeja PET 20×15 cm",
            volume="50 mil/mês",
            delivery_region="ABC paulista",
            visibility="published",
            publish_flags={"volume": True},
        )
    )


async def _subscriptions(w: World) -> None:
    now = w.now

    def add(key: str, **kw: Any) -> Subscription:
        sub = Subscription(
            org_id=w.orgs[key].id,
            stripe_customer_id=f"sim_cus_demo{key[:6]}",
            stripe_subscription_id=f"sim_sub_demo{key[:6]}",
            card_brand="visa",
            card_last4="4242",
            card_exp="12/2029",
            **kw,
        )
        w.session.add(sub)
        return sub

    def paid(key: str, plan: str, start: datetime) -> None:
        add(
            key,
            plan=plan,
            kind="standard",
            status="active",
            trial_start=start - timedelta(days=7),
            trial_end=start,
            current_period_end=add_months(start, 12 if plan == "annual" else 1),
        )
        w.session.add(TrialClaim(cnpj=DEMO_CNPJS[key], org_id=w.orgs[key].id, claimed_at=start))
        w.session.add(
            Invoice(
                org_id=w.orgs[key].id,
                stripe_invoice_id=f"sim_in_demo_{key}",
                amount_cents=PRICES_CENTS[plan],
                status="paid",
                description=f"VIP Network {'Anual' if plan == 'annual' else 'Mensal'}",
                period_start=start,
                period_end=add_months(start, 12 if plan == "annual" else 1),
                paid_at=start,
            )
        )

    # monthly payers renewed in the last days → revenue of this month
    for key, days in (("alfa", 11), ("metaltech", 4), ("bompreco", 8), ("vidaplena", 2)):
        paid(key, "monthly", w.ago(days))
    paid("central", "monthly", w.ago(16))
    paid("plastimax", "monthly", w.ago(20))
    for key, days in (("ecolog", 93), ("lumen", 143), ("horizonte", 67)):
        paid(key, "annual", w.ago(days))
    # trials
    for key, days in (("tecnova", 3), ("conecta", 5)):
        start = w.ago(days)
        add(
            key,
            plan="monthly",
            kind="standard",
            status="trialing",
            trial_start=start,
            trial_end=start + timedelta(hours=168),
            current_period_end=start + timedelta(hours=168),
        )
        w.session.add(TrialClaim(cnpj=DEMO_CNPJS[key], org_id=w.orgs[key].id, claimed_at=start))
    # payment failed
    start = w.ago(63)
    add(
        "rotasul",
        plan="monthly",
        kind="standard",
        status="past_due",
        trial_start=start,
        trial_end=start + timedelta(days=7),
        current_period_end=w.ago(1),
    )
    w.session.add(
        Invoice(
            org_id=w.orgs["rotasul"].id,
            stripe_invoice_id="sim_in_demo_rotasul_open",
            amount_cents=PRICES_CENTS["monthly"],
            status="open",
            description="VIP Network Mensal",
            period_start=w.ago(1),
        )
    )
    # canceled during the trial
    start = w.ago(12)
    add(
        "prime",
        plan="monthly",
        kind="standard",
        status="canceled",
        trial_start=start,
        trial_end=start + timedelta(hours=168),
        canceled_at=start + timedelta(days=3),
    )
    # VIP guests (invited)
    for key, vip_start, until in (
        ("andrade", w.ago(25), None),
        ("casanobre", w.ago(21), None),
        ("vertice", w.ago(340), now + timedelta(days=25)),
    ):
        vip_until = until or add_months(vip_start, 12)
        add(
            key,
            plan="monthly",
            kind="vip",
            status="trialing",
            trial_start=vip_start,
            trial_end=vip_until,
            current_period_end=vip_until,
            vip_until=vip_until,
            vip_after="then_charge",
        )


async def _invites(w: World) -> None:
    o = w.orgs

    def inv(
        code: str,
        inviter: str | None,
        company: str,
        cnpj: str,
        email: str,
        sent: datetime,
        status: str,
        accepted: str | None = None,
    ) -> None:
        w.session.add(
            Invite(
                code=code,
                inviter_org_id=o[inviter].id if inviter else None,
                inviter_user_id=w.owners[inviter].id if inviter else None,
                by_staff=inviter is None,
                first_name=email.split("@")[0].split(".")[0].title(),
                last_name=(email.split("@")[0].split(".")[1:] or [company.split()[0]])[0].title(),
                company_name=company,
                email=email,
                status=status,
                created_at=sent,
                expires_at=sent + timedelta(days=30),
                accepted_org_id=o[accepted].id if accepted else None,
                accepted_at=sent + timedelta(days=1) if accepted else None,
            )
        )

    inv(
        "VIP-EQ01-FND7",
        None,
        ORGS["horizonte"]["name"],
        DEMO_CNPJS["horizonte"],
        f"ricardo.horizonte@{DOMAIN}",
        w.ago(75),
        "accepted",
        "horizonte",
    )
    inv(
        "VIP-EQ02-VRTC",
        None,
        ORGS["vertice"]["name"],
        DEMO_CNPJS["vertice"],
        f"andre.vertice@{DOMAIN}",
        w.ago(341),
        "accepted",
        "vertice",
    )
    inv(
        "VIP-AE7K-2Q9M",
        "horizonte",
        ORGS["andrade"]["name"],
        DEMO_CNPJS["andrade"],
        f"marina@{DOMAIN}",
        w.ago(26),
        "accepted",
        "andrade",
    )
    inv(
        "VIP-7QK2-H4MD",
        "andrade",
        ORGS["casanobre"]["name"],
        DEMO_CNPJS["casanobre"],
        f"helena.casanobre@{DOMAIN}",
        w.ago(22),
        "accepted",
        "casanobre",
    )
    inv(
        "VIP-K9DW-1MPE",
        "casanobre",
        "Lavanderia Clean Pro",
        EXTRA_CNPJS["cleanpro"],
        f"contato.cleanpro@{DOMAIN}",
        w.ago(40),
        "expired",
    )
    inv(
        "VIP-M3TR-9XLA",
        "andrade",
        "Metalúrgica Serra Azul",
        EXTRA_CNPJS["serraazul"],
        f"compras.serraazul@{DOMAIN}",
        w.ago(4),
        "pending",
    )
    for key, by in (
        ("andrade", "horizonte"),
        ("casanobre", "andrade"),
        ("horizonte", None),
        ("vertice", None),
    ):
        o[key].entry = "invite"
        o[key].invited_by_org_id = o[by].id if by else None


async def _likes_matches(w: World) -> dict[str, Match]:
    o = w.orgs

    def like(src: str, tgt: str, intent: str, product: str, days: float) -> None:
        w.session.add(
            Like(
                source_org_id=o[src].id,
                target_org_id=o[tgt].id,
                actor_user_id=w.owners[src].id,
                intent=intent,
                products=[product],
                status="active",
                created_at=w.ago(days),
            )
        )

    # sent by Andrade
    like("andrade", "conecta", "buy", "Recrutamento operacional", 7)
    like("andrade", "central", "sell", "Bandejas para hortifrúti", 9)
    like("andrade", "horizonte", "sell", "Embalagens térmicas para congelados", 12)
    like("andrade", "plastimax", "sell", "Frascos PET 100 ml", 15)
    # received by Andrade
    like("alfa", "andrade", "sell", "Filme stretch industrial", 2)
    like("tecnova", "andrade", "buy", "Embalagens antiestáticas", 3)
    like("rotasul", "andrade", "sell", "Frete fracionado Sul–Sudeste", 5)
    like("vertice", "andrade", "part", "Distribuição no Nordeste", 6)
    like("bompreco", "andrade", "buy", "Bandejas para hortifrúti", 1)
    like("vidaplena", "andrade", "buy", "Frascos PET 100 ml", 8)
    like("horizonte", "andrade", "buy", "Embalagens térmicas para congelados", 11)
    like("plastimax", "andrade", "sell", "Tampas e lacres", 13)
    # the rest of the network
    like("metaltech", "alfa", "buy", "Resina PP injeção", 20)
    like("alfa", "metaltech", "sell", "Resina PP injeção", 19)
    like("tecnova", "metaltech", "part", "Automação de linhas", 2)
    like("ecolog", "bompreco", "sell", "Logística reversa", 4)
    like("lumen", "metaltech", "sell", "Energia por assinatura", 6)
    like("conecta", "rotasul", "sell", "Recrutamento operacional", 3)
    like("rotasul", "conecta", "sell", "Carga dedicada", 2)
    like("central", "plastimax", "net", "Atacado", 30)

    matches: dict[str, Match] = {}

    def match(key: str, a: str, b: str, **kw: Any) -> None:
        low, high = _pair(o[a], o[b])
        m = Match(org_low_id=low, org_high_id=high, **kw)
        w.session.add(m)
        matches[key] = m

    match(
        "horizonte",
        "andrade",
        "horizonte",
        kind="commercial",
        status="IN_CONVERSATION",
        origin="MUTUAL_LIKE",
        seller_org_id=o["andrade"].id,
        buyer_org_id=o["horizonte"].id,
        product="Embalagens térmicas para congelados",
        score=91,
        reason="Vocês vendem embalagens térmicas e eles compram para a linha de congelados.",
        confirmed_at=w.ago(11),
        created_at=w.ago(11),
    )
    match(
        "casanobre",
        "andrade",
        "casanobre",
        kind="commercial",
        status="CONNECTION_ACCEPTED",
        origin="EVENT_CONNECTION",
        seller_org_id=o["andrade"].id,
        buyer_org_id=o["casanobre"].id,
        product="Embalagens para amenities",
        score=76,
        reason="Conheceram-se no Jantar de Negócios VIP de outubro.",
        confirmed_at=w.ago(21),
        created_at=w.ago(21),
    )
    match(
        "plastimax",
        "andrade",
        "plastimax",
        kind="mutual_sell",
        status="MUTUAL_INTEREST",
        origin="MUTUAL_LIKE",
        product="Frascos PET 100 ml · Tampas e lacres",
        score=68,
        created_at=w.ago(13),
    )
    match(
        "metaltech",
        "metaltech",
        "alfa",
        kind="commercial",
        status="IN_CONVERSATION",
        origin="MUTUAL_LIKE",
        seller_org_id=o["alfa"].id,
        buyer_org_id=o["metaltech"].id,
        product="Resina PP injeção",
        score=88,
        confirmed_at=w.ago(19),
        created_at=w.ago(19),
    )
    match(
        "rotasul",
        "conecta",
        "rotasul",
        kind="mutual_sell",
        status="MUTUAL_INTEREST",
        origin="MUTUAL_LIKE",
        product="Recrutamento · Carga dedicada",
        created_at=w.ago(2),
    )
    await w.session.flush()

    for a, b, source, status, days, by in (
        ("andrade", "horizonte", "match", "accepted", 11, "andrade"),
        ("andrade", "casanobre", "event", "accepted", 21, "casanobre"),
        ("andrade", "vidaplena", "manual", "accepted", 8, "vidaplena"),
        ("andrade", "central", "manual", "accepted", 30, "andrade"),
        ("metaltech", "alfa", "match", "accepted", 19, "metaltech"),
        ("lumen", "metaltech", "manual", "requested", 1, "lumen"),
    ):
        low, high = _pair(o[a], o[b])
        w.session.add(
            Connection(
                org_low_id=low,
                org_high_id=high,
                requested_by_org_id=o[by].id,
                status=status,
                source=source,
                accepted_at=w.ago(days) if status == "accepted" else None,
                created_at=w.ago(days + 0.5),
            )
        )
    # AI recommendations shown to Andrade (Matchmaking: accepted / ignored)
    a = o["andrade"].id
    for kind, target, title, status, days in (
        ("solution", "lumen", "Energia por assinatura com 15% de desconto estimado", "new", 3),
        ("supplier", "alfa", "Filme stretch abaixo do preço que você paga", "acted", 9),
        ("buyer", "tecnova", "TecNova procura embalagens antiestáticas", "acted", 4),
        ("partner", "ecolog", "Venda das aparas de plástico para a EcoLog", "dismissed", 20),
        ("event", None, "Jantar de Negócios VIP em São Paulo", "new", 30),
    ):
        w.session.add(
            Recommendation(
                org_id=a,
                kind=kind,
                target_org_id=o[target].id if target else None,
                title=title,
                body=title,
                score=80,
                status=status,
                created_at=w.ago(days),
            )
        )
    return matches


def _hist(w: World, user: User, org: Organization, steps: list[tuple[str, float]]) -> list:
    out: list[dict[str, Any]] = []
    before = None
    for stage, days in steps:
        out.append(
            {
                "at": w.ago(days).isoformat(),
                "action": "created" if before is None else "stage",
                "org_id": str(org.id),
                "user_id": str(user.id),
                "user_name": user.full_name,
                "from": before,
                "to": stage,
            }
        )
        before = stage
    return out


async def _opportunities(w: World, matches: dict[str, Match]) -> dict[str, Opportunity]:
    o, u = w.orgs, w.users
    marina, joao, renata = u["marina"], u["joao"], u["renata"]
    a = o["andrade"]
    rows = {
        "vertice": dict(
            kind="partnership",
            buyer="vertice",
            seller="andrade",
            origin="DIRECT",
            title="Distribuição no Nordeste",
            stage="new",
            value=None,
            next="Responder interesse de parceria",
            owner=marina,
            steps=[("new", 6)],
        ),
        "alfa": dict(
            kind="buy_sell",
            buyer="andrade",
            seller="alfa",
            origin="AI_RECOMMENDATION",
            title="Filme stretch industrial",
            stage="qualification",
            value=2_380_000,
            next="Pedir ficha técnica e amostra",
            owner=joao,
            steps=[("new", 9), ("contact", 7), ("qualification", 2)],
        ),
        "casanobre": dict(
            kind="buy_sell",
            buyer="casanobre",
            seller="andrade",
            origin="EVENT",
            title="Embalagens para amenities",
            stage="contact",
            value=1_200_000,
            next="Levantar volume mensal",
            owner=renata,
            steps=[("new", 21), ("contact", 20)],
        ),
        "horizonte": dict(
            kind="buy_sell",
            buyer="horizonte",
            seller="andrade",
            origin="MUTUAL_LIKE",
            title="Embalagens térmicas T-500",
            stage="negotiation",
            value=8_600_000,
            next="Enviar amostras até 19/11",
            owner=marina,
            steps=[("new", 11), ("contact", 10), ("negotiation", 6)],
        ),
        "vidaplena": dict(
            kind="buy_sell",
            buyer="vidaplena",
            seller="andrade",
            origin="DIRECT",
            title="Frascos PET 100 ml",
            stage="proposal",
            value=3_100_000,
            next="Cobrar retorno na sexta",
            owner=renata,
            steps=[("new", 8), ("negotiation", 5), ("proposal", 3)],
        ),
        "central": dict(
            kind="buy_sell",
            buyer="central",
            seller="andrade",
            origin="MANUAL",
            title="Bandejas para hortifrúti",
            stage="won",
            value=1_800_000,
            next="Primeira entrega em 25/11",
            owner=renata,
            steps=[("new", 30), ("negotiation", 24), ("proposal", 20), ("won", 1)],
        ),
        "lumen": dict(
            kind="buy_sell",
            buyer="andrade",
            seller="lumen",
            origin="AI_RECOMMENDATION",
            title="Energia por assinatura",
            stage="lost",
            value=None,
            next="Contrato atual vence em 2027",
            owner=joao,
            steps=[("new", 40), ("contact", 35), ("lost", 28)],
        ),
        "metaltech": dict(
            kind="buy_sell",
            buyer="metaltech",
            seller="alfa",
            origin="MUTUAL_LIKE",
            title="Resina PP injeção",
            stage="negotiation",
            value=4_500_000,
            next="Fechar preço do trimestre",
            owner=None,
            steps=[("new", 45), ("negotiation", 38)],
        ),
    }
    out: dict[str, Opportunity] = {}
    for key, r in rows.items():
        creator = o[r["seller"]] if r["seller"] == "andrade" else o[r["buyer"]]
        owner = r["owner"] or w.owners[r["buyer"]]
        opp = Opportunity(
            kind=r["kind"],
            buyer_org_id=o[r["buyer"]].id,
            seller_org_id=o[r["seller"]].id,
            created_by_org_id=creator.id,
            match_id=matches[key].id if key in matches and key != "plastimax" else None,
            origin=r["origin"],
            title=r["title"],
            product=r["title"],
            compat=85,
            stage=r["stage"],
            value_estimate_cents=r["value"],
            next_action=r["next"],
            owners={str(owner.org_id): str(owner.id)},
            history=_hist(w, owner, a if owner.org_id == a.id else creator, r["steps"]),
            closed_value_cents=r["value"] if r["stage"] == "won" else None,
            close_confirmed_by=[str(o["central"].id), str(a.id)] if r["stage"] == "won" else [],
            created_at=w.ago(r["steps"][0][1]),
        )
        w.session.add(opp)
        out[key] = opp
    await w.session.flush()
    return out


async def _conversations(w: World, opps: dict[str, Opportunity]) -> None:
    o, u = w.orgs, w.users
    a = o["andrade"]
    script: dict[str, list[tuple[str | None, str, str, float, dict[str, Any] | None]]] = {
        # (sender user key or None for system, kind, body, days ago, data)
        "horizonte": [
            (None, "system", "Match confirmado · Curtida recíproca", 11, None),
            (
                "paula",
                "text",
                "Olá, Marina! Vimos as embalagens térmicas de vocês. Conseguem "
                "atender 40 mil unidades por mês?",
                10.8,
                None,
            ),
            (
                "marina",
                "attachment",
                "Olá, Paula. Conseguimos, sim. Envio a ficha técnica da linha T-500 em anexo.",
                10.5,
                {"name": "Ficha técnica T-500.pdf"},
            ),
            (
                "paula",
                "text",
                "Recebido. Podemos agendar uma visita técnica na semana que vem?",
                6,
                None,
            ),
            (
                "ricardo.horizonte",
                "text",
                "Se fecharmos amostra até dia 19, entramos no pedido de dezembro.",
                0.2,
                None,
            ),
        ],
        "casanobre": [
            (None, "system", "Conexão aceita · Jantar de Negócios VIP", 21, None),
            (
                "helena.casanobre",
                "text",
                "Foi ótimo conhecer vocês no jantar. Queremos cotar "
                "embalagens para kits de amenities.",
                20.5,
                None,
            ),
            ("renata", "text", "Obrigada, Helena! Qual o volume mensal estimado?", 20, None),
        ],
        "vidaplena": [
            (None, "system", "Solicitação de conexão aceita", 8, None),
            (
                "renata",
                "attachment",
                "Segue proposta para 20 mil frascos PET de 100 ml por mês.",
                3,
                {"name": "Proposta VP-2026-11.pdf"},
            ),
            (
                "carlos.vidaplena",
                "text",
                "Vamos analisar internamente e retornamos até sexta.",
                1,
                None,
            ),
        ],
    }
    for key, msgs in script.items():
        other = o[key]
        low, high = _pair(a, other)
        conv = Conversation(
            org_low_id=low,
            org_high_id=high,
            opportunity_id=opps[key].id,
            title=opps[key].title,
            departments={
                str(a.id): ["diretoria", "comercial"],
                str(other.id): ["diretoria", "compras"],
            },
            last_message_at=w.ago(msgs[-1][3]),
            created_at=w.ago(msgs[0][3]),
        )
        w.session.add(conv)
        await w.session.flush()
        for sender, kind, body, days, data in msgs:
            user = u[sender] if sender else None
            w.session.add(
                Message(
                    conversation_id=conv.id,
                    sender_org_id=user.org_id if user else None,
                    sender_user_id=user.id if user else None,
                    kind=kind,
                    body=body,
                    data=data or {},
                    created_at=w.ago(days),
                )
            )


async def _events(w: World) -> None:
    def at(days: int, hour: int, minute: int = 0) -> datetime:
        local = (w.now.astimezone(SP) + timedelta(days=days)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return local.astimezone(UTC)

    events = [
        (
            "demo-jantar-negocios-sp",
            "Jantar de Negócios VIP",
            "jantar",
            "São Paulo",
            "SP",
            "Restaurante parceiro · Jardins",
            at(14, 19, 30),
            40,
        ),
        (
            "demo-rodada-industria-joinville",
            "Rodada de Negócios Indústria",
            "rodada",
            "Joinville",
            "SC",
            "Centro de eventos · Zona Industrial",
            at(21, 9),
            60,
        ),
        (
            "demo-cafe-logistica",
            "Café Executivo Logística",
            "cafe",
            "Curitiba",
            "PR",
            "Hotel parceiro · Batel",
            at(27, 8),
            24,
        ),
    ]
    people = [w.owners[k] for k in ORGS]
    for slug, title, kind, city, state, place, starts, seats in events:
        ev = Event(
            slug=slug,
            title=title,
            kind=kind,
            city=city,
            state=state,
            place=place,
            starts_at=starts,
            ends_at=starts + timedelta(hours=3),
            seats=seats,
            description=f"{title}: encontro reservado para empresas da VIP Network.",
            status="published",
        )
        w.session.add(ev)
        await w.session.flush()
        guests = people[:6] if slug.endswith("-sp") else people[6:10]
        for i, user in enumerate(guests):
            w.session.add(
                EventRegistration(
                    event_id=ev.id,
                    org_id=user.org_id,
                    user_id=user.id,
                    status="waitlist" if slug.endswith("logistica") and i == 3 else "confirmed",
                    checkin_token=secrets.token_urlsafe(18),
                )
            )


async def _billing_extras(w: World) -> None:
    o = w.orgs
    rotasul = o["rotasul"]
    p = Purchase(
        org_id=rotasul.id,
        kind="boost",
        ref="10",
        amount_cents=PACKAGES[10],
        status="paid",
        stripe_session_id="sim_cs_demo_rotasul",
        paid_at=w.ago(6),
        data={"days": 10},
    )
    w.session.add(p)
    await w.session.flush()
    w.session.add(
        BoostCampaign(
            org_id=rotasul.id,
            purchase_id=p.id,
            days=10,
            amount_cents=PACKAGES[10],
            starts_at=w.ago(6),
            ends_at=w.ago(6) + timedelta(days=10),
            status="active",
        )
    )
    p2 = Purchase(
        org_id=o["prime"].id,
        kind="boost",
        ref="1",
        amount_cents=PACKAGES[1],
        status="paid",
        stripe_session_id="sim_cs_demo_prime",
        paid_at=w.ago(9),
        data={"days": 1},
    )
    w.session.add(p2)
    await w.session.flush()
    w.session.add(
        BoostCampaign(
            org_id=o["prime"].id,
            purchase_id=p2.id,
            days=1,
            amount_cents=PACKAGES[1],
            starts_at=w.ago(9),
            ends_at=w.ago(8),
            status="finished",
        )
    )


async def _stats(w: World) -> None:
    rnd = random.Random(42)
    today = w.now.astimezone(SP).date()
    boost_from = (w.ago(6)).astimezone(SP).date()
    for key, org in w.orgs.items():
        weight = 3 if key in ("andrade", "metaltech", "alfa", "horizonte") else 1
        for d in range(30):
            day = today - timedelta(days=d)
            sponsored = key == "rotasul" and day >= boost_from
            w.session.add(
                OrgDayStat(
                    org_id=org.id,
                    day=day,
                    impressions=rnd.randint(20, 90) * weight,
                    impressions_sponsored=rnd.randint(250, 400) if sponsored else 0,
                    profile_visits=rnd.randint(2, 14) * weight + (8 if sponsored else 0),
                    likes_received=rnd.randint(0, 3) * weight,
                    connections=rnd.randint(0, 1),
                    opportunities=1 if rnd.random() < 0.08 * weight else 0,
                )
            )


async def _support(w: World) -> None:
    o = w.orgs
    w.session.add(
        Report(
            source_org_id=o["andrade"].id,
            target_org_id=o["prime"].id,
            actor_user_id=w.owners["andrade"].id,
            reason="Informação falsa no perfil",
            details="O perfil cita clientes que não confirmam a parceria.",
            created_at=w.ago(2),
        )
    )
    w.session.add(
        Report(
            source_org_id=o["central"].id,
            target_org_id=o["rotasul"].id,
            actor_user_id=w.owners["central"].id,
            reason="Contato insistente",
            details="Várias mensagens por dia depois de recusada a proposta.",
            created_at=w.ago(1),
        )
    )
    w.session.add(
        Report(
            source_org_id=o["conecta"].id,
            target_org_id=o["rotasul"].id,
            reason="Match falso",
            details="Interesse registrado sem relação com o que vendemos.",
            created_at=w.ago(3),
        )
    )
    w.session.add(
        OrgBlock(
            source_org_id=o["plastimax"].id,
            target_org_id=o["central"].id,
            actor_user_id=w.owners["plastimax"].id,
            created_at=w.ago(1),
        )
    )
    for key, name, local, days in (
        ("andrade", "Felipe Moraes", "felipe.moraes", 3),
        ("metaltech", "Sandra Vieira", "sandra.vieira", 10),
    ):
        w.session.add(
            AccessRequest(
                org_id=o[key].id,
                email=f"{local}@{DOMAIN}",
                full_name=name,
                job_title="Comprador",
                created_at=w.ago(days),
            )
        )
    w.session.add(
        AuditLog(
            org_id=o["central"].id,
            action="access.denied",
            target_type="organization",
            target_id=str(o["horizonte"].id),
            data={"path": "/api/v1/organizations/…", "reason": "cross_org"},
            created_at=w.ago(2),
        )
    )
    for i, status in enumerate(("failed", "failed", "dead", "done", "done")):
        w.session.add(
            AIJob(
                org_id=o["andrade"].id,
                agent="ProcurementAgent",
                status=status,
                attempts=3 if status == "dead" else 1,
                error="timeout" if status != "done" else "",
                prompt_version="v1",
                latency_ms=9_700,
                created_at=w.ago(hours=2 + i),
            )
        )


async def _mail(w: World) -> None:
    rnd = random.Random(7)
    keys = [
        "like.buy_interest",
        "match.confirmed",
        "message.new",
        "billing.payment_failed",
        "invite.reminder",
        "billing.payment_succeeded",
        "connection.accepted",
    ]
    users = list(w.users.values())
    for i in range(24):
        user = users[i % len(users)]
        sent = w.ago(hours=rnd.uniform(0.2, 24 * 20))
        key = keys[i % len(keys)]
        w.session.add(
            EmailMessage(
                template_key=key,
                user_id=user.id,
                to_email=user.email,
                subject=f"[demo] {key}",
                variables={"primeiro_nome": user.full_name.split()[0], "_body_md": "Demo."},
                token=secrets.token_urlsafe(24),
                status="sent",
                attempts=1,
                sent_at=sent,
                opened_at=sent + timedelta(minutes=30) if rnd.random() < 0.6 else None,
                created_at=sent,
            )
        )


# ------------------------------------------------------------------ entry point


DEMO_IMAGES = Path(__file__).resolve().parents[4] / "imagens" / "home"
SECTOR_COVERS = {
    "industria": ["06_industria.jpg", "09_automacao_industrial.jpg", "05_empresa_edificio.jpg"],
    "logistica": ["07_armazem_logistica.jpg", "08_transporte.jpg"],
    "tecnologia": ["09_automacao_industrial.jpg"],
    "varejo": ["07_armazem_logistica.jpg", "05_empresa_edificio.jpg"],
    "servicos": [
        "01_reuniao_empresarial.jpg",
        "10_parceria_handshake.jpg",
        "03_jantar_networking.jpg",
    ],
}
EVENT_IMAGES = {
    "jantar": "03_jantar_networking.jpg",
    "rodada": "02_networking_executivo.jpg",
    "cafe": "01_reuniao_empresarial.jpg",
}


async def _presentation(w: World, org: Organization) -> None:
    from app.modules.admin.demo_pdf import presentation_pdf
    from app.modules.catalog.models import Offer
    from app.modules.media import service as media

    offers = [
        o.name
        for o in (await w.session.execute(select(Offer).where(Offer.org_id == org.id))).scalars()
    ]
    pdf = presentation_pdf(org.display_name, org.segment, org.city, org.description, offers)
    await media.save_presentation(org, pdf, f"Apresentacao {org.display_name}.pdf")


async def _images(w: World) -> str:
    """Upload covers and event photos to the bucket (vip/<company-slug>/cover/...,
    vip/vip-network/event/...), like a real company would through the profile screen."""
    from app.modules.media import service as media

    if not DEMO_IMAGES.is_dir():
        return "Imagens de exemplo: pasta imagens/home não encontrada (sem capas)."
    try:
        used: dict[str, int] = {}
        for org in w.orgs.values():
            options = SECTOR_COVERS.get(org.sector) or SECTOR_COVERS["servicos"]
            n = used.get(org.sector, 0)
            used[org.sector] = n + 1
            data = (DEMO_IMAGES / options[n % len(options)]).read_bytes()
            org.cover_url = (await media.save_company_image(org.slug, "cover", data))["url"]
            from app.modules.admin.demo_pdf import logo_png
            from app.modules.organizations.views import initials

            logo = logo_png(org.display_name, initials(org.display_name), org.color)
            org.logo_url = (await media.save_company_image(org.slug, "logo", logo))["url"]
            await _presentation(w, org)
        events = (await w.session.execute(select(Event).where(Event.slug.like("demo-%")))).scalars()
        for ev in events:
            name = EVENT_IMAGES.get(ev.kind, "02_networking_executivo.jpg")
            ev.image_url = (
                await media.save_platform_image("event", (DEMO_IMAGES / name).read_bytes())
            )["url"]
    except Exception as exc:  # noqa: BLE001 - storage down must not break the demo
        return f"Imagens de exemplo: não enviadas ({exc.__class__.__name__}: {exc})."
    return (
        f"Arquivos de exemplo enviados ao bucket: {len(w.orgs)} logos, {len(w.orgs)} capas, {len(w.orgs)} apresentações "
        "em PDF e as fotos dos eventos."
    )


async def run(session: AsyncSession) -> list[str]:
    if get_settings().env == "prod":
        return ["Dados de exemplo recusados em produção."]
    random.seed(2026)
    await clear(session)
    w = World(session=session, now=datetime.now(UTC), password_hash=hash_password(PASSWORD))
    await _orgs(w)
    await _needs(w)
    await _subscriptions(w)
    await _invites(w)
    matches = await _likes_matches(w)
    opps = await _opportunities(w, matches)
    await _conversations(w, opps)
    await _events(w)
    await _billing_extras(w)
    await _stats(w)
    images = await _images(w)
    # the cards a company really gets (economy with the savings math, suppliers, buyers, partners)
    from app.modules.intelligence import engine

    await w.session.flush()
    for org in w.orgs.values():
        await engine.refresh_for(w.session, org.id)
    await _support(w)
    await _mail(w)
    await _user(w, None, "Equipe VIP Network (demo)", "admin", kind="admin", admin_role="owner")
    await session.flush()
    return [
        f"Dados de exemplo: {len(w.orgs)} empresas, {len(w.users)} usuários (senha {PASSWORD}).",
        f"  Empresa (Andrade Embalagens, VIP): marina@{DOMAIN} / {PASSWORD}",
        f"  Compras da Andrade: joao@{DOMAIN} · Comercial: renata@{DOMAIN}",
        f"  Outras empresas: <responsável>@{DOMAIN}, ex. ricardo.horizonte@{DOMAIN}",
        f"  Painel da equipe (proprietário): {ADMIN_EMAIL} / {PASSWORD}",
        images,
    ]
