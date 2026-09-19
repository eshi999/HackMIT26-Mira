"""Idempotent Northstar Labs seed.

Run:
    python -m mira.seed.northstar
or let the API bootstrap on boot when MIRA_BOOTSTRAP=1.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from mira.core.enums import (
    AccountType,
    ActorType,
    AgentRole,
    AgentRunStatus,
    AgentTaskStatus,
    ApprovalStatus,
    ContractStatus,
    DecisionStatus,
    DocumentClass,
    ExtractionStatus,
    FindingStatus,
    InvoiceDirection,
    InvoiceStatus,
    MetricSource,
    PolicyStatus,
    PolicyType,
    POStatus,
    RiskLevel,
    RiskTier,
    SavingsCategory,
    Severity,
    StorageBackend,
    TransactionSource,
    UserRole,
)
from mira.core.models import (
    Account,
    AgentRun,
    AgentTask,
    Approval,
    AuditEvent,
    Budget,
    BudgetLine,
    Company,
    Contract,
    Customer,
    Decision,
    Document,
    Employee,
    Evidence,
    EvidenceReferenceRow,
    ExternalSignal,
    Finding,
    Forecast,
    Invoice,
    InvoiceLine,
    LedgerEntry,
    Metric,
    Policy,
    Precedent,
    PurchaseOrder,
    PurchaseOrderLine,
    RiskAssessment,
    SavingsEvent,
    Transaction,
    User,
    Vendor,
)
from mira.seed import ids

AS_OF = datetime(2026, 9, 19, 7, 30, tzinfo=UTC)
PERIOD = "2026-09"
ROOT = Path(__file__).resolve().parents[3]
INBOX = ROOT / "data" / "demo" / "inbox"

SPEND_POLICY_BODY = """Northstar Labs Spend & Authority Policy v3
Effective 2026-07-01

1. Purchases under $2,500 may be executed by the digital CFO (Mira) against an approved budget line.
2. Purchases of $2,500 to $10,000 require Controller (Jordan Hale) approval.
3. Purchases above $10,000 require dual approval: Controller and CFO (Elena Voss).
4. Preferred vendors must be used when the item is in-category, unless a written exception exists.
5. Rush software or cloud seat expansions require VP IT sign-off. Precedent 2026-04 applies.
6. Duplicate vendor invoices (same vendor, amount within $1, invoice number edit-distance ≤ 2, date within 14 days) are blocked, not paid.
"""

HELIX_MSA = """HELIXCLOUD MASTER SERVICES AGREEMENT
Customer: Northstar Labs, Inc.
Auto-renewal: 30-day notice required or term renews for 12 months.
Liability cap: 12 months of fees.
Invoice terms: Net 15.
Seat burst: overage billed at list, not committed rate.
"""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_inbox() -> None:
    INBOX.mkdir(parents=True, exist_ok=True)
    files = {
        "INV_helix_10441_FINAL(2).pdf.txt": "HelixCloud Invoice 10441\nAmount due: $18,400.00\nPeriod: Aug 2026 GPU/CPU burst\n",
        "scan_img_8821_helixcloud_invoice.PDF.txt": "HelixCloud Invoice 10441-A\nAmount due: $18,400.00\nDUPLICATE of 10441 with suffix -A\n",
        "apex scientific inv 9920 overdue.TXT": "Apex Scientific Supply INV-9920\nReagents and cold-chain\nTotal $42,100.00 due 2026-08-12 OVERDUE\n",
        "Spend Policy v3 REALLY FINAL.docx.txt": SPEND_POLICY_BODY,
        "HelixCloud_MSA_2024_executed.pdf.txt": HELIX_MSA,
        "BankStmt_Aug2026 weird export.csv": "date,desc,amount\n2026-08-29,OPERATING CASH,2412550.00\n",
        "gpu quote Q4 eval cluster.txt": "OEM quote: 2x inference GPU, $33,500 each, total $67,000. Sandbox catalog.\n",
        "random_receipt_uber_lab_dinner.jpg.txt": "Uber receipt $64.20 — personal? flag for review.\n",
    }
    for name, body in files.items():
        path = INBOX / name
        if not path.exists():
            path.write_text(body)


def seed_northstar(session: Session) -> Company:
    """Insert or return the Northstar Labs tenant. Idempotent on company slug."""
    _write_inbox()
    existing = session.scalar(select(Company).where(Company.slug == "northstar-labs"))
    if existing:
        return existing

    company = Company(
        id=ids.COMPANY,
        slug="northstar-labs",
        name="Northstar Labs",
        legal_name="Northstar Labs, Inc.",
        industry="Biotech / applied ML",
        stage="series_b",
        fiscal_year_start_month=1,
        base_currency="USD",
        timezone="America/New_York",
        employee_count=82,
        description=(
            "Series B lab company. Messy AP inbox, thin controller bench, "
            "and a digital CFO hired to run the office."
        ),
    )
    session.add(company)
    session.flush()

    elena = User(
        id=ids.ELENA,
        company_id=company.id,
        email="elena.voss@northstarlabs.example",
        full_name="Elena Voss",
        role=UserRole.CFO.value,
    )
    jordan = User(
        id=ids.JORDAN,
        company_id=company.id,
        email="jordan.hale@northstarlabs.example",
        full_name="Jordan Hale",
        role=UserRole.CONTROLLER.value,
    )
    sam = User(
        id=ids.SAM,
        company_id=company.id,
        email="sam.okonkwo@northstarlabs.example",
        full_name="Sam Okonkwo",
        role=UserRole.AP.value,
    )
    session.add_all([elena, jordan, sam])
    session.flush()

    session.add(
        Employee(
            id=ids.ELENA_EMP,
            company_id=company.id,
            user_id=elena.id,
            employee_number="E-001",
            full_name="Elena Voss",
            title="Chief Financial Officer",
            department="Office of the CFO",
            cost_center="CC-100",
            hire_date=date(2021, 3, 1),
            approval_limit=Decimal("10000000.00"),
        )
    )
    session.flush()
    session.add(
        Employee(
            id=ids.JORDAN_EMP,
            company_id=company.id,
            user_id=jordan.id,
            employee_number="E-014",
            full_name="Jordan Hale",
            title="Controller",
            department="Office of the CFO",
            cost_center="CC-100",
            manager_id=ids.ELENA_EMP,
            hire_date=date(2023, 6, 12),
            approval_limit=Decimal("10000.00"),
        )
    )
    session.flush()
    session.add(
        Employee(
            id=ids.SAM_EMP,
            company_id=company.id,
            user_id=sam.id,
            employee_number="E-028",
            full_name="Sam Okonkwo",
            title="Accounts Payable Lead",
            department="Office of the CFO",
            cost_center="CC-100",
            manager_id=ids.JORDAN_EMP,
            hire_date=date(2024, 1, 8),
            approval_limit=Decimal("2500.00"),
        )
    )
    session.flush()

    helix = Vendor(
        id=ids.HELIX,
        company_id=company.id,
        name="HelixCloud",
        email="billing@helixcloud.example",
        payment_terms="Net 15",
        risk_tier=RiskTier.MEDIUM.value,
        is_preferred=True,
        notes="Primary GPU/CPU burst vendor. MSA auto-renews.",
    )
    apex = Vendor(
        id=ids.APEX,
        company_id=company.id,
        name="Apex Scientific Supply",
        email="ar@apexsci.example",
        payment_terms="Net 30",
        risk_tier=RiskTier.HIGH.value,
        notes="Cold-chain reagents. Frequently overdue.",
    )
    session.add_all(
        [
            helix,
            apex,
            Vendor(
                id=ids.NA_INSURANCE,
                company_id=company.id,
                name="North Atlantic Insurance",
                payment_terms="Net 30",
                risk_tier=RiskTier.LOW.value,
                is_preferred=True,
            ),
            Vendor(
                id=ids.METRO_REIT,
                company_id=company.id,
                name="Metro Office REIT",
                payment_terms="Due on 1st",
                risk_tier=RiskTier.LOW.value,
            ),
            Vendor(
                id=ids.NVIDIA_OEM,
                company_id=company.id,
                name="Harbor Compute OEM (sandbox catalog)",
                payment_terms="Due on receipt",
                risk_tier=RiskTier.MEDIUM.value,
                notes="Sandbox / simulated merchant for Visa procurement path.",
            ),
        ]
    )
    session.add_all(
        [
            Customer(
                id=ids.NIH,
                company_id=company.id,
                name="NIH Grant Office",
                payment_terms="Net 45",
            ),
            Customer(
                id=ids.ATLAS,
                company_id=company.id,
                name="Atlas Pharma Partnership",
                payment_terms="Net 30",
            ),
        ]
    )
    session.flush()

    cash = Account(
        id=ids.CASH,
        company_id=company.id,
        code="1000",
        name="Operating cash",
        account_type=AccountType.ASSET.value,
        is_cash=True,
    )
    ap_acct = Account(
        id=ids.AP,
        company_id=company.id,
        code="2000",
        name="Accounts payable",
        account_type=AccountType.LIABILITY.value,
    )
    cloud = Account(
        id=ids.EXPENSE_CLOUD,
        company_id=company.id,
        code="6100",
        name="Cloud & compute",
        account_type=AccountType.EXPENSE.value,
    )
    lab = Account(
        id=ids.EXPENSE_LAB,
        company_id=company.id,
        code="6200",
        name="Lab supplies",
        account_type=AccountType.EXPENSE.value,
    )
    rent = Account(
        id=ids.EXPENSE_RENT,
        company_id=company.id,
        code="6300",
        name="Facilities rent",
        account_type=AccountType.EXPENSE.value,
    )
    capex = Account(
        id=ids.CAPEX,
        company_id=company.id,
        code="1500",
        name="Lab equipment / capex",
        account_type=AccountType.ASSET.value,
    )
    equity = Account(
        company_id=company.id,
        code="3000",
        name="Opening balances / equity",
        account_type=AccountType.EQUITY.value,
    )
    session.add_all([cash, ap_acct, cloud, lab, rent, capex, equity])
    session.flush()

    txn = Transaction(
        company_id=company.id,
        account_id=cash.id,
        amount=Decimal("2412550.00"),
        posted_at=AS_OF - timedelta(days=21),
        description="Operating cash balance (seed snapshot)",
        source=TransactionSource.SEED.value,
        is_sandbox=False,
    )
    session.add(txn)
    session.flush()
    session.add_all(
        [
            LedgerEntry(
                company_id=company.id,
                transaction_id=txn.id,
                account_id=cash.id,
                debit=Decimal("2412550.00"),
                credit=Decimal("0.00"),
                period="2026-08",
                memo="Seed cash snapshot",
            ),
            LedgerEntry(
                company_id=company.id,
                transaction_id=txn.id,
                account_id=equity.id,
                debit=Decimal("0.00"),
                credit=Decimal("2412550.00"),
                period="2026-08",
                memo="Opening balance equity (seed snapshot)",
            ),
        ]
    )

    budget = Budget(
        id=ids.BUDGET_Q3,
        company_id=company.id,
        name="Q3 FY2026 operating + capex",
        period="2026-Q3",
        owner_employee_id=ids.ELENA_EMP,
    )
    session.add(budget)
    session.add_all(
        [
            BudgetLine(
                company_id=company.id,
                budget_id=budget.id,
                account_id=cloud.id,
                category="Cloud & compute",
                amount=Decimal("180000.00"),
                spent_amount=Decimal("112400.00"),
            ),
            BudgetLine(
                company_id=company.id,
                budget_id=budget.id,
                account_id=capex.id,
                category="Eval cluster capex",
                amount=Decimal("120000.00"),
                spent_amount=Decimal("0.00"),
            ),
        ]
    )

    def doc(id_, filename: str, klass: str, text: str, mime: str = "text/plain") -> Document:
        row = Document(
            id=id_,
            company_id=company.id,
            filename=filename,
            mime_type=mime,
            storage_backend=StorageBackend.LOCAL.value,
            storage_uri=f"data/demo/inbox/{filename}",
            document_class=klass,
            extraction_status=ExtractionStatus.EXTRACTED.value,
            content_hash=_hash(text),
            ingested_at=AS_OF - timedelta(hours=6),
            raw_text=text,
        )
        session.add(row)
        return row

    doc(
        ids.DOC_HELIX_A,
        "INV_helix_10441_FINAL(2).pdf.txt",
        DocumentClass.INVOICE.value,
        "HelixCloud Invoice 10441 Amount due $18,400.00",
    )
    doc(
        ids.DOC_HELIX_B,
        "scan_img_8821_helixcloud_invoice.PDF.txt",
        DocumentClass.INVOICE.value,
        "HelixCloud Invoice 10441-A Amount due $18,400.00 DUPLICATE",
    )
    doc(
        ids.DOC_APEX,
        "apex scientific inv 9920 overdue.TXT",
        DocumentClass.INVOICE.value,
        "Apex Scientific INV-9920 $42,100.00 OVERDUE",
    )
    doc(
        ids.DOC_POLICY,
        "Spend Policy v3 REALLY FINAL.docx.txt",
        DocumentClass.POLICY.value,
        SPEND_POLICY_BODY,
    )
    doc(
        ids.DOC_MSA,
        "HelixCloud_MSA_2024_executed.pdf.txt",
        DocumentClass.CONTRACT.value,
        HELIX_MSA,
    )
    doc(
        ids.DOC_STMT,
        "BankStmt_Aug2026 weird export.csv",
        DocumentClass.STATEMENT.value,
        "operating cash 2412550.00",
    )
    doc(
        ids.DOC_GPU_QUOTE,
        "gpu quote Q4 eval cluster.txt",
        DocumentClass.OTHER.value,
        "2x inference GPU total $67,000 sandbox catalog",
    )
    session.flush()

    policy = Policy(
        id=ids.POLICY_SPEND,
        company_id=company.id,
        name="Spend & Authority Policy",
        policy_type=PolicyType.SPEND.value,
        version="3",
        body=SPEND_POLICY_BODY,
        rules={
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
            "po_exempt_vendor_ids": [
                "aaaaaaaa-bbbb-cccc-dddd-000000000033",
                "aaaaaaaa-bbbb-cccc-dddd-000000000032",
            ],
            "document_required_above": 100,
        },
        effective_at=datetime(2026, 7, 1, tzinfo=UTC),
        status=PolicyStatus.ACTIVE.value,
        document_id=ids.DOC_POLICY,
    )
    session.add(policy)
    session.add(
        Contract(
            id=ids.CONTRACT_HELIX,
            company_id=company.id,
            vendor_id=helix.id,
            document_id=ids.DOC_MSA,
            title="HelixCloud Master Services Agreement",
            start_date=date(2024, 11, 1),
            end_date=date(2026, 10, 31),
            value=Decimal("220000.00"),
            status=ContractStatus.ACTIVE.value,
            extracted_terms={
                "auto_renewal_notice_days": 30,
                "liability_cap": "12 months of fees",
                "payment_terms": "Net 15",
                "seat_burst": "list price overage",
            },
        )
    )

    inv_a = Invoice(
        id=ids.INV_HELIX_A,
        company_id=company.id,
        vendor_id=helix.id,
        invoice_number="10441",
        direction=InvoiceDirection.AP.value,
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 16),
        subtotal=Decimal("18400.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("18400.00"),
        status=InvoiceStatus.APPROVED.value,
        document_id=ids.DOC_HELIX_A,
        is_duplicate_suspect=False,
    )
    inv_b = Invoice(
        id=ids.INV_HELIX_B,
        company_id=company.id,
        vendor_id=helix.id,
        invoice_number="10441-A",
        direction=InvoiceDirection.AP.value,
        issue_date=date(2026, 9, 3),
        due_date=date(2026, 9, 18),
        subtotal=Decimal("18400.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("18400.00"),
        status=InvoiceStatus.REJECTED.value,
        document_id=ids.DOC_HELIX_B,
        is_duplicate_suspect=True,
    )
    inv_apex = Invoice(
        id=ids.INV_APEX,
        company_id=company.id,
        vendor_id=apex.id,
        invoice_number="INV-9920",
        direction=InvoiceDirection.AP.value,
        issue_date=date(2026, 7, 13),
        due_date=date(2026, 8, 12),
        subtotal=Decimal("42100.00"),
        total=Decimal("42100.00"),
        status=InvoiceStatus.NEEDS_REVIEW.value,
        document_id=ids.DOC_APEX,
    )
    inv_metro = Invoice(
        id=ids.INV_METRO,
        company_id=company.id,
        vendor_id=ids.METRO_REIT,
        invoice_number="RENT-2026-09",
        direction=InvoiceDirection.AP.value,
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 1),
        subtotal=Decimal("28000.00"),
        total=Decimal("28000.00"),
        status=InvoiceStatus.SCHEDULED.value,
    )
    session.add_all([inv_a, inv_b, inv_apex, inv_metro])
    session.flush()
    session.add_all(
        [
            InvoiceLine(
                company_id=company.id,
                invoice_id=inv_a.id,
                description="Aug 2026 GPU/CPU burst",
                quantity=Decimal("1"),
                unit_price=Decimal("18400.00"),
                amount=Decimal("18400.00"),
                account_id=cloud.id,
                gl_code="6100",
            ),
            InvoiceLine(
                company_id=company.id,
                invoice_id=inv_b.id,
                description="Aug 2026 GPU/CPU burst (duplicate)",
                quantity=Decimal("1"),
                unit_price=Decimal("18400.00"),
                amount=Decimal("18400.00"),
                account_id=cloud.id,
                gl_code="6100",
            ),
            InvoiceLine(
                company_id=company.id,
                invoice_id=inv_apex.id,
                description="Reagents and cold-chain",
                quantity=Decimal("1"),
                unit_price=Decimal("42100.00"),
                amount=Decimal("42100.00"),
                account_id=lab.id,
                gl_code="6200",
            ),
        ]
    )

    po = PurchaseOrder(
        id=ids.PO_GPU,
        company_id=company.id,
        vendor_id=ids.NVIDIA_OEM,
        po_number="PO-2026-0918-GPU",
        status=POStatus.AWAITING_APPROVAL.value,
        requested_by_user_id=jordan.id,
        needed_by=date(2026, 10, 6),
        total=Decimal("67000.00"),
        budget_id=budget.id,
        notes=(
            "Natural-language need: two inference GPUs for the Q4 eval cluster. "
            "Budget remaining on eval capex is $120,000. Dual approval required. "
            "Purchase would be Visa SANDBOX / simulated — not a live transfer."
        ),
    )
    session.add(po)
    session.add(
        PurchaseOrderLine(
            id=ids.PO_GPU_LINE,
            company_id=company.id,
            purchase_order_id=po.id,
            description="Inference GPU (sandbox catalog) x2",
            quantity=Decimal("2"),
            unit_price=Decimal("33500.00"),
            amount=Decimal("67000.00"),
            account_id=capex.id,
        )
    )

    session.add_all(
        [
            Evidence(
                id=ids.EVIDENCE_DUP_A,
                company_id=company.id,
                evidence_type="invoice",
                source_system="local",
                uri="data/demo/inbox/INV_helix_10441_FINAL(2).pdf.txt",
                title="HelixCloud invoice 10441",
                snippet="Amount due: $18,400.00",
                content_hash=_hash("10441"),
            ),
            Evidence(
                id=ids.EVIDENCE_DUP_B,
                company_id=company.id,
                evidence_type="invoice",
                source_system="local",
                uri="data/demo/inbox/scan_img_8821_helixcloud_invoice.PDF.txt",
                title="HelixCloud invoice 10441-A",
                snippet="DUPLICATE of 10441 with suffix -A",
                content_hash=_hash("10441-A"),
            ),
            Evidence(
                id=ids.EVIDENCE_POLICY,
                company_id=company.id,
                evidence_type="policy_clause",
                source_system="local",
                uri="data/demo/inbox/Spend Policy v3 REALLY FINAL.docx.txt",
                title="Duplicate invoice block (clause 6)",
                snippet="Duplicate vendor invoices ... are blocked, not paid.",
            ),
            Evidence(
                id=ids.EVIDENCE_SIGNAL,
                company_id=company.id,
                evidence_type="public_series",
                source_system="public_data",
                uri="https://fred.stlouisfed.org/series/DGS3MO",
                title="3-month Treasury yield (seeded public snapshot)",
                snippet="DGS3MO 4.22 percent as of 2026-09-18",
            ),
        ]
    )

    finding_dup = Finding(
        id=ids.FINDING_DUP,
        company_id=company.id,
        finding_type="duplicate_invoice",
        severity=Severity.HIGH.value,
        title="Duplicate HelixCloud AP $18,400 blocked",
        description=(
            "Invoice 10441-A matches 10441 on vendor, amount, and near invoice number. "
            "Spend policy v3 clause 6 requires a block. Dollars protected: $18,400."
        ),
        status=FindingStatus.ACKNOWLEDGED.value,
        related_object_type="invoice",
        related_object_id=inv_b.id,
    )
    finding_od = Finding(
        id=ids.FINDING_OVERDUE,
        company_id=company.id,
        finding_type="overdue_ap",
        severity=Severity.MEDIUM.value,
        title="Apex Scientific INV-9920 overdue 38 days",
        description="Cold-chain vendor. Pay vs dispute is a controller question.",
        status=FindingStatus.OPEN.value,
        related_object_type="invoice",
        related_object_id=inv_apex.id,
    )
    session.add_all([finding_dup, finding_od])

    run_ap = AgentRun(
        id=ids.RUN_AP,
        company_id=company.id,
        workflow_type="ap_intake",
        status=AgentRunStatus.COMPLETED.value,
        initiated_by=ActorType.MIRA.value,
        plan={
            "steps": [
                "classify inbox",
                "extract invoices",
                "duplicate check",
                "policy",
                "mira review",
            ]
        },
        started_at=AS_OF - timedelta(hours=5),
        completed_at=AS_OF - timedelta(hours=4, minutes=40),
    )
    run_proc = AgentRun(
        id=ids.RUN_PROCURE,
        company_id=company.id,
        workflow_type="procurement",
        status=AgentRunStatus.AWAITING_HUMAN.value,
        initiated_by=ActorType.USER.value,
        initiator_id=str(jordan.id),
        plan={
            "steps": [
                "parse need",
                "budget check",
                "policy check",
                "vendor select",
                "human dual approval",
                "visa sandbox",
                "invoice",
                "reconcile",
            ],
            "sandbox": True,
        },
        started_at=AS_OF - timedelta(hours=2),
    )
    session.add_all([run_ap, run_proc])
    session.flush()
    session.add_all(
        [
            AgentTask(
                id=ids.TASK_INTAKE,
                company_id=company.id,
                agent_run_id=run_ap.id,
                agent_role=AgentRole.EVIDENCE.value,
                status=AgentTaskStatus.COMPLETED.value,
                input_payload={"inbox": "data/demo/inbox"},
                result_type="AgentTaskResult",
                result_payload={"artifact_type": "documents", "count": 8},
                started_at=AS_OF - timedelta(hours=5),
                completed_at=AS_OF - timedelta(hours=4, minutes=50),
            ),
            AgentTask(
                id=ids.TASK_DUP,
                company_id=company.id,
                agent_run_id=run_ap.id,
                agent_role=AgentRole.ACCOUNTS_PAYABLE.value,
                status=AgentTaskStatus.COMPLETED.value,
                input_payload={"invoice_id": str(inv_b.id)},
                result_type="ReconciliationResult",
                result_payload={
                    "case_type": "duplicate",
                    "status": "duplicate",
                    "explanation": "10441-A is a duplicate of 10441",
                },
                started_at=AS_OF - timedelta(hours=4, minutes=50),
                completed_at=AS_OF - timedelta(hours=4, minutes=45),
            ),
            AgentTask(
                id=ids.TASK_POLICY,
                company_id=company.id,
                agent_run_id=run_proc.id,
                agent_role=AgentRole.POLICY.value,
                status=AgentTaskStatus.COMPLETED.value,
                input_payload={"po_id": str(po.id)},
                result_type="HumanEscalation",
                result_payload={
                    "question": "Approve sandbox GPU purchase of $67,000?",
                    "why_uncertain": "Amount exceeds dual-approval threshold",
                },
                started_at=AS_OF - timedelta(hours=2),
                completed_at=AS_OF - timedelta(hours=1, minutes=50),
            ),
        ]
    )

    session.add(
        RiskAssessment(
            id=ids.RISK_DUP,
            company_id=company.id,
            subject_type="invoice",
            subject_id=inv_b.id,
            risk_level=RiskLevel.HIGH.value,
            risk_score=Decimal("82.00"),
            factors=[
                {"code": "duplicate_amount", "points": 40, "note": "Exact $18,400 match"},
                {"code": "invoice_number_near", "points": 25, "note": "10441 vs 10441-A"},
                {"code": "same_vendor_14d", "points": 17, "note": "HelixCloud within 2 days"},
            ],
            engine_version="risk-0",
            assessed_at=AS_OF - timedelta(hours=4, minutes=44),
        )
    )
    session.add(
        RiskAssessment(
            id=ids.RISK_GPU,
            company_id=company.id,
            subject_type="purchase_order",
            subject_id=po.id,
            risk_level=RiskLevel.HIGH.value,
            risk_score=Decimal("71.00"),
            factors=[
                {"code": "amount_over_10k", "points": 35, "note": "$67,000 > dual approval"},
                {"code": "new_capex_sku", "points": 20, "note": "Not a preferred repeat SKU"},
                {"code": "sandbox_merchant", "points": 16, "note": "Visa sandbox catalog"},
            ],
            engine_version="risk-0",
            assessed_at=AS_OF - timedelta(hours=1, minutes=48),
        )
    )

    dec_dup = Decision(
        id=ids.DECISION_DUP,
        company_id=company.id,
        decision_type="invoice_block",
        status=DecisionStatus.EXECUTED.value,
        action="reject_duplicate_invoice",
        rationale=(
            "I blocked HelixCloud 10441-A. It is the same $18,400 as 10441 with a suffix. "
            "Spend policy v3 clause 6 is the authority. No human needed."
        ),
        structured_output={
            "type": "InvoiceDecision",
            "action": "reject",
            "invoice_id": str(inv_b.id),
            "duplicate_of_invoice_id": str(inv_a.id),
            "requires_human_approval": False,
        },
        confidence_score=Decimal("0.9600"),
        risk_level=RiskLevel.HIGH.value,
        policy_basis="Spend & Authority Policy v3 clause 6 (duplicate block)",
        authority_basis="Mira autonomous AP control; no spend occurs",
        requires_human_approval=False,
        agent_run_id=run_ap.id,
        subject_type="invoice",
        subject_id=inv_b.id,
        dollars_impact=Decimal("18400.00"),
        hours_saved_estimate=Decimal("1.50"),
    )
    dec_gpu = Decision(
        id=ids.DECISION_GPU,
        company_id=company.id,
        decision_type="procurement",
        status=DecisionStatus.AWAITING_HUMAN.value,
        action="request_dual_approval_sandbox_purchase",
        rationale=(
            "Need: two inference GPUs for the Q4 eval cluster. Budget remaining on eval "
            "capex is $120,000 so the $67,000 request clears the budget engine. Policy v3 "
            "clause 3 requires dual approval above $10,000. I will not place the Visa "
            "sandbox order until Elena and Jordan sign. This is a SANDBOX / simulated "
            "purchase, not a live transfer."
        ),
        structured_output={
            "type": "HumanEscalation",
            "question": "Approve sandbox GPU purchase of $67,000 against eval capex?",
            "requires_human_approval": True,
            "is_sandbox_purchase": True,
        },
        confidence_score=Decimal("0.5400"),
        risk_level=RiskLevel.HIGH.value,
        policy_basis="Spend & Authority Policy v3 clause 3 (dual approval > $10,000)",
        authority_basis="Mira cannot execute spend above $2,500 without a human",
        requires_human_approval=True,
        agent_run_id=run_proc.id,
        subject_type="purchase_order",
        subject_id=po.id,
        dollars_impact=Decimal("67000.00"),
        hours_saved_estimate=Decimal("3.00"),
    )
    session.add_all([dec_dup, dec_gpu])
    session.flush()
    session.add(
        Approval(
            id=ids.APPROVAL_GPU,
            company_id=company.id,
            subject_type="decision",
            subject_id=dec_gpu.id,
            requested_by_user_id=jordan.id,
            approver_user_id=elena.id,
            status=ApprovalStatus.PENDING.value,
            decision_id=dec_gpu.id,
            risk_level=RiskLevel.HIGH.value,
            confidence_score=Decimal("0.5400"),
            comment="Awaiting CFO + Controller dual approval. Visa path is sandbox.",
        )
    )

    session.add_all(
        [
            EvidenceReferenceRow(
                company_id=company.id,
                evidence_id=ids.EVIDENCE_DUP_A,
                object_type="decision",
                object_id=dec_dup.id,
                source_system="local",
                locator="invoice:10441",
                excerpt="Amount due: $18,400.00",
                role="supporting",
                captured_at=AS_OF,
            ),
            EvidenceReferenceRow(
                company_id=company.id,
                evidence_id=ids.EVIDENCE_DUP_B,
                object_type="decision",
                object_id=dec_dup.id,
                source_system="local",
                locator="invoice:10441-A",
                excerpt="DUPLICATE of 10441",
                role="supporting",
                captured_at=AS_OF,
            ),
            EvidenceReferenceRow(
                company_id=company.id,
                evidence_id=ids.EVIDENCE_POLICY,
                object_type="decision",
                object_id=dec_dup.id,
                source_system="local",
                locator="clause:6",
                excerpt="Duplicate vendor invoices ... are blocked, not paid.",
                role="policy_basis",
                captured_at=AS_OF,
            ),
        ]
    )

    session.add(
        Precedent(
            id=ids.PRECEDENT_SAAS,
            company_id=company.id,
            situation_hash=_hash("rush-saas-seats-no-vp-it")[:64],
            summary="April 2026: Elena rejected a rush HelixCloud seat burst without VP IT.",
            outcome="rejected",
            period="2026-04",
            reusable_rule="Rush software or cloud seat expansions require VP IT sign-off.",
        )
    )
    session.add(
        Forecast(
            id=ids.FORECAST_CASH,
            company_id=company.id,
            metric_name="operating_cash",
            period="2026-W42",
            method="linear_13w",
            value=Decimal("1984000.00"),
            lower=Decimal("1760000.00"),
            upper=Decimal("2140000.00"),
            currency="USD",
            inputs_hash=_hash("cash-13w-seed"),
            engine_version="forecast-0",
        )
    )
    session.add_all(
        [
            Metric(
                company_id=company.id,
                name="cash",
                period=PERIOD,
                value=Decimal("2412550.00"),
                unit="usd",
                source=MetricSource.SEED.value,
            ),
            Metric(
                company_id=company.id,
                name="open_ap",
                period=PERIOD,
                value=Decimal("70100.00"),
                unit="usd",
                source=MetricSource.SEED.value,
            ),
            Metric(
                company_id=company.id,
                name="monthly_burn",
                period=PERIOD,
                value=Decimal("510000.00"),
                unit="usd",
                source=MetricSource.SEED.value,
            ),
        ]
    )
    session.add_all(
        [
            SavingsEvent(
                id=ids.SAVINGS_DUP,
                company_id=company.id,
                category=SavingsCategory.DUPLICATE_PREVENTED.value,
                amount_usd=Decimal("18400.00"),
                hours_saved=Decimal("1.50"),
                workflow="ap_intake",
                period=PERIOD,
                related_object_type="invoice",
                related_object_id=inv_b.id,
                note="HelixCloud 10441-A blocked as duplicate of 10441",
            ),
            SavingsEvent(
                id=ids.SAVINGS_HOURS,
                company_id=company.id,
                category=SavingsCategory.INTAKE_HOURS.value,
                amount_usd=Decimal("0.00"),
                hours_saved=Decimal("6.50"),
                workflow="ap_intake",
                period=PERIOD,
                note="Inbox classification + coding that would have been Sam's morning",
            ),
            SavingsEvent(
                company_id=company.id,
                category=SavingsCategory.POLICY_BLOCK.value,
                amount_usd=Decimal("12820.00"),
                hours_saved=Decimal("2.00"),
                workflow="policy",
                period=PERIOD,
                note="Out-of-policy rush SaaS seats held pending VP IT (precedent 2026-04)",
            ),
        ]
    )
    session.add_all(
        [
            ExternalSignal(
                id=ids.SIGNAL_DGS3MO,
                company_id=company.id,
                source="FRED",
                series_id="DGS3MO",
                as_of=date(2026, 9, 18),
                value=Decimal("4.220000"),
                unit="percent",
                title="3-month Treasury yield",
                note=(
                    "Seeded public snapshot for demo. Idle operating cash earns ~0%; "
                    "public T-bill yield is 4.22%. Flag for Elena — not investment advice."
                ),
                uri="https://fred.stlouisfed.org/series/DGS3MO",
            ),
            ExternalSignal(
                id=ids.SIGNAL_CPI,
                company_id=company.id,
                source="FRED",
                series_id="CPIAUCSL",
                as_of=date(2026, 8, 31),
                value=Decimal("323.400000"),
                unit="index",
                title="CPI-U (seeded snapshot)",
                note="Lab supply inflation context for Apex Scientific pricing.",
                uri="https://fred.stlouisfed.org/series/CPIAUCSL",
            ),
        ]
    )

    session.add(
        AuditEvent(
            company_id=company.id,
            occurred_at=AS_OF,
            actor_type=ActorType.SYSTEM.value,
            actor_id="seed",
            event_type="company.seeded",
            object_type="company",
            object_id=company.id,
            payload={"slug": "northstar-labs", "sandbox": True},
        )
    )
    session.add(
        AuditEvent(
            company_id=company.id,
            occurred_at=AS_OF - timedelta(hours=4, minutes=40),
            actor_type=ActorType.MIRA.value,
            actor_id="mira",
            event_type="decision.executed",
            object_type="decision",
            object_id=dec_dup.id,
            correlation_id=run_ap.id,
            payload={"action": "reject_duplicate_invoice", "dollars": "18400.00"},
        )
    )
    session.add(
        AuditEvent(
            company_id=company.id,
            occurred_at=AS_OF - timedelta(hours=1, minutes=40),
            actor_type=ActorType.MIRA.value,
            actor_id="mira",
            event_type="decision.escalated",
            object_type="decision",
            object_id=dec_gpu.id,
            correlation_id=run_proc.id,
            payload={"action": "request_dual_approval_sandbox_purchase", "is_sandbox": True},
        )
    )
    from mira.seed.phase2 import seed_phase2

    seed_phase2(session, company.id)
    return company


def seed_from_url(database_url: str) -> None:
    from mira.core.db import create_schema, get_engine, get_sessionmaker

    engine = get_engine(database_url)
    create_schema(engine)
    SessionLocal = get_sessionmaker(database_url)
    session = SessionLocal()
    try:
        seed_northstar(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    import os

    url = os.environ.get("DATABASE_URL", "sqlite:///./data/mira.db")
    Path("data").mkdir(exist_ok=True)
    seed_from_url(url)
    print(f"Seeded Northstar Labs into {url}")


if __name__ == "__main__":
    main()
