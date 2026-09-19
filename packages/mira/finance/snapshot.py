"""In-memory company picture for deterministic engines.

Engines never query ad hoc during scoring. Load once, then calculate.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from mira.core.models import (
    Approval,
    Contract,
    Customer,
    Decision,
    Document,
    Employee,
    Evidence,
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceLine,
    Payment,
    Policy,
    Precedent,
    PurchaseOrder,
    PurchaseOrderLine,
    RecurringSubscription,
    SavingsEvent,
    Transaction,
    User,
    Vendor,
)


class LineView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    purchase_order_line_id: UUID | None = None


class VendorView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    risk_tier: str
    status: str
    is_preferred: bool
    onboarded_at: date | None = None
    bank_account_ref: str | None = None
    previous_bank_account_ref: str | None = None
    bank_changed_at: datetime | None = None
    payment_terms: str | None = None


class CustomerView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    payment_terms: str | None = None


class EmployeeView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    user_id: UUID | None
    full_name: str
    title: str
    approval_limit: Decimal | None = None


class UserView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    full_name: str
    role: str
    employee_id: UUID | None = None
    approval_limit: Decimal | None = None


class InvoiceView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    vendor_id: UUID | None
    customer_id: UUID | None
    invoice_number: str
    direction: str
    issue_date: date
    due_date: date | None
    total: Decimal
    subtotal: Decimal
    currency: str
    status: str
    purchase_order_id: UUID | None
    document_id: UUID | None
    requested_by_user_id: UUID | None = None
    approved_by_user_id: UUID | None = None
    posted_period: str | None = None
    is_duplicate_suspect: bool = False
    lines: tuple[LineView, ...] = ()


class PurchaseOrderView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    vendor_id: UUID
    po_number: str
    status: str
    total: Decimal
    requested_by_user_id: UUID | None
    needed_by: date | None = None
    lines: tuple[LineView, ...] = ()


class GoodsReceiptView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    purchase_order_id: UUID
    received_at: datetime
    status: str
    lines: tuple[LineView, ...] = ()


class PaymentView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    invoice_id: UUID | None
    amount: Decimal
    currency: str
    method: str
    status: str
    paid_at: datetime | None
    transaction_id: UUID | None
    processor_ref: str | None = None
    is_sandbox: bool = True


class TransactionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    account_id: UUID
    vendor_id: UUID | None
    customer_id: UUID | None
    amount: Decimal
    currency: str
    posted_at: datetime
    description: str
    source: str
    external_ref: str | None = None
    is_sandbox: bool = False


class ContractView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    vendor_id: UUID | None
    title: str
    start_date: date | None
    end_date: date | None
    value: Decimal | None
    currency: str
    status: str
    extracted_terms: dict = Field(default_factory=dict)


class PolicyView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    policy_type: str
    version: str
    body: str
    rules: dict = Field(default_factory=dict)
    status: str


class ApprovalView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    subject_type: str
    subject_id: UUID
    requested_by_user_id: UUID | None
    approver_user_id: UUID | None
    status: str
    decision_id: UUID | None = None
    comment: str | None = None


class SubscriptionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    vendor_id: UUID
    name: str
    expected_amount: Decimal
    cadence: str
    is_in_use: bool
    start_date: date | None = None
    cancelled_at: date | None = None


class PrecedentView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    situation_hash: str
    summary: str
    outcome: str
    reusable_rule: str | None = None
    period: str


class EvidenceView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    evidence_type: str
    source_system: str
    title: str
    snippet: str | None = None
    uri: str | None = None


class DocumentView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    filename: str
    document_class: str
    storage_uri: str


class DecisionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    decision_type: str
    status: str
    action: str
    requires_human_approval: bool
    confidence_score: Decimal
    risk_level: str
    dollars_impact: Decimal | None = None
    hours_saved_estimate: Decimal | None = None
    subject_type: str | None = None
    subject_id: UUID | None = None


class SavingsView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    category: str
    amount_usd: Decimal
    hours_saved: Decimal
    workflow: str
    period: str


class FinanceSnapshot(BaseModel):
    """Frozen company picture. Engines calculate against this, not against live ORM identity."""

    model_config = ConfigDict(frozen=True)

    company_id: UUID
    as_of: date
    vendors: tuple[VendorView, ...] = ()
    customers: tuple[CustomerView, ...] = ()
    users: tuple[UserView, ...] = ()
    employees: tuple[EmployeeView, ...] = ()
    invoices: tuple[InvoiceView, ...] = ()
    purchase_orders: tuple[PurchaseOrderView, ...] = ()
    receipts: tuple[GoodsReceiptView, ...] = ()
    payments: tuple[PaymentView, ...] = ()
    transactions: tuple[TransactionView, ...] = ()
    contracts: tuple[ContractView, ...] = ()
    policies: tuple[PolicyView, ...] = ()
    approvals: tuple[ApprovalView, ...] = ()
    subscriptions: tuple[SubscriptionView, ...] = ()
    precedents: tuple[PrecedentView, ...] = ()
    evidence: tuple[EvidenceView, ...] = ()
    documents: tuple[DocumentView, ...] = ()
    decisions: tuple[DecisionView, ...] = ()
    savings: tuple[SavingsView, ...] = ()

    def vendor(self, vendor_id: UUID | None) -> VendorView | None:
        if vendor_id is None:
            return None
        return next((row for row in self.vendors if row.id == vendor_id), None)

    def invoice(self, invoice_id: UUID) -> InvoiceView | None:
        return next((row for row in self.invoices if row.id == invoice_id), None)

    def purchase_order(self, po_id: UUID | None) -> PurchaseOrderView | None:
        if po_id is None:
            return None
        return next((row for row in self.purchase_orders if row.id == po_id), None)

    def receipts_for_po(self, po_id: UUID) -> tuple[GoodsReceiptView, ...]:
        return tuple(row for row in self.receipts if row.purchase_order_id == po_id)

    def user(self, user_id: UUID | None) -> UserView | None:
        if user_id is None:
            return None
        return next((row for row in self.users if row.id == user_id), None)

    def active_policies(self) -> tuple[PolicyView, ...]:
        return tuple(row for row in self.policies if row.status == "active")

    def ap_invoices(self) -> tuple[InvoiceView, ...]:
        return tuple(row for row in self.invoices if row.direction == "ap")

    def ar_invoices(self) -> tuple[InvoiceView, ...]:
        return tuple(row for row in self.invoices if row.direction == "ar")

    def bank_transactions(self) -> tuple[TransactionView, ...]:
        return tuple(row for row in self.transactions if row.source == "bank")

    def merged_rules(self) -> dict:
        merged: dict = {}
        for policy in self.active_policies():
            merged.update(policy.rules or {})
        return merged


def load_snapshot(session: Session, company_id: UUID, as_of: date) -> FinanceSnapshot:
    vendors = session.query(Vendor).filter(Vendor.company_id == company_id).all()
    customers = session.query(Customer).filter(Customer.company_id == company_id).all()
    users = session.query(User).filter(User.company_id == company_id).all()
    employees = session.query(Employee).filter(Employee.company_id == company_id).all()
    invoices = session.query(Invoice).filter(Invoice.company_id == company_id).all()
    invoice_lines = session.query(InvoiceLine).filter(InvoiceLine.company_id == company_id).all()
    pos = session.query(PurchaseOrder).filter(PurchaseOrder.company_id == company_id).all()
    po_lines = session.query(PurchaseOrderLine).filter(PurchaseOrderLine.company_id == company_id).all()
    receipts = session.query(GoodsReceipt).filter(GoodsReceipt.company_id == company_id).all()
    gr_lines = session.query(GoodsReceiptLine).filter(GoodsReceiptLine.company_id == company_id).all()
    payments = session.query(Payment).filter(Payment.company_id == company_id).all()
    txns = session.query(Transaction).filter(Transaction.company_id == company_id).all()
    contracts = session.query(Contract).filter(Contract.company_id == company_id).all()
    policies = session.query(Policy).filter(Policy.company_id == company_id).all()
    approvals = session.query(Approval).filter(Approval.company_id == company_id).all()
    subs = session.query(RecurringSubscription).filter(RecurringSubscription.company_id == company_id).all()
    precedents = session.query(Precedent).filter(Precedent.company_id == company_id).all()
    evidence = session.query(Evidence).filter(Evidence.company_id == company_id).all()
    documents = session.query(Document).filter(Document.company_id == company_id).all()
    decisions = session.query(Decision).filter(Decision.company_id == company_id).all()
    savings = session.query(SavingsEvent).filter(SavingsEvent.company_id == company_id).all()

    lines_by_invoice: dict[UUID, list[LineView]] = {}
    for line in invoice_lines:
        lines_by_invoice.setdefault(line.invoice_id, []).append(
            LineView(
                id=line.id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                amount=line.amount,
            )
        )
    lines_by_po: dict[UUID, list[LineView]] = {}
    for line in po_lines:
        lines_by_po.setdefault(line.purchase_order_id, []).append(
            LineView(
                id=line.id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                amount=line.amount,
            )
        )
    lines_by_gr: dict[UUID, list[LineView]] = {}
    for line in gr_lines:
        lines_by_gr.setdefault(line.goods_receipt_id, []).append(
            LineView(
                id=line.id,
                description=line.description,
                quantity=line.quantity,
                purchase_order_line_id=line.purchase_order_line_id,
            )
        )

    emp_by_user = {row.user_id: row for row in employees if row.user_id is not None}

    return FinanceSnapshot(
        company_id=company_id,
        as_of=as_of,
        vendors=tuple(
            VendorView(
                id=row.id,
                name=row.name,
                risk_tier=row.risk_tier,
                status=row.status,
                is_preferred=row.is_preferred,
                onboarded_at=row.onboarded_at,
                bank_account_ref=row.bank_account_ref,
                previous_bank_account_ref=row.previous_bank_account_ref,
                bank_changed_at=row.bank_changed_at,
                payment_terms=row.payment_terms,
            )
            for row in vendors
        ),
        customers=tuple(
            CustomerView(id=row.id, name=row.name, payment_terms=row.payment_terms) for row in customers
        ),
        users=tuple(
            UserView(
                id=row.id,
                full_name=row.full_name,
                role=row.role,
                employee_id=emp_by_user[row.id].id if row.id in emp_by_user else None,
                approval_limit=emp_by_user[row.id].approval_limit if row.id in emp_by_user else None,
            )
            for row in users
        ),
        employees=tuple(
            EmployeeView(
                id=row.id,
                user_id=row.user_id,
                full_name=row.full_name,
                title=row.title,
                approval_limit=row.approval_limit,
            )
            for row in employees
        ),
        invoices=tuple(
            InvoiceView(
                id=row.id,
                vendor_id=row.vendor_id,
                customer_id=row.customer_id,
                invoice_number=row.invoice_number,
                direction=row.direction,
                issue_date=row.issue_date,
                due_date=row.due_date,
                total=row.total,
                subtotal=row.subtotal,
                currency=row.currency,
                status=row.status,
                purchase_order_id=row.purchase_order_id,
                document_id=row.document_id,
                requested_by_user_id=row.requested_by_user_id,
                approved_by_user_id=row.approved_by_user_id,
                posted_period=row.posted_period,
                is_duplicate_suspect=row.is_duplicate_suspect,
                lines=tuple(lines_by_invoice.get(row.id, ())),
            )
            for row in invoices
        ),
        purchase_orders=tuple(
            PurchaseOrderView(
                id=row.id,
                vendor_id=row.vendor_id,
                po_number=row.po_number,
                status=row.status,
                total=row.total,
                requested_by_user_id=row.requested_by_user_id,
                needed_by=row.needed_by,
                lines=tuple(lines_by_po.get(row.id, ())),
            )
            for row in pos
        ),
        receipts=tuple(
            GoodsReceiptView(
                id=row.id,
                purchase_order_id=row.purchase_order_id,
                received_at=row.received_at,
                status=row.status,
                lines=tuple(lines_by_gr.get(row.id, ())),
            )
            for row in receipts
        ),
        payments=tuple(
            PaymentView(
                id=row.id,
                invoice_id=row.invoice_id,
                amount=row.amount,
                currency=row.currency,
                method=row.method,
                status=row.status,
                paid_at=row.paid_at,
                transaction_id=row.transaction_id,
                processor_ref=row.processor_ref,
                is_sandbox=row.is_sandbox,
            )
            for row in payments
        ),
        transactions=tuple(
            TransactionView(
                id=row.id,
                account_id=row.account_id,
                vendor_id=row.vendor_id,
                customer_id=row.customer_id,
                amount=row.amount,
                currency=row.currency,
                posted_at=row.posted_at,
                description=row.description,
                source=row.source,
                external_ref=row.external_ref,
                is_sandbox=row.is_sandbox,
            )
            for row in txns
        ),
        contracts=tuple(
            ContractView(
                id=row.id,
                vendor_id=row.vendor_id,
                title=row.title,
                start_date=row.start_date,
                end_date=row.end_date,
                value=row.value,
                currency=row.currency,
                status=row.status,
                extracted_terms=row.extracted_terms or {},
            )
            for row in contracts
        ),
        policies=tuple(
            PolicyView(
                id=row.id,
                name=row.name,
                policy_type=row.policy_type,
                version=row.version,
                body=row.body,
                rules=row.rules or {},
                status=row.status,
            )
            for row in policies
        ),
        approvals=tuple(
            ApprovalView(
                id=row.id,
                subject_type=row.subject_type,
                subject_id=row.subject_id,
                requested_by_user_id=row.requested_by_user_id,
                approver_user_id=row.approver_user_id,
                status=row.status,
                decision_id=row.decision_id,
                comment=row.comment,
            )
            for row in approvals
        ),
        subscriptions=tuple(
            SubscriptionView(
                id=row.id,
                vendor_id=row.vendor_id,
                name=row.name,
                expected_amount=row.expected_amount,
                cadence=row.cadence,
                is_in_use=row.is_in_use,
                start_date=row.start_date,
                cancelled_at=row.cancelled_at,
            )
            for row in subs
        ),
        precedents=tuple(
            PrecedentView(
                id=row.id,
                situation_hash=row.situation_hash,
                summary=row.summary,
                outcome=row.outcome,
                reusable_rule=row.reusable_rule,
                period=row.period,
            )
            for row in precedents
        ),
        evidence=tuple(
            EvidenceView(
                id=row.id,
                evidence_type=row.evidence_type,
                source_system=row.source_system,
                title=row.title,
                snippet=row.snippet,
                uri=row.uri,
            )
            for row in evidence
        ),
        documents=tuple(
            DocumentView(
                id=row.id,
                filename=row.filename,
                document_class=row.document_class,
                storage_uri=row.storage_uri,
            )
            for row in documents
        ),
        decisions=tuple(
            DecisionView(
                id=row.id,
                decision_type=row.decision_type,
                status=row.status,
                action=row.action,
                requires_human_approval=row.requires_human_approval,
                confidence_score=row.confidence_score,
                risk_level=row.risk_level,
                dollars_impact=row.dollars_impact,
                hours_saved_estimate=row.hours_saved_estimate,
                subject_type=row.subject_type,
                subject_id=row.subject_id,
            )
            for row in decisions
        ),
        savings=tuple(
            SavingsView(
                id=row.id,
                category=row.category,
                amount_usd=row.amount_usd,
                hours_saved=row.hours_saved,
                workflow=row.workflow,
                period=row.period,
            )
            for row in savings
        ),
    )
