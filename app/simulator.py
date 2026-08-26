import random
from models import ActionType


# Synthetic-only benchmark assumptions.

ACTION_SUCCESS_PROB = {
    ActionType.SMART_RETRY: 0.70,
    ActionType.HINGLISH_WHATSAPP: 0.62,
    ActionType.TOKEN_UPDATE_LINK: 0.78,
    ActionType.GENERIC_EMAIL: 0.45,
}


def simulate_gateway_callback(action: ActionType) -> tuple[bool, float]:
    """Return (success, benchmark_probability) for the synthetic gateway."""
    if action in (ActionType.STOP_TERMINATE, ActionType.HUMAN_ESCALATION):
        return False, 0.0

    probability = ACTION_SUCCESS_PROB[action]
    success = random.random() < probability
    return success, probability
