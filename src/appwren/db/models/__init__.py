"""Every ORM model. Importing this package registers them all on ``Base.metadata``."""

from __future__ import annotations

from appwren.db.models.assessment import (
    Assessment,
    PortfolioSnapshot,
    Questionnaire,
    ScoreSnapshot,
    ScoringModel,
)
from appwren.db.models.decision import Decision
from appwren.db.models.inventory import (
    Application,
    ApplicationCapability,
    ApplicationUnit,
    Capability,
    Component,
    ComponentTechnology,
    ExternalRef,
    RecordLink,
    RecordOwner,
    Technology,
    TechnologyRelease,
    Vendor,
)
from appwren.db.models.landscape import Interface
from appwren.db.models.people import (
    Account,
    Credential,
    FailedSignIn,
    Identity,
    Membership,
    OrgUnit,
    ProviderMapping,
    RoleGrant,
    SessionToken,
    SignInRequest,
)
from appwren.db.models.program import Setting
from appwren.db.models.system import ChainHead, Counter, Event

__all__ = [
    "Account",
    "Application",
    "ApplicationCapability",
    "ApplicationUnit",
    "Assessment",
    "Capability",
    "ChainHead",
    "Component",
    "ComponentTechnology",
    "Counter",
    "Credential",
    "Decision",
    "Event",
    "ExternalRef",
    "FailedSignIn",
    "Identity",
    "Interface",
    "Membership",
    "OrgUnit",
    "PortfolioSnapshot",
    "ProviderMapping",
    "Questionnaire",
    "RecordLink",
    "RecordOwner",
    "RoleGrant",
    "ScoreSnapshot",
    "ScoringModel",
    "SessionToken",
    "Setting",
    "SignInRequest",
    "Technology",
    "TechnologyRelease",
    "Vendor",
]
