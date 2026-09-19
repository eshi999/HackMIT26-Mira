"""Stable identifiers for the Northstar Labs demo tenant."""

from __future__ import annotations

from uuid import UUID, uuid5


def _u(n: int) -> UUID:
    return UUID(f"aaaaaaaa-bbbb-cccc-dddd-{n:012d}")


FILLER_NS = UUID("bbbbbbbb-cccc-dddd-eeee-000000000001")


def filler(kind: str, n: int) -> UUID:
    return uuid5(FILLER_NS, f"{kind}-{n}")


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

# Phase 2 people
PRIYA = _u(13)
MARCUS = _u(14)
AVERY = _u(15)
PRIYA_EMP = _u(23)
MARCUS_EMP = _u(24)
AVERY_EMP = _u(25)

# Phase 2 vendors / customers / accounts
AWS = _u(300)
LABBENCH = _u(301)
COLDCHAIN = _u(302)
FIGMA = _u(303)
NOTION = _u(304)
SLACK = _u(305)
SHADOWLINK = _u(306)
PULSEDIGEST = _u(307)
QUARTZ = _u(308)
BIOREAGENT = _u(309)
FEDEX = _u(310)
CONSTELLATION = _u(311)
GUSTO = _u(312)
CLEANLAB = _u(313)
HARBOR_GLASS = _u(314)
DATADOG = _u(315)
GITHUB = _u(316)
ZOOM = _u(317)
OFFICE_DEPOT = _u(318)
WEWORK = _u(319)

BOSTON_CHILDRENS = _u(42)
MASS_GRANT = _u(43)

AR = _u(56)
REVENUE = _u(57)
EXPENSE_SAAS = _u(58)
EXPENSE_PAYROLL = _u(59)
EXPENSE_UTIL = _u(61)
EXPENSE_PROF = _u(62)
EXPENSE_SHIP = _u(63)

DOC_VOLUME = _u(97)
DOC_COLDCHAIN = _u(98)
POLICY_VENDOR = _u(102)
CONTRACT_COLDCHAIN = _u(103)
CONTRACT_AWS = _u(104)
PRECEDENT_AWS = _u(181)

SUB_AWS = _u(850)
SUB_FIGMA = _u(851)
SUB_NOTION = _u(852)
SUB_SLACK = _u(853)

# Scenario 1 duplicate $4,850
INV_4850 = _u(500)
INV_4850A = _u(501)
# Scenario 2 invoice exceeds PO
PO_EXCEED = _u(600)
PO_EXCEED_LINE = _u(601)
GR_EXCEED = _u(650)
GR_EXCEED_LINE = _u(651)
INV_EXCEED = _u(502)
# Scenario 3 self-approve
PO_SELF = _u(602)
PO_SELF_LINE = _u(603)
APPROVAL_SELF = _u(900)
# Scenario 4 one ACH covers three invoices
INV_BIO_A = _u(503)
INV_BIO_B = _u(504)
INV_BIO_C = _u(505)
TXN_ACH_THREE = _u(750)
# Scenario 5 duplicated refund
INV_REFUND = _u(506)
TXN_REFUND_A = _u(751)
TXN_REFUND_B = _u(752)
# Scenario 6 unexplained $12.40
INV_FEE_GAP = _u(507)
TXN_FEE_GAP = _u(753)
# Scenario 7 AWS spike
INV_AWS_JUL = _u(508)
INV_AWS_AUG = _u(509)
INV_AWS_SEP = _u(510)
PO_AWS_JUL = _u(604)
PO_AWS_AUG = _u(605)
PO_AWS_SEP = _u(606)
# Scenario 8 contract 4% vs 11%
INV_COLDCHAIN = _u(511)
# Scenario 9 AR >45 days
INV_ATLAS_OD = _u(512)
# Scenario 10 unused Figma
INV_FIGMA_JUL = _u(513)
INV_FIGMA_AUG = _u(514)
INV_FIGMA_SEP = _u(515)
# Scenario 11 closed-period
INV_CLOSED = _u(516)
# Scenario 12 missing receipt
PO_MISSING_GR = _u(607)
PO_MISSING_GR_LINE = _u(608)
INV_MISSING_GR = _u(517)
# Scenario 13 new vendor
INV_QUARTZ = _u(518)
PO_QUARTZ = _u(609)

# Extra detector plants
PO_AUTHORITY = _u(610)
PO_AUTHORITY_LINE = _u(611)
APPROVAL_AUTHORITY = _u(901)
INV_DUP_PAY = _u(519)
PAY_DUP_A = _u(700)
PAY_DUP_B = _u(701)
INV_MISSING_DOC = _u(520)
INV_MISSING_PO = _u(521)
TXN_ODD_HOURS = _u(754)
PAY_ROUND = _u(702)
INV_ROUND = _u(522)
INV_PULSE_JUL = _u(523)
INV_PULSE_AUG = _u(524)
INV_PULSE_SEP = _u(525)
INV_SHADOW = _u(526)
PO_HELIX = _u(612)
PO_APEX = _u(613)
GR_HELIX = _u(652)
GR_APEX = _u(653)
GR_MISSING_NONE = _u(654)  # unused sentinel
PAY_ROUND_TXN = _u(755)

INV_PULSE = INV_PULSE_SEP
