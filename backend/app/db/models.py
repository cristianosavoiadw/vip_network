"""Imports every model so Alembic autogenerate sees the whole metadata."""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.auth.models import AuthToken, RefreshToken, User
from app.modules.billing.models import Invoice, Purchase, StripeEvent, Subscription, TrialClaim
from app.modules.boosts.models import BoostCampaign, OrgDayStat
from app.modules.catalog.models import Offer, PurchaseNeed
from app.modules.connections.models import Connection
from app.modules.discovery.models import DiscoveryAction, OrgBlock, Report, SavedOrg
from app.modules.events.models import Event, EventRegistration
from app.modules.integrations.cnpj.models import CnpjRecord
from app.modules.intelligence.models import MarketReport, Recommendation
from app.modules.invites.models import Invite
from app.modules.likes.models import Like
from app.modules.mail.models import EmailCampaign, EmailMessage, EmailSuppression, EmailTemplate
from app.modules.matches.models import Match
from app.modules.mentorship.models import (
    Mentor,
    MentorshipDocument,
    MentorshipPlan,
    MentorshipSession,
)
from app.modules.messaging.models import Conversation, ConversationRead, Message
from app.modules.notifications.models import Notification
from app.modules.opportunities.models import Opportunity, OpportunityNote
from app.modules.organizations.models import AccessRequest, AiSuggestion, Department, Organization
from app.modules.settings.models import PlatformSetting
from app.modules.weos.models import AIJob

__all__ = [
    "AIJob",
    "AccessRequest",
    "AiSuggestion",
    "AuditLog",
    "AuthToken",
    "Base",
    "BoostCampaign",
    "CnpjRecord",
    "Connection",
    "Conversation",
    "ConversationRead",
    "Department",
    "DiscoveryAction",
    "EmailCampaign",
    "EmailMessage",
    "EmailSuppression",
    "EmailTemplate",
    "Event",
    "EventRegistration",
    "Invite",
    "Invoice",
    "Like",
    "MarketReport",
    "Match",
    "Mentor",
    "MentorshipDocument",
    "MentorshipPlan",
    "MentorshipSession",
    "Message",
    "Notification",
    "Offer",
    "Opportunity",
    "OpportunityNote",
    "OrgBlock",
    "OrgDayStat",
    "Organization",
    "PlatformSetting",
    "Purchase",
    "PurchaseNeed",
    "Recommendation",
    "RefreshToken",
    "Report",
    "SavedOrg",
    "StripeEvent",
    "Subscription",
    "TrialClaim",
    "User",
]
