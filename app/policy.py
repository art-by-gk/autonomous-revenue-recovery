from models import ActionType, FailureReason, InterventionResult, PaymentEvent


def resolve_bounded_intervention(
    payment: PaymentEvent,
) -> InterventionResult:
    """Deterministic policy: the authority for automated financial actions."""

    # 1. Hard stopping rule: customer fatigue / bounded attempts.
    if payment.previous_attempts >= 3:
        return InterventionResult(
            action=ActionType.STOP_TERMINATE,
            reasoning=(
                f"Stopping rule triggered: attempts ({payment.previous_attempts}) "
                ">= 3. Autonomous outreach halted."
            ),
            cost=0.0,
        )

    # 2. High-risk / high-value transactions always require a human.
    if (
        payment.failure_reason == FailureReason.SUSPICIOUS_TRANSACTION
        or payment.amount >= 15000.0
    ):
        return InterventionResult(
            action=ActionType.HUMAN_ESCALATION,
            reasoning=(
                "High-value or fraud-risk threshold reached. "
                "Routed to human review."
            ),
            cost=15.0,
            payload={
                "queue": "senior_risk_review",
                "priority": "HIGH",
            },
        )

    # 3. Timeout → bounded smart retry.
    if payment.failure_reason == FailureReason.TIMEOUT:
        return InterventionResult(
            action=ActionType.SMART_RETRY,
            reasoning=(
                "Timeout failure detected. "
                "Applying bounded smart retry policy."
            ),
            cost=0.50,
        )

    # 4. Insufficient balance → localized one-click recovery link.
    if payment.failure_reason == FailureReason.INSUFFICIENT_FUNDS:
        pay_link = (
            f"https://pay.gateway.internal/quickpay?tx={payment.id}"
        )

        return InterventionResult(
            action=ActionType.HINGLISH_WHATSAPP,
            reasoning=(
                "Insufficient balance diagnosed. "
                "Dispatching localized 1-click recovery link."
            ),
            cost=0.25,
            payload={
                "link": pay_link,
                "message": (
                    f"Namaste {payment.customer_name}! Aapka "
                    f"₹{payment.amount:,.2f} payment retry karein: {pay_link}"
                ),
            },
        )

    # 5. Expired payment instrument → update link.
    if payment.failure_reason == FailureReason.EXPIRED_INSTRUMENT:
        return InterventionResult(
            action=ActionType.TOKEN_UPDATE_LINK,
            reasoning=(
                "Expired payment token. "
                "Dispatching card update form."
            ),
            cost=0.10,
        )

    # 6. Safe fallback for other non-risk declines.
    return InterventionResult(
        action=ActionType.GENERIC_EMAIL,
        reasoning="Standard decline reminder dispatched.",
        cost=0.05,
    )
