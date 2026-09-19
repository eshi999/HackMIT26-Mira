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
    AWAITING_HUMAN = "awaiting_human"


class PrecedentStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


class OfficeEventType(StrEnum):
    INVOICE_RECEIVED = "invoice_received"
    BANK_FEED_UPDATED = "bank_feed_updated"
    PAYMENT_RECEIVED = "payment_received"
    PURCHASE_REQUESTED = "purchase_requested"
    MONTH_END_STARTED = "month_end_started"
    CLOSE_DEADLINE_APPROACHING = "close_deadline_approaching"
    DOCUMENT_INGESTED = "document_ingested"
    HUMAN_FEEDBACK_RECEIVED = "human_feedback_received"


class OfficeEventStatus(StrEnum):
    RECEIVED = "received"
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    AWAITING_HUMAN = "awaiting_human"
    FAILED = "failed"


class AuthorityDisposition(StrEnum):
    AUTO_COMPLETE = "auto_complete"
    ESCALATE = "escalate"
    BLOCK = "block"


class SavingsSource(StrEnum):
    SEED = "seed"
    RUNTIME = "runtime"


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


class FindingType(StrEnum):
    DUPLICATE_INVOICE = "duplicate_invoice"
    DUPLICATE_PAYMENT = "duplicate_payment"
    INVOICE_PO_MISMATCH = "invoice_po_mismatch"
    INVOICE_GR_MISMATCH = "invoice_gr_mismatch"
    MISSING_PURCHASE_ORDER = "missing_purchase_order"
    NEW_VENDOR = "new_vendor"
    VENDOR_BANK_DETAIL_CHANGE = "vendor_bank_detail_change"
    UNUSUAL_VENDOR_AMOUNT = "unusual_vendor_amount"
    SELF_APPROVED_REQUEST = "self_approved_request"
    APPROVAL_AUTHORITY_EXCEEDED = "approval_authority_exceeded"
    MISSING_SUPPORTING_DOCUMENT = "missing_supporting_document"
    CLOSED_PERIOD_POSTING = "closed_period_posting"
    ABNORMAL_TRANSACTION_TIMING = "abnormal_transaction_timing"
    CONTRACT_PRICING_VIOLATION = "contract_pricing_violation"
    SUSPICIOUS_ROUND_NUMBER_PAYMENT = "suspicious_round_number_payment"
    PREVIOUSLY_FLAGGED_VENDOR = "previously_flagged_vendor"
    UNEXPECTED_RECURRING_SUBSCRIPTION = "unexpected_recurring_subscription"
    OVERDUE_RECEIVABLE = "overdue_receivable"
    UNUSED_RECURRING_CHARGE = "unused_recurring_charge"


class MatchStatus(StrEnum):
    MATCH = "MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    MISMATCH = "MISMATCH"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"


class ReconStage(StrEnum):
    EXACT_ONE_TO_ONE = "exact_one_to_one"
    NORMALIZED_REFERENCE = "normalized_reference"
    AMOUNT_DATE_FUZZY = "amount_date_fuzzy"
    ONE_TO_MANY = "one_to_many"
    FEE_ADJUSTED = "fee_adjusted"
    REFUND_CHARGEBACK = "refund_chargeback"
    UNRESOLVED = "unresolved"


class RecommendedAction(StrEnum):
    BLOCK_PAYMENT = "BLOCK_PAYMENT"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"
    REVERSE_APPROVAL = "REVERSE_APPROVAL"
    REQUIRE_SECONDARY_APPROVAL = "REQUIRE_SECONDARY_APPROVAL"
    REJECT_POSTING = "REJECT_POSTING"
    ESCALATE_TO_CFO = "ESCALATE_TO_CFO"
    INVESTIGATE_BANK_CHANGE = "INVESTIGATE_BANK_CHANGE"
    REVIEW_CONTRACT_PRICING = "REVIEW_CONTRACT_PRICING"
    COLLECT_RECEIVABLE = "COLLECT_RECEIVABLE"
    CANCEL_SUBSCRIPTION = "CANCEL_SUBSCRIPTION"
    OBTAIN_RECEIPT = "OBTAIN_RECEIPT"
    OBTAIN_PO = "OBTAIN_PO"
    NO_FORCED_MATCH = "NO_FORCED_MATCH"
    REVIEW_DUPLICATE_REFUND = "REVIEW_DUPLICATE_REFUND"
