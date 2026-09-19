"""Canonical enumerations. Keep these stable — they are persisted as strings."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    CFO = "cfo"
    CONTROLLER = "controller"
    AP = "ap"
    EXECUTIVE = "executive"
    AUDITOR = "auditor"


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"


class PartyStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    PENDING = "pending"


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    WATCH = "watch"


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class TransactionSource(StrEnum):
    BANK = "bank"
    CARD = "card"
    SANDBOX = "sandbox"
    MANUAL = "manual"
    SEED = "seed"


class InvoiceDirection(StrEnum):
    AP = "ap"
    AR = "ar"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    RECEIVED = "received"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    PAID = "paid"
    VOID = "void"


class POStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    AWAITING_APPROVAL = "awaiting_approval"


class ReceiptStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    VOID = "void"


class PaymentMethod(StrEnum):
    ACH = "ach"
    WIRE = "wire"
    CHECK = "check"
    CARD = "card"
    VISA_SANDBOX = "visa_sandbox"
    MANUAL = "manual"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    SETTLED = "settled"
    FAILED = "failed"
    VOID = "void"


class StorageBackend(StrEnum):
    LOCAL = "local"
    DROPBOX = "dropbox"


class DocumentClass(StrEnum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    STATEMENT = "statement"
    POLICY = "policy"
    OTHER = "other"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    FAILED = "failed"
    SKIPPED = "skipped"


class ContractStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class PolicyType(StrEnum):
    SPEND = "spend"
    APPROVAL = "approval"
    VENDOR = "vendor"
    TREASURY = "treasury"
    DATA = "data"


class PolicyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    AWAITING_HUMAN = "awaiting_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    SUPERSEDED = "superseded"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MetricSource(StrEnum):
    COMPUTED = "computed"
    EXTERNAL = "external"
    SEED = "seed"


class SavingsCategory(StrEnum):
    DUPLICATE_PREVENTED = "duplicate_prevented"
    POLICY_BLOCK = "policy_block"
    EARLY_PAY_DISCOUNT = "early_pay_discount"
    INTAKE_HOURS = "intake_hours"
    OTHER = "other"


class ActorType(StrEnum):
    USER = "user"
    MIRA = "mira"
    AGENT = "agent"
    SYSTEM = "system"
    ZENNI = "zenni"
    VOICE = "voice"


class AgentRole(StrEnum):
    MIRA_CFO = "mira_cfo"
    CONTROLLER = "controller"
    ACCOUNTS_PAYABLE = "accounts_payable"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    TREASURY = "treasury"
    PROCUREMENT = "procurement"
    AUDIT = "audit"
    FPNA = "fpna"
    POLICY = "policy"
    EVIDENCE = "evidence"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class ReconciliationStatus(StrEnum):
    OPEN = "open"
    MATCHED = "matched"
    EXCEPTION = "exception"
    CLOSED = "closed"


class EvidenceRole(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    POLICY_BASIS = "policy_basis"
    AUTHORITY_BASIS = "authority_basis"
