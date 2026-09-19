"""SQLAlchemy canonical models. Import this module to populate metadata."""

from __future__ import annotations

from mira.core.models.agents import AgentRun, AgentTask
from mira.core.models.audit import AuditEvent
from mira.core.models.base import Base
from mira.core.models.control import (
    Approval,
    Decision,
    Evidence,
    EvidenceReferenceRow,
    Finding,
    Incident,
    IncidentFinding,
    RiskAssessment,
)
from mira.core.models.documents import Contract, Document, Policy
from mira.core.models.intel import (
    ExternalSignal,
    Forecast,
    Metric,
    Precedent,
    ReconciliationCase,
    SavingsEvent,
)
from mira.core.models.ledger import Account, LedgerEntry, Transaction
from mira.core.models.party import Company, Customer, Employee, User, Vendor
from mira.core.models.procure import (
    Budget,
    BudgetLine,
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceLine,
    Payment,
    PurchaseOrder,
    PurchaseOrderLine,
)

CANONICAL_MODELS = (
    Company,
    User,
    Employee,
    Vendor,
    Customer,
    Account,
    Invoice,
    InvoiceLine,
    PurchaseOrder,
    GoodsReceipt,
    Transaction,
    LedgerEntry,
    Contract,
    Policy,
    Approval,
    Evidence,
    Finding,
    Incident,
    RiskAssessment,
    Decision,
    AgentTask,
    AgentRun,
    Precedent,
    Forecast,
    Metric,
)

__all__ = [
    "Base",
    "CANONICAL_MODELS",
    "Company",
    "User",
    "Employee",
    "Vendor",
    "Customer",
    "Account",
    "Invoice",
    "InvoiceLine",
    "PurchaseOrder",
    "PurchaseOrderLine",
    "GoodsReceipt",
    "GoodsReceiptLine",
    "Transaction",
    "LedgerEntry",
    "Contract",
    "Policy",
    "Approval",
    "Evidence",
    "EvidenceReferenceRow",
    "Finding",
    "Incident",
    "IncidentFinding",
    "RiskAssessment",
    "Decision",
    "AgentTask",
    "AgentRun",
    "Precedent",
    "Forecast",
    "Metric",
    "Budget",
    "BudgetLine",
    "Payment",
    "SavingsEvent",
    "ExternalSignal",
    "ReconciliationCase",
    "Document",
    "AuditEvent",
]
