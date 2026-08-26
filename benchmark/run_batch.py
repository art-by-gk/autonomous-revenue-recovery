import random

from ledger import init_db, reset_recovery_ledger, print_financial_audit_summary
from main import execute_closed_loop_recovery
from models import FailureReason, PaymentEvent


PAYMENT_METHODS = ["upi", "credit_card", "debit_card", "mandate_auto_debit"]
FAILURE_REASONS = list(FailureReason)
NAMES = [
    "Aakash Verma", "Priya Sharma", "Rohit Sen", "Sneha Patel", "Vikram Rao",
    "Meera Iyer", "Arjun Kumar", "Kavya Nair", "Rahul Das", "Ananya Shah",
]


def build_edge_cases() -> list[PaymentEvent]:
    """Small deterministic set proving every important policy boundary."""
    return [
        PaymentEvent(id="TX_EDGE_001", customer_name="Timeout Case", amount=4500, payment_method="credit_card", failure_reason=FailureReason.TIMEOUT, previous_attempts=0, minutes_since_last_attempt=5),
        PaymentEvent(id="TX_EDGE_002", customer_name="Funds Case", amount=1299, payment_method="upi", failure_reason=FailureReason.INSUFFICIENT_FUNDS, previous_attempts=0, minutes_since_last_attempt=15),
        PaymentEvent(id="TX_EDGE_003", customer_name="Expired Case", amount=3200, payment_method="credit_card", failure_reason=FailureReason.EXPIRED_INSTRUMENT, previous_attempts=0, minutes_since_last_attempt=30),
        PaymentEvent(id="TX_EDGE_004", customer_name="High Value Boundary", amount=15000, payment_method="mandate_auto_debit", failure_reason=FailureReason.LIMIT_EXCEEDED, previous_attempts=0, minutes_since_last_attempt=60),
        PaymentEvent(id="TX_EDGE_005", customer_name="Suspicious Case", amount=18000, payment_method="credit_card", failure_reason=FailureReason.SUSPICIOUS_TRANSACTION, previous_attempts=0, minutes_since_last_attempt=10),
        PaymentEvent(id="TX_EDGE_006", customer_name="Max Attempt Case", amount=2000, payment_method="upi", failure_reason=FailureReason.TIMEOUT, previous_attempts=3, minutes_since_last_attempt=60),
        PaymentEvent(id="TX_EDGE_007", customer_name="Below Threshold", amount=14999, payment_method="debit_card", failure_reason=FailureReason.LIMIT_EXCEEDED, previous_attempts=0, minutes_since_last_attempt=60),
    ]


def generate_synthetic_transactions(n: int = 193, seed: int = 42) -> list[PaymentEvent]:
    """Generate reproducible synthetic payment failures for benchmarking."""
    rng = random.Random(seed)
    payments = []

    for i in range(n):
        reason = rng.choice(FAILURE_REASONS)

        # Bias the benchmark toward realistic low/mid-value payments while
        # deliberately creating enough high-value and max-attempt edge cases.
        amount = round(rng.uniform(300, 12000), 2)
        if i % 17 == 0:
            amount = round(rng.uniform(15000, 30000), 2)

        attempts = rng.choices([0, 1, 2, 3], weights=[48, 28, 18, 6])[0]
        method = rng.choice(PAYMENT_METHODS)
        minutes = rng.randint(5, 1440)

        payments.append(
            PaymentEvent(
                id=f"TX_SYN_{i + 1:04d}",
                customer_name=NAMES[i % len(NAMES)],
                amount=amount,
                payment_method=method,
                failure_reason=reason,
                previous_attempts=attempts,
                minutes_since_last_attempt=minutes,
            )
        )

    return payments


def run_batch_evaluation():
    init_db()
    reset_recovery_ledger()
    random.seed(42)  # reproducible synthetic gateway outcomes

    batch = build_edge_cases() + generate_synthetic_transactions(193, seed=42)

    print("=" * 72)
    print("        EXECUTING 200-TRANSACTION SYNTHETIC BENCHMARK")
    print("=" * 72)
    print("Dataset: 7 deterministic edge cases + 193 generated cases")
    print("Outcome model: synthetic gateway probabilities, not ML")

    for payment in batch:
        execute_closed_loop_recovery(payment)

    print_financial_audit_summary()


if __name__ == "__main__":
    run_batch_evaluation()
