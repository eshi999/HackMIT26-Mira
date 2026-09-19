"""Phase 2 Northstar expansion: operating volume + planted scenarios with known answers."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from mira.core.enums import (
    AccountType,
    ApprovalStatus,
    ContractStatus,
    DocumentClass,
    ExtractionStatus,
    InvoiceDirection,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    PolicyStatus,
    PolicyType,
    POStatus,
    ReceiptStatus,
    RiskTier,
    StorageBackend,
    TransactionSource,
    UserRole,
)
from mira.core.models import (
    Account,
    Approval,
    Contract,
    Customer,
    Document,
    Employee,
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceLine,
    LedgerEntry,
    Payment,
    Policy,
    Precedent,
    PurchaseOrder,
    PurchaseOrderLine,
    RecurringSubscription,
    Transaction,
    User,
    Vendor,
)
from mira.seed import ids

AS_OF = datetime(2026, 9, 19, 7, 30, tzinfo=UTC)
AS_OF_DATE = date(2026, 9, 19)


def _dt(d: date, hour: int = 14, minute: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=UTC)


def _period(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _invoice(
    session: Session,
    *,
    id_,
    vendor_id=None,
    customer_id=None,
    number: str,
    direction: str,
    issue: date,
    due: date | None,
    total: Decimal,
    status: str,
    po_id=None,
    document_id=None,
    account_id=None,
    description: str,
    requested_by=None,
    approved_by=None,
    posted_period: str | None = None,
    duplicate: bool = False,
) -> Invoice:
    inv = Invoice(
        id=id_,
        company_id=ids.COMPANY,
        vendor_id=vendor_id,
        customer_id=customer_id,
        invoice_number=number,
        direction=direction,
        issue_date=issue,
        due_date=due,
        subtotal=total,
        total=total,
        status=status,
        purchase_order_id=po_id,
        document_id=document_id,
        requested_by_user_id=requested_by,
        approved_by_user_id=approved_by,
        posted_period=posted_period or _period(issue),
        is_duplicate_suspect=duplicate,
    )
    session.add(inv)
    session.add(
        InvoiceLine(
            company_id=ids.COMPANY,
            invoice_id=id_,
            description=description,
            quantity=Decimal("1"),
            unit_price=total,
            amount=total,
            account_id=account_id,
        )
    )
    session.flush()
    return inv


def _po(session: Session, *, id_, vendor_id, number: str, total: Decimal, requester, status: str, line_id=None, account_id=None, description: str, qty: Decimal = Decimal("1")) -> PurchaseOrder:
    po = PurchaseOrder(
        id=id_,
        company_id=ids.COMPANY,
        vendor_id=vendor_id,
        po_number=number,
        status=status,
        requested_by_user_id=requester,
        total=total,
    )
    session.add(po)
    session.add(
        PurchaseOrderLine(
            id=line_id or ids.filler("poline", int(id_.int % 10_000_000)),
            company_id=ids.COMPANY,
            purchase_order_id=id_,
            description=description,
            quantity=qty,
            unit_price=total / qty,
            amount=total,
            account_id=account_id,
        )
    )
    session.flush()
    return po


def _gr(session: Session, *, id_, po_id, line_id, qty: Decimal, description: str, received: datetime) -> GoodsReceipt:
    gr = GoodsReceipt(
        id=id_,
        company_id=ids.COMPANY,
        purchase_order_id=po_id,
        received_at=received,
        received_by_user_id=ids.SAM,
        status=ReceiptStatus.POSTED.value,
    )
    session.add(gr)
    session.add(
        GoodsReceiptLine(
            company_id=ids.COMPANY,
            goods_receipt_id=id_,
            purchase_order_line_id=line_id,
            description=description,
            quantity=qty,
        )
    )
    session.flush()
    return gr


def _bank(
    session: Session,
    *,
    id_,
    amount: Decimal,
    posted: datetime,
    description: str,
    vendor_id=None,
    customer_id=None,
    ref: str | None = None,
) -> Transaction:
    txn = Transaction(
        id=id_,
        company_id=ids.COMPANY,
        account_id=ids.CASH,
        vendor_id=vendor_id,
        customer_id=customer_id,
        amount=amount,
        posted_at=posted,
        description=description,
        source=TransactionSource.BANK.value,
        external_ref=ref,
        is_sandbox=False,
    )
    session.add(txn)
    session.flush()
    return txn


def _ledger_pair(session: Session, txn_id, debit_acct, credit_acct, amount: Decimal, period: str, memo: str) -> None:
    session.add_all(
        [
            LedgerEntry(
                company_id=ids.COMPANY,
                transaction_id=txn_id,
                account_id=debit_acct,
                debit=amount,
                credit=Decimal("0.00"),
                period=period,
                memo=memo,
            ),
            LedgerEntry(
                company_id=ids.COMPANY,
                transaction_id=txn_id,
                account_id=credit_acct,
                debit=Decimal("0.00"),
                credit=amount,
                period=period,
                memo=memo,
            ),
        ]
    )


def seed_phase2(session: Session, company_id) -> None:
    _people_and_coa(session)
    _vendors_customers(session)
    _policies_contracts_subs(session)
    _existing_po_backfill(session)
    _plant_scenarios(session)
    _operating_volume(session)


def _people_and_coa(session: Session) -> None:
    elena = session.get(Employee, ids.ELENA_EMP)
    jordan = session.get(Employee, ids.JORDAN_EMP)
    sam = session.get(Employee, ids.SAM_EMP)
    if elena:
        elena.approval_limit = Decimal("10000000.00")
    if jordan:
        jordan.approval_limit = Decimal("10000.00")
    if sam:
        sam.approval_limit = Decimal("2500.00")

    priya = User(
        id=ids.PRIYA,
        company_id=ids.COMPANY,
        email="priya.shah@northstarlabs.example",
        full_name="Priya Shah",
        role=UserRole.EXECUTIVE.value,
    )
    marcus = User(
        id=ids.MARCUS,
        company_id=ids.COMPANY,
        email="marcus.chen@northstarlabs.example",
        full_name="Marcus Chen",
        role=UserRole.EXECUTIVE.value,
    )
    avery = User(
        id=ids.AVERY,
        company_id=ids.COMPANY,
        email="avery.kim@northstarlabs.example",
        full_name="Avery Kim",
        role=UserRole.AP.value,
    )
    session.add_all([priya, marcus, avery])
    session.flush()
    session.add_all(
        [
            Employee(
                id=ids.PRIYA_EMP,
                company_id=ids.COMPANY,
                user_id=ids.PRIYA,
                employee_number="E-007",
                full_name="Priya Shah",
                title="VP Information Technology",
                department="IT",
                cost_center="CC-200",
                manager_id=ids.ELENA_EMP,
                hire_date=date(2022, 4, 4),
                approval_limit=Decimal("12000.00"),
            ),
            Employee(
                id=ids.MARCUS_EMP,
                company_id=ids.COMPANY,
                user_id=ids.MARCUS,
                employee_number="E-019",
                full_name="Marcus Chen",
                title="Lab Operations Manager",
                department="Lab",
                cost_center="CC-300",
                manager_id=ids.ELENA_EMP,
                hire_date=date(2022, 9, 12),
                approval_limit=Decimal("5000.00"),
            ),
            Employee(
                id=ids.AVERY_EMP,
                company_id=ids.COMPANY,
                user_id=ids.AVERY,
                employee_number="E-033",
                full_name="Avery Kim",
                title="Procurement Specialist",
                department="Office of the CFO",
                cost_center="CC-100",
                manager_id=ids.JORDAN_EMP,
                hire_date=date(2025, 2, 3),
                approval_limit=Decimal("2500.00"),
            ),
        ]
    )
    session.add_all(
        [
            Account(id=ids.AR, company_id=ids.COMPANY, code="1100", name="Accounts receivable", account_type=AccountType.ASSET.value),
            Account(id=ids.REVENUE, company_id=ids.COMPANY, code="4000", name="Collaboration revenue", account_type=AccountType.REVENUE.value),
            Account(id=ids.EXPENSE_SAAS, company_id=ids.COMPANY, code="6400", name="SaaS subscriptions", account_type=AccountType.EXPENSE.value),
            Account(id=ids.EXPENSE_PAYROLL, company_id=ids.COMPANY, code="6500", name="Payroll processing", account_type=AccountType.EXPENSE.value),
            Account(id=ids.EXPENSE_UTIL, company_id=ids.COMPANY, code="6600", name="Utilities", account_type=AccountType.EXPENSE.value),
            Account(id=ids.EXPENSE_PROF, company_id=ids.COMPANY, code="6700", name="Professional services", account_type=AccountType.EXPENSE.value),
            Account(id=ids.EXPENSE_SHIP, company_id=ids.COMPANY, code="6800", name="Shipping", account_type=AccountType.EXPENSE.value),
        ]
    )
    session.flush()


def _vendors_customers(session: Session) -> None:
    for vendor_id, onboarded in (
        (ids.HELIX, date(2024, 11, 1)),
        (ids.APEX, date(2023, 1, 15)),
        (ids.NA_INSURANCE, date(2021, 6, 1)),
        (ids.METRO_REIT, date(2021, 3, 1)),
        (ids.NVIDIA_OEM, date(2026, 1, 8)),
    ):
        vendor = session.get(Vendor, vendor_id)
        if vendor:
            vendor.onboarded_at = onboarded
            if vendor_id == ids.HELIX:
                vendor.bank_account_ref = "****8891"

    vendors = [
        Vendor(id=ids.AWS, company_id=ids.COMPANY, name="Amazon Web Services", payment_terms="Net 15", risk_tier=RiskTier.LOW.value, is_preferred=True, onboarded_at=date(2024, 2, 1), bank_account_ref="****1001"),
        Vendor(id=ids.LABBENCH, company_id=ids.COMPANY, name="LabBench Software", payment_terms="Net 30", risk_tier=RiskTier.MEDIUM.value, onboarded_at=date(2025, 3, 1), bank_account_ref="****4410"),
        Vendor(id=ids.COLDCHAIN, company_id=ids.COMPANY, name="ColdChain Logistics", payment_terms="Net 30", risk_tier=RiskTier.MEDIUM.value, onboarded_at=date(2024, 9, 1), bank_account_ref="****7722"),
        Vendor(id=ids.FIGMA, company_id=ids.COMPANY, name="Figma", payment_terms="Due on receipt", risk_tier=RiskTier.LOW.value, onboarded_at=date(2024, 5, 1), bank_account_ref="****3003"),
        Vendor(id=ids.NOTION, company_id=ids.COMPANY, name="Notion Labs", payment_terms="Due on receipt", risk_tier=RiskTier.LOW.value, is_preferred=True, onboarded_at=date(2023, 8, 1)),
        Vendor(id=ids.SLACK, company_id=ids.COMPANY, name="Slack Technologies", payment_terms="Due on receipt", risk_tier=RiskTier.LOW.value, onboarded_at=date(2023, 8, 1)),
        Vendor(
            id=ids.SHADOWLINK,
            company_id=ids.COMPANY,
            name="ShadowLink Staffing",
            payment_terms="Net 15",
            risk_tier=RiskTier.WATCH.value,
            onboarded_at=date(2025, 11, 2),
            bank_account_ref="****2210",
            previous_bank_account_ref="****0099",
            bank_changed_at=datetime(2026, 9, 8, 11, 4, tzinfo=UTC),
            notes="Previously flagged. Bank details changed 2026-09-08.",
        ),
        Vendor(id=ids.PULSEDIGEST, company_id=ids.COMPANY, name="PulseDigest Media", payment_terms="Due on receipt", risk_tier=RiskTier.MEDIUM.value, onboarded_at=date(2026, 6, 20)),
        Vendor(id=ids.QUARTZ, company_id=ids.COMPANY, name="Quartz Analytics LLC", payment_terms="Due on receipt", risk_tier=RiskTier.MEDIUM.value, onboarded_at=date(2026, 9, 10), notes="New vendor. Outside onboarding policy."),
        Vendor(id=ids.BIOREAGENT, company_id=ids.COMPANY, name="BioReagent Direct", payment_terms="Net 20", risk_tier=RiskTier.LOW.value, onboarded_at=date(2024, 4, 1)),
        Vendor(id=ids.FEDEX, company_id=ids.COMPANY, name="FedEx Freight", payment_terms="Net 15", risk_tier=RiskTier.LOW.value, onboarded_at=date(2022, 1, 1)),
        Vendor(id=ids.CONSTELLATION, company_id=ids.COMPANY, name="Constellation Energy", payment_terms="Net 20", risk_tier=RiskTier.LOW.value, onboarded_at=date(2021, 3, 1)),
        Vendor(id=ids.GUSTO, company_id=ids.COMPANY, name="Gusto Payroll", payment_terms="Due on receipt", risk_tier=RiskTier.LOW.value, is_preferred=True, onboarded_at=date(2022, 7, 1)),
        Vendor(id=ids.CLEANLAB, company_id=ids.COMPANY, name="CleanLab Services", payment_terms="Net 30", risk_tier=RiskTier.LOW.value, onboarded_at=date(2023, 2, 1)),
        Vendor(id=ids.HARBOR_GLASS, company_id=ids.COMPANY, name="Harbor Scientific Glass", payment_terms="Net 30", risk_tier=RiskTier.MEDIUM.value, onboarded_at=date(2024, 1, 9)),
        Vendor(id=ids.DATADOG, company_id=ids.COMPANY, name="Datadog", payment_terms="Net 15", risk_tier=RiskTier.LOW.value, onboarded_at=date(2024, 6, 1)),
        Vendor(id=ids.GITHUB, company_id=ids.COMPANY, name="GitHub", payment_terms="Due on receipt", risk_tier=RiskTier.LOW.value, onboarded_at=date(2023, 5, 1)),
        Vendor(id=ids.ZOOM, company_id=ids.COMPANY, name="Zoom Video", payment_terms="Due on receipt", risk_tier=RiskTier.LOW.value, onboarded_at=date(2023, 5, 1)),
        Vendor(id=ids.OFFICE_DEPOT, company_id=ids.COMPANY, name="Office Depot Business", payment_terms="Net 30", risk_tier=RiskTier.LOW.value, onboarded_at=date(2022, 8, 1)),
        Vendor(id=ids.WEWORK, company_id=ids.COMPANY, name="WeWork Overflow", payment_terms="Due on 1st", risk_tier=RiskTier.MEDIUM.value, onboarded_at=date(2025, 1, 6)),
    ]
    session.add_all(vendors)
    session.add_all(
        [
            Customer(id=ids.BOSTON_CHILDRENS, company_id=ids.COMPANY, name="Boston Children's Collaboration", payment_terms="Net 30"),
            Customer(id=ids.MASS_GRANT, company_id=ids.COMPANY, name="Commonwealth of Massachusetts Grant Office", payment_terms="Net 45"),
        ]
    )
    session.add(
        Document(
            id=ids.DOC_VOLUME,
            company_id=ids.COMPANY,
            filename="volume_ap_pack.pdf.txt",
            mime_type="text/plain",
            storage_backend=StorageBackend.LOCAL.value,
            storage_uri="data/demo/inbox/volume_ap_pack.pdf.txt",
            document_class=DocumentClass.INVOICE.value,
            extraction_status=ExtractionStatus.EXTRACTED.value,
            ingested_at=AS_OF - timedelta(days=2),
            raw_text="Northstar volume AP pack",
        )
    )
    session.add(
        Document(
            id=ids.DOC_COLDCHAIN,
            company_id=ids.COMPANY,
            filename="ColdChain_MSA_terms.pdf.txt",
            mime_type="text/plain",
            storage_backend=StorageBackend.LOCAL.value,
            storage_uri="data/demo/inbox/ColdChain_MSA_terms.pdf.txt",
            document_class=DocumentClass.CONTRACT.value,
            extraction_status=ExtractionStatus.EXTRACTED.value,
            ingested_at=AS_OF - timedelta(days=40),
            raw_text="ColdChain agreed price 10000 allowed annual increase 4%",
        )
    )
    session.flush()


def _policies_contracts_subs(session: Session) -> None:
    spend = session.get(Policy, ids.POLICY_SPEND)
    if spend is not None:
        spend.rules = {
            "mira_autonomous_limit": 2500,
            "controller_limit": 10000,
            "dual_approval_above": 10000,
            "cfo_approval_above": 10000,
            "duplicate_amount_tolerance": 1.00,
            "duplicate_date_window_days": 14,
            "aws_precedent_limit": 12000,
            "new_vendor_days": 30,
            "closed_periods": ["2026-06"],
            "po_required_above": 2500,
            "po_exempt_vendor_ids": [str(ids.METRO_REIT), str(ids.NA_INSURANCE), str(ids.CONSTELLATION)],
            "document_required_above": 100,
        }
    session.add(
        Policy(
            id=ids.POLICY_VENDOR,
            company_id=ids.COMPANY,
            name="Vendor onboarding & close calendar",
            policy_type=PolicyType.VENDOR.value,
            version="1",
            body="New vendors require secondary approval. June 2026 is closed. AWS infra below $12,000 may use approved precedent.",
            rules={
                "new_vendor_days": 30,
                "closed_periods": ["2026-06"],
                "aws_precedent_limit": 12000,
            },
            effective_at=datetime(2026, 7, 1, tzinfo=UTC),
            status=PolicyStatus.ACTIVE.value,
        )
    )
    session.add(
        Precedent(
            id=ids.PRECEDENT_AWS,
            company_id=ids.COMPANY,
            situation_hash="aws-infra-under-12k-q2",
            summary="Q2 2026: Elena approved AWS infrastructure spend under $12,000 against the cloud budget without dual approval.",
            outcome="approved",
            period="2026-06",
            reusable_rule="AWS infrastructure below $12,000 may use this approved precedent instead of dual CFO approval.",
        )
    )
    session.add(
        Contract(
            id=ids.CONTRACT_COLDCHAIN,
            company_id=ids.COMPANY,
            vendor_id=ids.COLDCHAIN,
            document_id=ids.DOC_COLDCHAIN,
            title="ColdChain Logistics warehousing agreement",
            start_date=date(2025, 9, 1),
            end_date=date(2027, 8, 31),
            value=Decimal("10000.00"),
            status=ContractStatus.ACTIVE.value,
            extracted_terms={
                "agreed_price": "10000.00",
                "allowed_annual_increase_pct": "4",
                "payment_terms": "Net 30",
                "renewal_date": "2027-08-31",
                "termination_terms": "60-day notice",
                "price_basis_date": "2025-09-01",
                "applies_invoice_numbers": ["CC-2026-09"],
            },
        )
    )
    session.add(
        Contract(
            id=ids.CONTRACT_AWS,
            company_id=ids.COMPANY,
            vendor_id=ids.AWS,
            title="AWS Enterprise Discount Program",
            start_date=date(2024, 2, 1),
            end_date=date(2027, 1, 31),
            value=Decimal("12000.00"),
            status=ContractStatus.ACTIVE.value,
            extracted_terms={
                "payment_terms": "Net 15",
                "renewal_date": "2027-01-31",
                "termination_terms": "30-day notice",
            },
        )
    )
    session.add_all(
        [
            RecurringSubscription(id=ids.SUB_AWS, company_id=ids.COMPANY, vendor_id=ids.AWS, name="AWS infrastructure", expected_amount=Decimal("8400.00"), cadence="monthly", is_in_use=True, start_date=date(2024, 2, 1)),
            RecurringSubscription(id=ids.SUB_FIGMA, company_id=ids.COMPANY, vendor_id=ids.FIGMA, name="Figma organization", expected_amount=Decimal("75.00"), cadence="monthly", is_in_use=False, start_date=date(2024, 5, 1)),
            RecurringSubscription(id=ids.SUB_NOTION, company_id=ids.COMPANY, vendor_id=ids.NOTION, name="Notion workspace", expected_amount=Decimal("144.00"), cadence="monthly", is_in_use=True, start_date=date(2023, 8, 1)),
            RecurringSubscription(id=ids.SUB_SLACK, company_id=ids.COMPANY, vendor_id=ids.SLACK, name="Slack business+", expected_amount=Decimal("240.00"), cadence="monthly", is_in_use=True, start_date=date(2023, 8, 1)),
        ]
    )
    session.flush()


def _existing_po_backfill(session: Session) -> None:
    helix_a = session.get(Invoice, ids.INV_HELIX_A)
    helix_b = session.get(Invoice, ids.INV_HELIX_B)
    apex = session.get(Invoice, ids.INV_APEX)
    _po(session, id_=ids.PO_HELIX, vendor_id=ids.HELIX, number="PO-2026-HELIX-BURST", total=Decimal("18400.00"), requester=ids.JORDAN, status=POStatus.RECEIVED.value, line_id=ids.filler("poline", 1), account_id=ids.EXPENSE_CLOUD, description="Aug GPU/CPU burst")
    _po(session, id_=ids.PO_APEX, vendor_id=ids.APEX, number="PO-2026-APEX-REAGENTS", total=Decimal("42100.00"), requester=ids.MARCUS, status=POStatus.RECEIVED.value, line_id=ids.filler("poline", 2), account_id=ids.EXPENSE_LAB, description="Reagents and cold-chain")
    session.flush()
    helix_line = session.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id == ids.PO_HELIX).one()
    apex_line = session.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id == ids.PO_APEX).one()
    _gr(session, id_=ids.GR_HELIX, po_id=ids.PO_HELIX, line_id=helix_line.id, qty=Decimal("1"), description="burst received", received=_dt(date(2026, 8, 28)))
    _gr(session, id_=ids.GR_APEX, po_id=ids.PO_APEX, line_id=apex_line.id, qty=Decimal("1"), description="reagents received", received=_dt(date(2026, 7, 20)))
    if helix_a:
        helix_a.purchase_order_id = ids.PO_HELIX
        helix_a.posted_period = "2026-09"
    if helix_b:
        helix_b.purchase_order_id = ids.PO_HELIX
        helix_b.posted_period = "2026-09"
    if apex:
        apex.purchase_order_id = ids.PO_APEX
        apex.posted_period = "2026-07"
    session.flush()


def _plant_scenarios(session: Session) -> None:
    # 1. Duplicate $4,850
    _po(session, id_=ids.filler("po-labbench", 1), vendor_id=ids.LABBENCH, number="PO-2026-LABBENCH-4850", total=Decimal("4850.00"), requester=ids.JORDAN, status=POStatus.APPROVED.value, account_id=ids.EXPENSE_SAAS, description="LabBench annual seats")
    po_lab = session.query(PurchaseOrder).filter(PurchaseOrder.po_number == "PO-2026-LABBENCH-4850").one()
    _invoice(session, id_=ids.INV_4850, vendor_id=ids.LABBENCH, number="INV-4850", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 4), due=date(2026, 10, 4), total=Decimal("4850.00"), status=InvoiceStatus.RECEIVED.value, po_id=po_lab.id, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SAAS, description="LabBench annual seats")
    _invoice(session, id_=ids.INV_4850A, vendor_id=ids.LABBENCH, number="INV-4850A", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 6), due=date(2026, 10, 6), total=Decimal("4850.00"), status=InvoiceStatus.RECEIVED.value, po_id=po_lab.id, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SAAS, description="LabBench annual seats duplicate", duplicate=True)

    # 2. Invoice exceeds PO
    _po(session, id_=ids.PO_EXCEED, vendor_id=ids.HARBOR_GLASS, number="PO-2026-GLASS-10K", total=Decimal("10000.00"), requester=ids.MARCUS, status=POStatus.RECEIVED.value, line_id=ids.PO_EXCEED_LINE, account_id=ids.EXPENSE_LAB, description="Borosilicate lot", qty=Decimal("1"))
    _gr(session, id_=ids.GR_EXCEED, po_id=ids.PO_EXCEED, line_id=ids.PO_EXCEED_LINE, qty=Decimal("1"), description="glass received", received=_dt(date(2026, 9, 8)))
    _invoice(session, id_=ids.INV_EXCEED, vendor_id=ids.HARBOR_GLASS, number="HG-12500", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 10), due=date(2026, 10, 10), total=Decimal("12500.00"), status=InvoiceStatus.NEEDS_REVIEW.value, po_id=ids.PO_EXCEED, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_LAB, description="Borosilicate lot billed high")
    # Keep billed qty = 1 so GR mismatch does not fire; amount mismatch does.
    session.flush()

    # 3. Requester self-approves (Sam, $1,800 — within AP limit so authority-exceeded stays silent)
    _po(session, id_=ids.PO_SELF, vendor_id=ids.OFFICE_DEPOT, number="PO-2026-SELF-1800", total=Decimal("1800.00"), requester=ids.SAM, status=POStatus.APPROVED.value, line_id=ids.PO_SELF_LINE, account_id=ids.EXPENSE_SAAS, description="Office chairs")
    session.add(
        Approval(
            id=ids.APPROVAL_SELF,
            company_id=ids.COMPANY,
            subject_type="purchase_order",
            subject_id=ids.PO_SELF,
            requested_by_user_id=ids.SAM,
            approver_user_id=ids.SAM,
            status=ApprovalStatus.APPROVED.value,
            comment="Self-approved — control failure planted for evaluation.",
        )
    )

    # Authority exceeded (Jordan $25,000 > $10,000 controller limit)
    _po(session, id_=ids.PO_AUTHORITY, vendor_id=ids.WEWORK, number="PO-2026-AUTH-25K", total=Decimal("25000.00"), requester=ids.AVERY, status=POStatus.APPROVED.value, line_id=ids.PO_AUTHORITY_LINE, account_id=ids.EXPENSE_RENT, description="Overflow suite")
    session.add(
        Approval(
            id=ids.APPROVAL_AUTHORITY,
            company_id=ids.COMPANY,
            subject_type="purchase_order",
            subject_id=ids.PO_AUTHORITY,
            requested_by_user_id=ids.AVERY,
            approver_user_id=ids.JORDAN,
            status=ApprovalStatus.APPROVED.value,
            comment="Controller approved $25,000 — exceeds $10,000 authority.",
        )
    )

    # 4. One ACH covers three invoices
    _invoice(session, id_=ids.INV_BIO_A, vendor_id=ids.BIOREAGENT, number="BIO-1200", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 2), due=date(2026, 9, 22), total=Decimal("1200.00"), status=InvoiceStatus.APPROVED.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_LAB, description="Kit A")
    _invoice(session, id_=ids.INV_BIO_B, vendor_id=ids.BIOREAGENT, number="BIO-1400", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 3), due=date(2026, 9, 23), total=Decimal("1400.00"), status=InvoiceStatus.APPROVED.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_LAB, description="Kit B")
    _invoice(session, id_=ids.INV_BIO_C, vendor_id=ids.BIOREAGENT, number="BIO-1000", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 4), due=date(2026, 9, 24), total=Decimal("1000.00"), status=InvoiceStatus.APPROVED.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_LAB, description="Kit C")
    _bank(session, id_=ids.TXN_ACH_THREE, amount=Decimal("-3600.00"), posted=_dt(date(2026, 9, 15), 10, 12), description="ACH BioReagent Direct batch", vendor_id=ids.BIOREAGENT, ref="ACH-BIO-BATCH")

    # 5. Duplicated refund
    _invoice(session, id_=ids.INV_REFUND, vendor_id=ids.FEDEX, number="REF-185", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 7), due=date(2026, 9, 7), total=Decimal("185.00"), status=InvoiceStatus.REJECTED.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SHIP, description="FedEx credit memo")
    _bank(session, id_=ids.TXN_REFUND_A, amount=Decimal("185.00"), posted=_dt(date(2026, 9, 9), 11, 0), description="REFUND FedEx credit", vendor_id=ids.FEDEX, ref="REFUND-185-A")
    _bank(session, id_=ids.TXN_REFUND_B, amount=Decimal("185.00"), posted=_dt(date(2026, 9, 10), 11, 5), description="REFUND FedEx credit", vendor_id=ids.FEDEX, ref="REFUND-185-B")

    # 6. Unexplained $12.40
    _invoice(session, id_=ids.INV_FEE_GAP, vendor_id=ids.CLEANLAB, number="CL-5000", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 11), due=date(2026, 10, 11), total=Decimal("5000.00"), status=InvoiceStatus.APPROVED.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_LAB, description="Deep clean")
    _bank(session, id_=ids.TXN_FEE_GAP, amount=Decimal("-5012.40"), posted=_dt(date(2026, 9, 12), 9, 40), description="ACH CleanLab Services", vendor_id=ids.CLEANLAB, ref="ACH-CL-5000")

    # 7. AWS monthly + spike. Aug $11,000 proves the $12k precedent carve-out.
    for inv_id, po_id, number, issue, total in (
        (ids.INV_AWS_JUL, ids.PO_AWS_JUL, "AWS-2026-07", date(2026, 7, 3), Decimal("8200.00")),
        (ids.INV_AWS_AUG, ids.PO_AWS_AUG, "AWS-2026-08", date(2026, 8, 3), Decimal("11000.00")),
        (ids.INV_AWS_SEP, ids.PO_AWS_SEP, "AWS-2026-09", date(2026, 9, 3), Decimal("19800.00")),
    ):
        _po(session, id_=po_id, vendor_id=ids.AWS, number=f"PO-{number}", total=total, requester=ids.PRIYA, status=POStatus.RECEIVED.value, account_id=ids.EXPENSE_CLOUD, description="AWS infrastructure")
        session.flush()
        po_line = session.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id == po_id).one()
        _gr(session, id_=ids.filler("gr-aws", po_id.int % 100000), po_id=po_id, line_id=po_line.id, qty=Decimal("1"), description="AWS period", received=_dt(issue))
        _invoice(session, id_=inv_id, vendor_id=ids.AWS, number=number, direction=InvoiceDirection.AP.value, issue=issue, due=issue + timedelta(days=15), total=total, status=InvoiceStatus.APPROVED.value if total < Decimal("15000") else InvoiceStatus.NEEDS_REVIEW.value, po_id=po_id, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_CLOUD, description="AWS infrastructure")

    # 8. Contract 4% vs invoice 11%
    _invoice(session, id_=ids.INV_COLDCHAIN, vendor_id=ids.COLDCHAIN, number="CC-2026-09", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 1), due=date(2026, 10, 1), total=Decimal("11100.00"), status=InvoiceStatus.NEEDS_REVIEW.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SHIP, description="Warehousing September")

    # 9. Customer >45 days overdue (due 2026-07-31 → 50 days on 2026-09-19)
    _invoice(session, id_=ids.INV_ATLAS_OD, customer_id=ids.ATLAS, number="NSL-AR-4411", direction=InvoiceDirection.AR.value, issue=date(2026, 7, 1), due=date(2026, 7, 31), total=Decimal("28000.00"), status=InvoiceStatus.NEEDS_REVIEW.value, document_id=ids.DOC_VOLUME, account_id=ids.REVENUE, description="Atlas collaboration milestone")

    # 10. Unused Figma
    for inv_id, number, issue in (
        (ids.INV_FIGMA_JUL, "FIGMA-2026-07", date(2026, 7, 1)),
        (ids.INV_FIGMA_AUG, "FIGMA-2026-08", date(2026, 8, 1)),
        (ids.INV_FIGMA_SEP, "FIGMA-2026-09", date(2026, 9, 1)),
    ):
        _invoice(session, id_=inv_id, vendor_id=ids.FIGMA, number=number, direction=InvoiceDirection.AP.value, issue=issue, due=issue, total=Decimal("75.00"), status=InvoiceStatus.PAID.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SAAS, description="Figma org unused")

    # 11. Closed-period invoice
    _invoice(session, id_=ids.INV_CLOSED, vendor_id=ids.HARBOR_GLASS, number="HG-CLOSED-JUN", direction=InvoiceDirection.AP.value, issue=date(2026, 6, 20), due=date(2026, 7, 20), total=Decimal("3200.00"), status=InvoiceStatus.RECEIVED.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_LAB, description="June glass posted after close", posted_period="2026-06")

    # 12. Missing receipt
    _po(session, id_=ids.PO_MISSING_GR, vendor_id=ids.FEDEX, number="PO-2026-NO-GR", total=Decimal("4100.00"), requester=ids.SAM, status=POStatus.APPROVED.value, line_id=ids.PO_MISSING_GR_LINE, account_id=ids.EXPENSE_SHIP, description="Cold-chain freight")
    _invoice(session, id_=ids.INV_MISSING_GR, vendor_id=ids.FEDEX, number="FDX-4100", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 14), due=date(2026, 9, 29), total=Decimal("4100.00"), status=InvoiceStatus.RECEIVED.value, po_id=ids.PO_MISSING_GR, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SHIP, description="Freight billed, no receipt")

    # 13. New vendor outside policy
    _po(session, id_=ids.PO_QUARTZ, vendor_id=ids.QUARTZ, number="PO-2026-QUARTZ", total=Decimal("14200.00"), requester=ids.AVERY, status=POStatus.SUBMITTED.value, account_id=ids.EXPENSE_SAAS, description="Analytics trial")
    _invoice(session, id_=ids.INV_QUARTZ, vendor_id=ids.QUARTZ, number="QZ-14200", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 12), due=date(2026, 9, 26), total=Decimal("14200.00"), status=InvoiceStatus.NEEDS_REVIEW.value, po_id=ids.PO_QUARTZ, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SAAS, description="Quartz analytics new vendor", requested_by=ids.AVERY)

    # Duplicate payment of one invoice
    _invoice(session, id_=ids.INV_DUP_PAY, vendor_id=ids.CLEANLAB, number="CL-2200", direction=InvoiceDirection.AP.value, issue=date(2026, 8, 20), due=date(2026, 9, 20), total=Decimal("2200.00"), status=InvoiceStatus.PAID.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_LAB, description="Spot clean")
    session.add_all(
        [
            Payment(id=ids.PAY_DUP_A, company_id=ids.COMPANY, invoice_id=ids.INV_DUP_PAY, amount=Decimal("2200.00"), method=PaymentMethod.ACH.value, status=PaymentStatus.SETTLED.value, is_sandbox=False, paid_at=_dt(date(2026, 9, 1), 12, 0), processor_ref="ACH-CL-2200-A"),
            Payment(id=ids.PAY_DUP_B, company_id=ids.COMPANY, invoice_id=ids.INV_DUP_PAY, amount=Decimal("2200.00"), method=PaymentMethod.ACH.value, status=PaymentStatus.SETTLED.value, is_sandbox=False, paid_at=_dt(date(2026, 9, 2), 12, 5), processor_ref="ACH-CL-2200-B"),
        ]
    )

    # Missing supporting document
    _invoice(session, id_=ids.INV_MISSING_DOC, vendor_id=ids.WEWORK, number="WW-NO-DOC", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 8), due=date(2026, 9, 22), total=Decimal("3600.00"), status=InvoiceStatus.RECEIVED.value, document_id=None, account_id=ids.EXPENSE_RENT, description="Day pass block without file")

    # Missing PO (established vendor, over threshold)
    _invoice(session, id_=ids.INV_MISSING_PO, vendor_id=ids.DATADOG, number="DD-NO-PO", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 5), due=date(2026, 9, 20), total=Decimal("8000.00"), status=InvoiceStatus.RECEIVED.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SAAS, description="Datadog overage without PO")

    # Abnormal timing
    _bank(session, id_=ids.TXN_ODD_HOURS, amount=Decimal("-640.00"), posted=datetime(2026, 9, 5, 3, 17, tzinfo=UTC), description="CARD *shadow weekend", vendor_id=ids.SHADOWLINK, ref="CARD-ODD-640")

    # Round-number payment
    _invoice(session, id_=ids.INV_ROUND, vendor_id=ids.GUSTO, number="GUSTO-50K", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 1), due=date(2026, 9, 1), total=Decimal("50000.00"), status=InvoiceStatus.SCHEDULED.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_PAYROLL, description="Payroll funding")
    session.add(
        Payment(
            id=ids.PAY_ROUND,
            company_id=ids.COMPANY,
            invoice_id=ids.INV_ROUND,
            amount=Decimal("50000.00"),
            method=PaymentMethod.ACH.value,
            status=PaymentStatus.PENDING.value,
            is_sandbox=False,
            paid_at=_dt(date(2026, 9, 1), 9, 0),
            processor_ref="ACH-50K-ROUND",
        )
    )

    # Unexpected recurring PulseDigest
    for inv_id, number, issue in (
        (ids.INV_PULSE_JUL, "PULSE-2026-07", date(2026, 7, 8)),
        (ids.INV_PULSE_AUG, "PULSE-2026-08", date(2026, 8, 8)),
        (ids.INV_PULSE_SEP, "PULSE-2026-09", date(2026, 9, 8)),
    ):
        _invoice(session, id_=inv_id, vendor_id=ids.PULSEDIGEST, number=number, direction=InvoiceDirection.AP.value, issue=issue, due=issue, total=Decimal("49.00"), status=InvoiceStatus.PAID.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_SAAS, description="PulseDigest newsletter")

    # Flagged vendor invoice after bank change
    _invoice(session, id_=ids.INV_SHADOW, vendor_id=ids.SHADOWLINK, number="SH-9901", direction=InvoiceDirection.AP.value, issue=date(2026, 9, 10), due=date(2026, 9, 25), total=Decimal("6400.00"), status=InvoiceStatus.NEEDS_REVIEW.value, document_id=ids.DOC_VOLUME, account_id=ids.EXPENSE_PROF, description="Contractors week 37")

    session.flush()


def _operating_volume(session: Session) -> None:
    rng = random.Random(20260919)
    recurring = [
        (ids.NOTION, "NOTION", Decimal("144.00"), ids.EXPENSE_SAAS),
        (ids.SLACK, "SLACK", Decimal("240.00"), ids.EXPENSE_SAAS),
        (ids.DATADOG, "DDOG", Decimal("1800.00"), ids.EXPENSE_SAAS),
        (ids.GITHUB, "GH", Decimal("800.00"), ids.EXPENSE_SAAS),
        (ids.ZOOM, "ZOOM", Decimal("220.00"), ids.EXPENSE_SAAS),
        (ids.CLEANLAB, "CLN", Decimal("1200.00"), ids.EXPENSE_LAB),
        (ids.CONSTELLATION, "PWR", Decimal("3100.00"), ids.EXPENSE_UTIL),
        (ids.GUSTO, "PAY", Decimal("8500.00"), ids.EXPENSE_PAYROLL),
        (ids.NA_INSURANCE, "INS", Decimal("4100.00"), ids.EXPENSE_PROF),
        (ids.OFFICE_DEPOT, "OD", Decimal("340.00"), ids.EXPENSE_SAAS),
    ]
    n = 0
    for month, day in ((7, 5), (8, 5), (9, 5)):
        issue = date(2026, month, day)
        for vendor_id, prefix, amount, acct in recurring:
            n += 1
            inv_id = ids.filler("vol-inv", n)
            _invoice(
                session,
                id_=inv_id,
                vendor_id=vendor_id,
                number=f"{prefix}-2026-{month:02d}",
                direction=InvoiceDirection.AP.value,
                issue=issue,
                due=issue + timedelta(days=15),
                total=amount,
                status=InvoiceStatus.PAID.value,
                document_id=ids.DOC_VOLUME,
                account_id=acct,
                description=f"{prefix} recurring {issue.isoformat()}",
            )
            txn = _bank(
                session,
                id_=ids.filler("vol-ach", n),
                amount=-amount,
                posted=_dt(issue + timedelta(days=10), 11, n % 50),
                description=f"ACH {prefix}",
                vendor_id=vendor_id,
                ref=f"{prefix}-2026-{month:02d}",
            )
            _ledger_pair(session, txn.id, ids.AP, ids.CASH, amount, _period(issue), f"pay {prefix}")

    # Customer invoices + receipts
    for i, (cust, number, issue, total, status) in enumerate(
        (
            (ids.NIH, "NSL-AR-NIH-07", date(2026, 7, 15), Decimal("62000.00"), InvoiceStatus.PAID.value),
            (ids.NIH, "NSL-AR-NIH-08", date(2026, 8, 15), Decimal("62000.00"), InvoiceStatus.PAID.value),
            (ids.BOSTON_CHILDRENS, "NSL-AR-BCH-08", date(2026, 8, 10), Decimal("18500.00"), InvoiceStatus.PAID.value),
            (ids.MASS_GRANT, "NSL-AR-MA-07", date(2026, 7, 20), Decimal("44000.00"), InvoiceStatus.PAID.value),
            (ids.ATLAS, "NSL-AR-ATLAS-08", date(2026, 8, 20), Decimal("15000.00"), InvoiceStatus.PAID.value),
        ),
        start=1,
    ):
        _invoice(session, id_=ids.filler("ar-inv", i), customer_id=cust, number=number, direction=InvoiceDirection.AR.value, issue=issue, due=issue + timedelta(days=30), total=total, status=status, document_id=ids.DOC_VOLUME, account_id=ids.REVENUE, description="Collaboration billing")
        txn = _bank(session, id_=ids.filler("ar-cash", i), amount=total, posted=_dt(issue + timedelta(days=20), 15, 0), description=f"WIRE {number}", customer_id=cust, ref=number)
        _ledger_pair(session, txn.id, ids.CASH, ids.AR, total, _period(issue), "customer receipt")

    # ~70 card transactions across Jul–Sep
    start = date(2026, 7, 1)
    for i in range(70):
        d = start + timedelta(days=i)
        if d > date(2026, 9, 18):
            break
        if d.weekday() >= 5:
            continue
        amount = Decimal(str(round(12.5 + (rng.random() * 370), 2)))
        txn = _bank(
            session,
            id_=ids.filler("card", i),
            amount=-amount,
            posted=_dt(d, 9 + (i % 8), (i * 3) % 60),
            description=f"CARD *NSL ops {i:03d}",
            ref=f"CARD-{i:04d}",
        )
        _ledger_pair(session, txn.id, ids.EXPENSE_SAAS, ids.CASH, amount, _period(d), "card spend")

    june = date(2026, 6, 1)
    extra = 0
    day = 0
    while extra < 20:
        d = june + timedelta(days=day)
        day += 1
        if d.weekday() >= 5:
            continue
        extra += 1
        amount = Decimal(str(round(20 + extra * 3.25, 2)))
        txn = _bank(
            session,
            id_=ids.filler("card-jun", extra),
            amount=-amount,
            posted=_dt(d, 10, extra),
            description=f"CARD *NSL june {extra:03d}",
            ref=f"CARD-JUN-{extra:04d}",
        )
        _ledger_pair(session, txn.id, ids.EXPENSE_SAAS, ids.CASH, amount, _period(d), "june card spend")

    session.flush()
