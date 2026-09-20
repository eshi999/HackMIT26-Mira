from mira.context.models import ContextProfile, Profile

ALL_CATEGORIES = frozenset(
    {
        "vendors",
        "customers",
        "users",
        "employees",
        "invoices",
        "purchase_orders",
        "receipts",
        "payments",
        "transactions",
        "contracts",
        "policies",
        "approvals",
        "subscriptions",
        "precedents",
        "factual_memories",
        "historical_memories",
        "evidence",
        "documents",
        "decisions",
        "savings",
        "metrics",
        "forecasts",
    }
)
CONTROLS = {"policies", "approvals", "decisions"}


def _profile(required: set[str], optional: set[str]) -> ContextProfile:
    required = required | CONTROLS
    optional = optional - required
    return ContextProfile(
        required=frozenset(required),
        optional=frozenset(optional),
        irrelevant=ALL_CATEGORIES - required - optional,
    )


PROFILES = {
    Profile.AP_INVOICE_REVIEW: _profile(
        {
            "invoices",
            "purchase_orders",
            "receipts",
            "vendors",
            "documents",
            "evidence",
            "precedents",
            "contracts",
        },
        {"factual_memories", "historical_memories"},
    ),
    Profile.TREASURY_RECONCILIATION: _profile(
        {"transactions", "payments"}, {"invoices", "vendors", "evidence", "documents"}
    ),
    Profile.CFO_VARIANCE_INVESTIGATION: _profile(
        {"invoices", "vendors", "contracts", "precedents"},
        {"historical_memories", "factual_memories", "evidence", "documents", "metrics"},
    ),
    Profile.FPNA_SCENARIO: _profile(
        {"metrics", "forecasts"}, {"employees", "invoices", "historical_memories"}
    ),
    Profile.AUDIT_REVIEW: _profile(
        {"evidence", "documents", "precedents"},
        {"invoices", "transactions", "payments", "contracts", "vendors"},
    ),
    Profile.EXECUTIVE_QUESTION: _profile(
        {"metrics"},
        {
            "forecasts",
            "historical_memories",
            "factual_memories",
            "savings",
            "precedents",
            "customers",
            "invoices",
        },
    ),
}


def select_profile(task: str) -> Profile:
    """Explicit application task mapping, never an authority decision by a model."""
    return {
        "invoice_review": Profile.AP_INVOICE_REVIEW,
        "reconciliation": Profile.TREASURY_RECONCILIATION,
        "aws_spend": Profile.CFO_VARIANCE_INVESTIGATION,
        "hiring_scenario": Profile.FPNA_SCENARIO,
        "audit_review": Profile.AUDIT_REVIEW,
        "executive_question": Profile.EXECUTIVE_QUESTION,
    }[task]
