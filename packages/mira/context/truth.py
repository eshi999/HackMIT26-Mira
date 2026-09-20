"""Invoke existing tools on the FULL snapshot, before any context selection."""

import json

from mira.agents.tools import (
    collect_aws_spend_evidence,
    tool_assess_risk,
    tool_evaluate_contract,
    tool_evaluate_invoice,
    tool_evaluate_policy,
    tool_get_ar_aging,
    tool_get_cash_position,
    tool_reconcile_period,
)
from mira.context.encoding import encode
from mira.context.models import ContextRequest, Profile
from mira.finance.snapshot import FinanceSnapshot
from mira.forecasting.cash import afford_engineers


def deterministic_truth(snapshot: FinanceSnapshot, request: ContextRequest) -> dict:
    if snapshot.company_id != request.company_id:
        raise ValueError("Context company does not match snapshot")
    profile = request.profile
    if request.subject_id is not None and profile != Profile.AP_INVOICE_REVIEW:
        raise ValueError("Subject-specific context currently requires the AP profile")
    if request.vendor_id is not None and profile not in {
        Profile.AP_INVOICE_REVIEW,
        Profile.CFO_VARIANCE_INVESTIGATION,
    }:
        raise ValueError("Vendor-specific context currently requires AP or AWS variance")
    if request.customer_id is not None:
        if profile != Profile.EXECUTIVE_QUESTION:
            raise ValueError("Customer retrieval currently requires the executive profile")
        if not any(v.id == request.customer_id for v in snapshot.customers):
            raise ValueError("Customer is not present in the canonical snapshot")
    result: dict = {}
    if profile == Profile.AP_INVOICE_REVIEW:
        invoice = snapshot.invoice(request.subject_id) if request.subject_id else None
        if invoice is None or invoice.direction != "ap":
            raise ValueError("AP review requires a canonical AP invoice")
        if request.vendor_id and request.vendor_id != invoice.vendor_id:
            raise ValueError("Invoice vendor does not match requested vendor")
        result = {
            "match": tool_evaluate_invoice(snapshot, invoice.id),
            "policy": tool_evaluate_policy(snapshot, subject_type="invoice", subject_id=invoice.id),
            "contract": tool_evaluate_contract(snapshot, invoice.id),
            "risk": tool_assess_risk(snapshot, invoice.id),
        }
    elif profile == Profile.TREASURY_RECONCILIATION:
        result = {
            "reconciliation": tool_reconcile_period(snapshot),
            "cash": tool_get_cash_position(snapshot),
        }
    elif profile == Profile.CFO_VARIANCE_INVESTIGATION:
        # This first implementation supports the existing AWS investigation tool.
        aws = next(
            (
                v
                for v in snapshot.vendors
                if "aws" in v.name.lower() or "amazon web" in v.name.lower()
            ),
            None,
        )
        if request.vendor_id and (aws is None or request.vendor_id != aws.id):
            raise ValueError("Variance profile currently supports AWS only")
        period = request.period or snapshot.as_of.strftime("%Y-%m")
        result = {
            "aws_spend": collect_aws_spend_evidence(snapshot, period),
            "cash": tool_get_cash_position(snapshot),
        }
    elif profile == Profile.FPNA_SCENARIO:
        result = {"forecast": afford_engineers(snapshot, headcount=request.headcount)}
    elif profile == Profile.AUDIT_REVIEW:
        result = {
            "risk": tool_assess_risk(snapshot),
            "reconciliation": tool_reconcile_period(snapshot),
        }
    elif profile == Profile.EXECUTIVE_QUESTION:
        result = {
            "cash": tool_get_cash_position(snapshot),
            "ar_aging": tool_get_ar_aging(snapshot),
            "risk": tool_assess_risk(snapshot),
        }
    return json.loads(encode(result))
