"""Human-in-the-loop authority. Risk and confidence come from engines."""

from __future__ import annotations

from decimal import Decimal

from mira.core.agent_outputs import AuthorityDecision, Confidence
from mira.core.enums import AuthorityDisposition, RiskLevel

HIGH_CONFIDENCE = Decimal("0.80")


def decide_authority(
    *,
    confidence: Confidence,
    risk_level: RiskLevel,
    is_payment: bool = False,
    is_sandbox: bool = True,
    policy_requires_human: bool = False,
    auditor_rejected: bool = False,
    mandatory_control_failure: bool = False,
) -> AuthorityDecision:
    """HIGH CONFIDENCE + LOW RISK => auto-complete safe internal/sandbox action.

    HIGH CONFIDENCE + HIGH RISK => block/escalate.
    LOW CONFIDENCE => human review.
    Irreversible real-world payments never execute outside an explicit sandbox.
    """
    high_conf = confidence.score >= HIGH_CONFIDENCE
    high_risk = risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    low_risk = risk_level == RiskLevel.LOW

    if is_payment and not is_sandbox:
        return AuthorityDecision(
            disposition=AuthorityDisposition.BLOCK.value,
            auto_complete=False,
            requires_human_approval=True,
            blocks_action=True,
            is_sandbox=False,
            reason="Irreversible real-world payment is forbidden unless an explicitly documented sponsor sandbox is used.",
            confidence=confidence,
            risk_level=risk_level,
        )
    if auditor_rejected:
        return AuthorityDecision(
            disposition=AuthorityDisposition.BLOCK.value if high_risk else AuthorityDisposition.ESCALATE.value,
            auto_complete=False,
            requires_human_approval=True,
            blocks_action=True,
            is_sandbox=is_sandbox,
            reason="Auditor rejected the proposed action on policy, control, evidence, or risk grounds.",
            confidence=confidence,
            risk_level=risk_level,
        )
    if mandatory_control_failure:
        return AuthorityDecision(
            disposition=AuthorityDisposition.BLOCK.value if is_payment else AuthorityDisposition.ESCALATE.value,
            auto_complete=False,
            requires_human_approval=True,
            blocks_action=is_payment,
            is_sandbox=is_sandbox,
            reason="Mandatory evidence, arithmetic, or match failure cannot be offset by a low risk score.",
            confidence=confidence,
            risk_level=risk_level,
        )
    if policy_requires_human or not high_conf:
        return AuthorityDecision(
            disposition=AuthorityDisposition.ESCALATE.value,
            auto_complete=False,
            requires_human_approval=True,
            blocks_action=False,
            is_sandbox=is_sandbox,
            reason=(
                "Policy requires a human approver."
                if policy_requires_human
                else "Low confidence requires human review."
            ),
            confidence=confidence,
            risk_level=risk_level,
        )
    if high_conf and high_risk:
        return AuthorityDecision(
            disposition=AuthorityDisposition.BLOCK.value,
            auto_complete=False,
            requires_human_approval=True,
            blocks_action=True,
            is_sandbox=is_sandbox,
            reason="High confidence combined with high risk must block and escalate.",
            confidence=confidence,
            risk_level=risk_level,
        )
    if high_conf and low_risk:
        if is_payment:
            return AuthorityDecision(
                disposition=AuthorityDisposition.AUTO_COMPLETE.value,
                auto_complete=True,
                requires_human_approval=False,
                blocks_action=False,
                is_sandbox=True,
                reason="High confidence, low risk, sandbox payment path only.",
                confidence=confidence,
                risk_level=risk_level,
            )
        return AuthorityDecision(
            disposition=AuthorityDisposition.AUTO_COMPLETE.value,
            auto_complete=True,
            requires_human_approval=False,
            blocks_action=False,
            is_sandbox=is_sandbox,
            reason="High confidence and low risk: safe internal action may auto-complete.",
            confidence=confidence,
            risk_level=risk_level,
        )
    # Medium risk + high confidence: internal work may auto-complete; payments still escalate.
    if is_payment:
        return AuthorityDecision(
            disposition=AuthorityDisposition.ESCALATE.value,
            auto_complete=False,
            requires_human_approval=True,
            blocks_action=False,
            is_sandbox=is_sandbox,
            reason="Payment with medium residual risk still requires a human.",
            confidence=confidence,
            risk_level=risk_level,
        )
    return AuthorityDecision(
        disposition=AuthorityDisposition.AUTO_COMPLETE.value,
        auto_complete=True,
        requires_human_approval=False,
        blocks_action=False,
        is_sandbox=is_sandbox,
        reason="High confidence internal action with medium risk may auto-complete.",
        confidence=confidence,
        risk_level=risk_level,
    )
