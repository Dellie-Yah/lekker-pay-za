"""Redis client for idempotency and caching."""

import redis.asyncio as redis
from app.config import settings


class RedisClient:
    """Redis client wrapper for async operations."""

    def __init__(self) -> None:
        """Initialize Redis client."""
        self.client: redis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        self.client = await redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.client:
            await self.client.aclose()

    async def set_webhook_processed(self, provider_payment_id: str, ttl: int = 86400) -> None:
        """
        Mark webhook as processed for idempotency.
        
        Args:
            provider_payment_id: Provider's payment ID
            ttl: Time to live in seconds (default 24 hours)
        """
        if self.client:
            key = f"webhook:processed:{provider_payment_id}"
            await self.client.setex(key, ttl, "1")

    async def is_webhook_processed(self, provider_payment_id: str) -> bool:
        """
        Check if webhook was already processed.
        
        Args:
            provider_payment_id: Provider's payment ID
            
        Returns:
            True if webhook was already processed
        """
        if self.client:
            key = f"webhook:processed:{provider_payment_id}"
            return await self.client.exists(key) > 0
        return False


# Global Redis client instance
redis_client = RedisClient()

# Made with Bob
