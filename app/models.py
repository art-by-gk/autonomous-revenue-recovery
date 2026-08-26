from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FailureReason(str, Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    TIMEOUT = "timeout"
    EXPIRED_INSTRUMENT = "expired_instrument"
    LIMIT_EXCEEDED = "limit_exceeded"
    SUSPICIOUS_TRANSACTION = "suspicious_transaction"


class ActionType(str, Enum):
    SMART_RETRY = "SMART_RETRY_SCHEDULED"
    HINGLISH_WHATSAPP = "HINGLISH_WHATSAPP_NUDGE"
    TOKEN_UPDATE_LINK = "MANDATE_UPDATE_LINK_SENT"
    HUMAN_ESCALATION = "ESCALATE_TO_RISK_TEAM"
    STOP_TERMINATE = "STOP_MAX_RETRIES"
    GENERIC_EMAIL = "GENERIC_EMAIL_REMINDER"


class RecoveryStatus(str, Enum):
    PENDING_RETRY = "PENDING_RETRY"
    RECOVERED = "RECOVERED"
    STOPPED = "STOPPED_MAX_ATTEMPTS"
    ESCALATED = "ESCALATED_HUMAN_REVIEW"


class PaymentEvent(BaseModel):
    id: str
    customer_name: str
    customer_phone: str = "+919876543210"
    amount: float
    payment_method: str = "upi"
    failure_reason: FailureReason
    previous_attempts: int = 0
    minutes_since_last_attempt: int = 15


class InterventionResult(BaseModel):
    action: ActionType
    reasoning: str
    cost: float
    payload: Optional[dict] = None


class LedgerRecord(BaseModel):
    attempt_id: str
    transaction_id: str
    customer_name: str
    principal_amount: float
    failure_reason: str
    attempt_number: int
    simulated_success_prob: float
    action_taken: ActionType
    cost: float
    status: RecoveryStatus
    recovered_amount: float
    decision_source: str = "DETERMINISTIC_POLICY"
    outcome_source: str = "SYNTHETIC_GATEWAY_SIMULATOR"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
