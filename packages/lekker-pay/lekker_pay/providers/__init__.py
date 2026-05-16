"""
Payment provider adapters.

Each provider module implements BasePaymentAdapter for a specific
payment gateway.
"""

from lekker_pay.providers.payfast import PayFastAdapter
from lekker_pay.providers.paystack import PaystackAdapter

__all__ = [
    "PayFastAdapter",
    "PaystackAdapter",
]

# Made with Bob
