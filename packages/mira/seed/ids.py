"""Stable identifiers for the Northstar Labs demo tenant."""

from __future__ import annotations

from uuid import UUID


def _u(n: int) -> UUID:
    return UUID(f"aaaaaaaa-bbbb-cccc-dddd-{n:012d}")


COMPANY = _u(1)

ELENA = _u(10)
JORDAN = _u(11)
SAM = _u(12)

ELENA_EMP = _u(20)
JORDAN_EMP = _u(21)
SAM_EMP = _u(22)

HELIX = _u(30)
APEX = _u(31)
NA_INSURANCE = _u(32)
METRO_REIT = _u(33)
NVIDIA_OEM = _u(34)

NIH = _u(40)
ATLAS = _u(41)

CASH = _u(50)
AP = _u(51)
EXPENSE_CLOUD = _u(52)
EXPENSE_LAB = _u(53)
EXPENSE_RENT = _u(54)
CAPEX = _u(55)

BUDGET_Q3 = _u(60)

PO_GPU = _u(70)
PO_GPU_LINE = _u(71)

INV_HELIX_A = _u(80)
INV_HELIX_B = _u(81)
INV_APEX = _u(82)
INV_METRO = _u(83)

DOC_HELIX_A = _u(90)
DOC_HELIX_B = _u(91)
DOC_APEX = _u(92)
DOC_POLICY = _u(93)
DOC_MSA = _u(94)
DOC_STMT = _u(95)
DOC_GPU_QUOTE = _u(96)

POLICY_SPEND = _u(100)
CONTRACT_HELIX = _u(101)

FINDING_DUP = _u(110)
FINDING_OVERDUE = _u(111)

DECISION_DUP = _u(120)
DECISION_GPU = _u(121)

APPROVAL_GPU = _u(130)

RUN_AP = _u(140)
RUN_PROCURE = _u(141)

TASK_INTAKE = _u(150)
TASK_DUP = _u(151)
TASK_POLICY = _u(152)

SIGNAL_DGS3MO = _u(160)
SIGNAL_CPI = _u(161)

SAVINGS_DUP = _u(170)
SAVINGS_HOURS = _u(171)

PRECEDENT_SAAS = _u(180)

FORECAST_CASH = _u(190)

RISK_GPU = _u(200)
RISK_DUP = _u(201)

EVIDENCE_DUP_A = _u(210)
EVIDENCE_DUP_B = _u(211)
EVIDENCE_POLICY = _u(212)
EVIDENCE_SIGNAL = _u(213)
