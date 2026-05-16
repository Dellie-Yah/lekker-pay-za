"""Main FastAPI application."""

import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, init_db, Order, OrderStatus
from app.redis_client import redis_client
from app.payment_service import payment_service
from lekker_pay.errors import LekkerPayError, SignatureMismatchError

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting merchant-api")
    await init_db()
    await redis_client.connect()
    logger.info("Database and Redis initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down merchant-api")
    await redis_client.disconnect()


app = FastAPI(
    title="Lekker Pay Merchant API",
    description="Demo merchant API for Lekker Pay payment processing",
    version="0.1.0",
    lifespan=lifespan,
)


# Request/Response Models

class CheckoutRequest(BaseModel):
    """Request model for creating a checkout."""
    
    amount_cents: int = Field(..., gt=0, description="Amount in cents (e.g., 10000 = R100.00)")
    customer_email: EmailStr = Field(..., description="Customer email address")
    customer_name: str = Field(..., min_length=1, description="Customer full name")
    provider: str = Field(default="payfast", description="Payment provider to use")


class CheckoutResponse(BaseModel):
    """Response model for checkout creation."""
    
    reference: str = Field(..., description="Order reference")
    redirect_url: str = Field(..., description="URL to redirect customer for payment")
    amount_cents: int = Field(..., description="Amount in cents")
    provider: str = Field(..., description="Payment provider")


class OrderResponse(BaseModel):
    """Response model for order status."""
    
    reference: str
    provider: str
    provider_payment_id: str | None
    amount_cents: int
    customer_email: str
    customer_name: str
    status: str
    webhook_received: bool
    created_at: str
    updated_at: str


# Endpoints

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with simple checkout form."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lekker Pay Demo</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            form { background: #f5f5f5; padding: 20px; border-radius: 8px; }
            label { display: block; margin-top: 10px; font-weight: bold; }
            input, select { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin-top: 20px; }
            button:hover { background: #0056b3; }
            .info { background: #e7f3ff; padding: 15px; border-radius: 4px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>🚀 Lekker Pay Demo</h1>
        <div class="info">
            <strong>Test Payment</strong><br>
            This will create a payment with your selected provider's sandbox.
        </div>
        
        <form action="/checkout" method="POST" id="checkoutForm">
            <label for="amount">Amount (Rands):</label>
            <input type="number" id="amount" name="amount" value="100" min="1" step="0.01" required>
            <small style="color: #666;">Enter amount in Rands (e.g., 100 for R100.00)</small>
            
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" value="test@example.com" required>
            
            <label for="name">Name:</label>
            <input type="text" id="name" name="name" value="Test Customer" required>
            
            <label for="provider">Provider:</label>
            <select id="provider" name="provider">
                <option value="payfast">PayFast</option>
                <option value="paystack">Paystack</option>
            </select>
            
            <button type="submit">Create Payment</button>
        </form>
        
        <script>
            document.getElementById('checkoutForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const amount_cents = parseInt(formData.get('amount')) * 100;
                
                const response = await fetch('/checkout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        amount_cents: amount_cents,
                        customer_email: formData.get('email'),
                        customer_name: formData.get('name'),
                        provider: formData.get('provider')
                    })
                });
                
                const data = await response.json();
                if (response.ok) {
                    window.location.href = data.redirect_url;
                } else {
                    alert('Error: ' + data.detail);
                }
            });
        </script>
    </body>
    </html>
    """


@app.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def create_checkout(
    request: CheckoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a new payment checkout.
    
    This endpoint:
    1. Creates an order in the database
    2. Initiates payment with the provider
    3. Returns redirect URL for customer
    """
    # Generate unique reference
    reference = f"ORDER-{uuid.uuid4().hex[:12].upper()}"
    
    # Build URLs
    base_url = settings.webhook_base_url
    return_url = f"{base_url}/orders/{reference}?status=success"
    cancel_url = f"{base_url}/orders/{reference}?status=cancelled"
    webhook_url = f"{base_url}/webhooks/{request.provider}"
    
    try:
        # Debug logging for amount
        logger.info(
            "checkout_request_received",
            amount_cents=request.amount_cents,
            reference=reference,
            provider=request.provider,
        )
        
        # Create payment with provider
        result = await payment_service.create_payment(
            provider=request.provider,
            amount_cents=request.amount_cents,
            reference=reference,
            customer_email=request.customer_email,
            customer_name=request.customer_name,
            return_url=return_url,
            cancel_url=cancel_url,
            webhook_url=webhook_url,
        )
        
        # Create order in database
        order = Order(
            reference=reference,
            provider=request.provider,
            provider_payment_id=result["provider_payment_id"],
            amount_cents=request.amount_cents,
            customer_email=request.customer_email,
            customer_name=request.customer_name,
            status=OrderStatus.PENDING.value,
            redirect_url=result["redirect_url"],
        )
        db.add(order)
        await db.commit()
        
        logger.info(
            "checkout_created",
            reference=reference,
            provider=request.provider,
            amount_cents=request.amount_cents,
        )
        
        return CheckoutResponse(
            reference=reference,
            redirect_url=result["redirect_url"],
            amount_cents=request.amount_cents,
            provider=request.provider,
        )
        
    except LekkerPayError as e:
        logger.error("payment_creation_failed", error=str(e), provider=request.provider)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment creation failed: {str(e)}",
        )


@app.post("/webhooks/{provider}", status_code=status.HTTP_200_OK)
async def receive_webhook(
    provider: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Receive and process payment webhooks.
    
    This endpoint:
    1. Verifies webhook signature
    2. Checks for duplicate processing (idempotency)
    3. Updates order status in database
    """
    # Get raw body for signature verification
    body = await request.body()
    headers = dict(request.headers)
    
    try:
        # Verify webhook signature
        event = payment_service.verify_webhook(provider, headers, body)
        
        logger.info(
            "webhook_received",
            provider=provider,
            event_type=event["event_type"],
            reference=event["reference"],
            provider_payment_id=event["provider_payment_id"],
        )
        
        # Check idempotency
        if await redis_client.is_webhook_processed(event["provider_payment_id"]):
            logger.info(
                "webhook_already_processed",
                provider_payment_id=event["provider_payment_id"],
            )
            return {"status": "ok", "message": "Already processed"}
        
        # Find order by reference
        result = await db.execute(
            select(Order).where(Order.reference == event["reference"])
        )
        order = result.scalar_one_or_none()
        
        if not order:
            logger.warning("order_not_found", reference=event["reference"])
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )
        
        # Update order status based on event type
        if event["event_type"] == "payment.succeeded":
            order.status = OrderStatus.PAID.value
        elif event["event_type"] == "payment.failed":
            order.status = OrderStatus.FAILED.value
        elif event["event_type"] == "payment.refunded":
            order.status = OrderStatus.REFUNDED.value
        
        order.webhook_received = True
        order.provider_payment_id = event["provider_payment_id"]
        
        await db.commit()
        
        # Mark as processed
        await redis_client.set_webhook_processed(event["provider_payment_id"])
        
        logger.info(
            "webhook_processed",
            reference=event["reference"],
            status=order.status,
        )
        
        return {"status": "ok", "message": "Webhook processed"}
        
    except SignatureMismatchError as e:
        logger.error("webhook_signature_invalid", provider=provider, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
    except LekkerPayError as e:
        logger.error("webhook_processing_failed", provider=provider, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook processing failed: {str(e)}",
        )


@app.get("/orders/{reference}", response_model=OrderResponse)
async def get_order(
    reference: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get order status by reference.
    
    This endpoint is used for:
    1. Return URL after payment (success/cancel)
    2. Checking order status
    """
    result = await db.execute(
        select(Order).where(Order.reference == reference)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    
    return OrderResponse(
        reference=order.reference,
        provider=order.provider,
        provider_payment_id=order.provider_payment_id,
        amount_cents=order.amount_cents,
        customer_email=order.customer_email,
        customer_name=order.customer_name,
        status=order.status,
        webhook_received=order.webhook_received,
        created_at=order.created_at.isoformat(),
        updated_at=order.updated_at.isoformat(),
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "merchant-api"}


# Made with Bob