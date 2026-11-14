"""Serializers shared by routes of several modules (company cards, public profile, me)."""

from __future__ import annotations

from typing import Any

from app.modules.auth.models import User
from app.modules.billing.entitlement import entitled, state_label
from app.modules.billing.models import Subscription
from app.modules.organizations import permissions
from app.modules.organizations.models import Organization


def iso(dt: Any) -> str | None:
    return dt.isoformat() if dt else None


def initials(name: str) -> str:
    words = [w for w in name.replace("&", " ").split() if len(w) > 2 or w[:1].isupper()]
    return ("".join(w[0] for w in words[:2]) or name[:2]).upper()


def org_card(org: Organization) -> dict[str, Any]:
    """The minimum to draw a company anywhere (lists, chips, chat)."""
    return {
        "id": str(org.id),
        "slug": org.slug,
        "name": org.display_name,
        "initials": initials(org.display_name),
        "color": org.color,
        "logo_url": org.logo_url,
        "cover_url": org.cover_url,
        "segment": org.segment,
        "sector": org.sector,
        "city": org.city,
        "state": org.state,
        "verified": org.verified,
    }


def org_public(org: Organization) -> dict[str, Any]:
    """Public profile (§5.1). Never includes purchases, suppliers or anything private."""
    return {
        **org_card(org),
        "description": org.description,
        "website": org.website,
        "coverage": org.coverage,
        "differentials": org.differentials,
        "certifications": org.certifications,
        "contacts": org.contacts,
        "cover_url": org.cover_url,
        "since": org.opened_on.year if org.opened_on else None,
        "presentation": {k: v for k, v in (org.presentation or {}).items() if k != "key"} or None,
    }


def org_private(org: Organization) -> dict[str, Any]:
    """The company's own view: public profile + official data + onboarding state."""
    return {
        **org_public(org),
        "cnpj": org.official.get("cnpj") if org.official else org.cnpj,
        "legal_name": org.legal_name,
        "official": org.official,
        "official_fetched_at": iso(org.official_fetched_at),
        "description_source": org.description_source,
        "goals": org.goals,
        "status": org.status,
        "entry": org.entry,
        "onboarding_step": org.onboarding_step,
        "onboarding_completed_at": iso(org.onboarding_completed_at),
        "discoverable": org.discoverable,
    }


def subscription_view(sub: Subscription | None) -> dict[str, Any] | None:
    if sub is None:
        return None
    return {
        "plan": sub.plan,
        "kind": sub.kind,
        "status": sub.status,
        "state": state_label(sub),
        "entitled": entitled(sub),
        "trial_start": iso(sub.trial_start),
        "trial_end": iso(sub.trial_end),
        "current_period_end": iso(sub.current_period_end),
        "cancel_at_period_end": sub.cancel_at_period_end,
        "canceled_at": iso(sub.canceled_at),
        "vip_until": iso(sub.vip_until),
        "vip_after": sub.vip_after,
        "card": {"brand": sub.card_brand, "last4": sub.card_last4, "exp": sub.card_exp}
        if sub.card_last4
        else None,
    }


def user_view(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "job_title": user.job_title,
        "phone": user.phone,
        "kind": user.kind,
        "status": user.status,
        "is_org_owner": user.is_org_owner,
        "departments": user.departments,
        "email_verified": user.email_verified_at is not None,
        "admin_role": user.admin_role or ("owner" if user.is_superuser else ""),
        "last_login_at": iso(user.last_login_at),
        "notification_prefs": user.notification_prefs or {},
    }


def me_view(user: User, org: Organization | None, sub: Subscription | None) -> dict[str, Any]:
    out: dict[str, Any] = {"user": user_view(user), "org": None, "subscription": None, "areas": []}
    if user.kind == "member" and org is not None:
        out["org"] = org_private(org)
        out["subscription"] = subscription_view(sub)
        out["areas"] = permissions.areas_for(user.departments, is_owner=user.is_org_owner)
    return out
