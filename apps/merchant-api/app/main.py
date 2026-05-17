"""Main FastAPI application."""

import json
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import FastAPI, Depends, Query, Request, HTTPException, status
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


# ---------------------------------------------------------------------------
# UI helpers — Tailwind CDN-driven HTML rendering
# ---------------------------------------------------------------------------

_STATUS_VIEW: dict[str, dict[str, str]] = {
    "paid": {
        "label": "Payment Successful",
        "subtitle": "Funds confirmed by the provider.",
        "icon": "check",
        "tone_bg": "bg-emerald-50",
        "tone_ring": "ring-emerald-200",
        "tone_text": "text-emerald-700",
        "tone_dot": "bg-emerald-500",
    },
    "succeeded": {
        "label": "Payment Successful",
        "subtitle": "Funds confirmed by the provider.",
        "icon": "check",
        "tone_bg": "bg-emerald-50",
        "tone_ring": "ring-emerald-200",
        "tone_text": "text-emerald-700",
        "tone_dot": "bg-emerald-500",
    },
    "pending": {
        "label": "Awaiting Confirmation",
        "subtitle": "Waiting for the provider's webhook.",
        "icon": "clock",
        "tone_bg": "bg-amber-50",
        "tone_ring": "ring-amber-200",
        "tone_text": "text-amber-700",
        "tone_dot": "bg-amber-500",
    },
    "failed": {
        "label": "Payment Failed",
        "subtitle": "The provider rejected this payment.",
        "icon": "x",
        "tone_bg": "bg-rose-50",
        "tone_ring": "ring-rose-200",
        "tone_text": "text-rose-700",
        "tone_dot": "bg-rose-500",
    },
    "cancelled": {
        "label": "Payment Cancelled",
        "subtitle": "The customer cancelled before completion.",
        "icon": "x",
        "tone_bg": "bg-rose-50",
        "tone_ring": "ring-rose-200",
        "tone_text": "text-rose-700",
        "tone_dot": "bg-rose-500",
    },
    "refunded": {
        "label": "Payment Refunded",
        "subtitle": "Funds returned to the customer.",
        "icon": "refresh",
        "tone_bg": "bg-sky-50",
        "tone_ring": "ring-sky-200",
        "tone_text": "text-sky-700",
        "tone_dot": "bg-sky-500",
    },
}


_PROVIDER_VIEW: dict[str, dict[str, str]] = {
    "payfast": {"label": "PayFast", "badge": "bg-blue-100 text-blue-800"},
    "paystack": {"label": "Paystack", "badge": "bg-cyan-100 text-cyan-800"},
}


_ICON_SVG: dict[str, str] = {
    "check": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-8 h-8"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>',
    "clock": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-8 h-8"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
    "x": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-8 h-8"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>',
    "refresh": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-8 h-8"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0011.667 0l3.181-3.183m-4.991-2.69v-.001h4.99v4.99" /></svg>',
}


def _format_amount(cents: int) -> str:
    """Format integer cents as 'R100.00'."""
    rands = cents // 100
    remainder = cents % 100
    return f"R{rands:,}.{remainder:02d}"


def _provider_badge(provider: str) -> str:
    """Render a styled provider badge."""
    view = _PROVIDER_VIEW.get(provider, {"label": provider.title(), "badge": "bg-slate-100 text-slate-700"})
    return f'<span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold {view["badge"]}">{view["label"]}</span>'


def _render_home() -> str:
    """Render the checkout home page."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Lekker Pay — Demo Checkout</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>body { font-family: 'Inter', system-ui, -apple-system, sans-serif; }</style>
</head>
<body class="bg-gradient-to-br from-slate-50 via-white to-slate-100 min-h-screen antialiased text-slate-900">
  <div class="max-w-2xl mx-auto px-6 py-16">

    <header class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <span class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-slate-900 text-white font-bold text-lg">L</span>
        <span class="text-sm font-semibold text-slate-500 tracking-wide uppercase">Lekker Pay</span>
      </div>
      <h1 class="text-4xl font-bold tracking-tight text-slate-900">Demo Checkout</h1>
      <p class="mt-2 text-slate-600">A unified payment interface across South African providers.</p>
    </header>

    <div class="bg-white rounded-2xl shadow-sm ring-1 ring-slate-200 overflow-hidden">
      <div class="px-8 py-7 border-b border-slate-100">
        <h2 class="text-lg font-semibold text-slate-900">Create a test payment</h2>
        <p class="mt-1 text-sm text-slate-500">Pick a provider and we will route the payment through Lekker Pay's adapter.</p>
      </div>

      <form id="checkoutForm" class="px-8 py-7 space-y-5">
        <div>
          <label for="amount" class="block text-sm font-medium text-slate-700">Amount (Rands)</label>
          <div class="mt-1.5 relative rounded-lg shadow-sm">
            <div class="pointer-events-none absolute inset-y-0 left-0 pl-3.5 flex items-center"><span class="text-slate-400 sm:text-sm">R</span></div>
            <input type="number" name="amount" id="amount" value="100" min="1" step="0.01" required class="block w-full rounded-lg border-0 py-2.5 pl-7 pr-3 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-slate-900 text-base">
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <label for="email" class="block text-sm font-medium text-slate-700">Email</label>
            <input type="email" id="email" name="email" value="test@example.com" required class="mt-1.5 block w-full rounded-lg border-0 py-2.5 px-3 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-slate-900 text-base">
          </div>
          <div>
            <label for="name" class="block text-sm font-medium text-slate-700">Name</label>
            <input type="text" id="name" name="name" value="Test Customer" required class="mt-1.5 block w-full rounded-lg border-0 py-2.5 px-3 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-slate-900 text-base">
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700 mb-2">Provider</label>
          <div class="grid grid-cols-2 gap-3">
            <label class="relative flex cursor-pointer rounded-lg border border-slate-300 bg-white p-4 shadow-sm focus-within:ring-2 focus-within:ring-slate-900 has-[:checked]:border-slate-900 has-[:checked]:ring-1 has-[:checked]:ring-slate-900">
              <input type="radio" name="provider" value="payfast" checked class="sr-only">
              <span class="flex flex-1 items-center">
                <span class="flex flex-col">
                  <span class="block text-sm font-semibold text-slate-900">PayFast</span>
                  <span class="mt-1 text-xs text-slate-500">SA cards via redirect</span>
                </span>
              </span>
            </label>
            <label class="relative flex cursor-pointer rounded-lg border border-slate-300 bg-white p-4 shadow-sm focus-within:ring-2 focus-within:ring-slate-900 has-[:checked]:border-slate-900 has-[:checked]:ring-1 has-[:checked]:ring-slate-900">
              <input type="radio" name="provider" value="paystack" class="sr-only">
              <span class="flex flex-1 items-center">
                <span class="flex flex-col">
                  <span class="block text-sm font-semibold text-slate-900">Paystack</span>
                  <span class="mt-1 text-xs text-slate-500">Pan-African REST</span>
                </span>
              </span>
            </label>
          </div>
        </div>

        <div class="pt-2">
          <button type="submit" id="submitBtn" class="w-full inline-flex justify-center items-center rounded-lg bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-900 focus:ring-offset-2 transition">
            <span id="btnLabel">Continue to payment</span>
            <svg id="btnSpinner" class="ml-2 hidden animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          </button>
        </div>

        <div id="errorBox" class="hidden rounded-lg bg-rose-50 ring-1 ring-rose-200 px-4 py-3 text-sm text-rose-700"></div>
      </form>
    </div>

    <p class="mt-6 text-center text-xs text-slate-400">All payments are sandbox &middot; No real money moves.</p>
  </div>

  <script>
    const form = document.getElementById('checkoutForm');
    const errorBox = document.getElementById('errorBox');
    const btn = document.getElementById('submitBtn');
    const btnLabel = document.getElementById('btnLabel');
    const btnSpinner = document.getElementById('btnSpinner');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorBox.classList.add('hidden');
      btn.disabled = true;
      btnLabel.textContent = 'Creating payment…';
      btnSpinner.classList.remove('hidden');

      const formData = new FormData(form);
      const amount_cents = Math.round(parseFloat(formData.get('amount')) * 100);

      try {
        const response = await fetch('/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            amount_cents,
            customer_email: formData.get('email'),
            customer_name: formData.get('name'),
            provider: formData.get('provider'),
          }),
        });
        const data = await response.json();
        if (response.ok) {
          window.location.href = data.redirect_url;
        } else {
          throw new Error(data.detail || 'Payment creation failed');
        }
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.classList.remove('hidden');
        btn.disabled = false;
        btnLabel.textContent = 'Continue to payment';
        btnSpinner.classList.add('hidden');
      }
    });
  </script>
</body>
</html>"""


def _render_order_html(order: Order, status_query: str | None) -> str:
    """Render the order status page with Tailwind UI."""
    view = _STATUS_VIEW.get(
        order.status,
        {
            "label": order.status.replace("_", " ").title(),
            "subtitle": "Status not recognised.",
            "icon": "clock",
            "tone_bg": "bg-slate-50",
            "tone_ring": "ring-slate-200",
            "tone_text": "text-slate-700",
            "tone_dot": "bg-slate-400",
        },
    )

    is_pending = order.status in ("pending", "processing")
    auto_refresh = '<meta http-equiv="refresh" content="3">' if is_pending else ""

    amount_display = _format_amount(order.amount_cents)
    icon_svg = _ICON_SVG.get(view["icon"], _ICON_SVG["clock"])
    provider_badge = _provider_badge(order.provider)

    # Timeline events derived from order state
    created_at = order.created_at.strftime("%H:%M:%S")
    updated_at = order.updated_at.strftime("%H:%M:%S")

    timeline_rows = [
        ("Order created", created_at, "done"),
        ("Customer redirected to provider", created_at, "done"),
        (
            "Webhook received",
            updated_at if order.webhook_received else "Waiting…",
            "done" if order.webhook_received else ("active" if is_pending else "pending"),
        ),
        (
            f"Order {order.status}",
            updated_at if order.webhook_received else "—",
            "done" if order.webhook_received else "pending",
        ),
    ]

    def _timeline_dot(state: str) -> str:
        if state == "done":
            return '<span class="flex h-3 w-3 rounded-full bg-emerald-500 ring-4 ring-emerald-100"></span>'
        if state == "active":
            return '<span class="relative flex h-3 w-3"><span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75"></span><span class="relative inline-flex h-3 w-3 rounded-full bg-amber-500"></span></span>'
        return '<span class="flex h-3 w-3 rounded-full bg-slate-200 ring-4 ring-slate-50"></span>'

    timeline_html = "".join(
        f'<li class="flex items-start gap-4 py-3"><div class="mt-1.5">{_timeline_dot(state)}</div>'
        f'<div class="flex-1 flex justify-between items-baseline"><span class="text-sm font-medium text-slate-900">{label}</span>'
        f'<span class="text-xs font-mono text-slate-500">{when}</span></div></li>'
        for label, when, state in timeline_rows
    )

    provider_payment_id = order.provider_payment_id or "—"

    # Build raw API response JSON (server-side dump avoids f-string escaping headaches)
    raw_response_json = json.dumps(
        {
            "reference": order.reference,
            "provider": order.provider,
            "provider_payment_id": order.provider_payment_id,
            "amount_cents": order.amount_cents,
            "customer_email": order.customer_email,
            "customer_name": order.customer_name,
            "status": order.status,
            "webhook_received": order.webhook_received,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
        },
        indent=2,
    )

    status_query_banner = ""
    if status_query and not is_pending:
        # Optional: show a soft note if customer returned via cancel
        if status_query == "cancelled" and order.status != "cancelled":
            status_query_banner = '<div class="mb-6 rounded-lg bg-amber-50 ring-1 ring-amber-200 px-4 py-3 text-sm text-amber-800">You cancelled the payment, but the webhook may still arrive. This page refreshes automatically.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  {auto_refresh}
  <title>Order {order.reference} — Lekker Pay</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', system-ui, sans-serif; }}
    .font-mono, code, pre {{ font-family: 'JetBrains Mono', ui-monospace, monospace; }}
  </style>
</head>
<body class="bg-gradient-to-br from-slate-50 via-white to-slate-100 min-h-screen antialiased text-slate-900">
  <div class="max-w-3xl mx-auto px-6 py-12">

    <a href="/" class="inline-flex items-center text-sm text-slate-500 hover:text-slate-900 mb-8 transition">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 mr-1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5"/></svg>
      Back to checkout
    </a>

    {status_query_banner}

    <!-- Status hero card -->
    <div class="rounded-2xl {view['tone_bg']} ring-1 {view['tone_ring']} px-8 py-8 mb-8 shadow-sm">
      <div class="flex items-start gap-5">
        <div class="flex-shrink-0 w-14 h-14 rounded-2xl bg-white shadow-sm flex items-center justify-center {view['tone_text']}">
          {icon_svg}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="inline-flex h-2 w-2 rounded-full {view['tone_dot']}"></span>
            <span class="text-xs font-semibold {view['tone_text']} uppercase tracking-wider">{order.status}</span>
          </div>
          <h1 class="text-2xl font-bold text-slate-900">{view['label']}</h1>
          <p class="mt-1 text-sm text-slate-600">{view['subtitle']}</p>
          <div class="mt-4 flex items-baseline gap-3">
            <span class="text-3xl font-bold text-slate-900">{amount_display}</span>
            {provider_badge}
          </div>
        </div>
      </div>
    </div>

    <!-- Details grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      <div class="bg-white rounded-xl ring-1 ring-slate-200 p-6">
        <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Customer</h2>
        <dl class="space-y-3">
          <div>
            <dt class="text-xs text-slate-500">Name</dt>
            <dd class="text-sm font-medium text-slate-900">{order.customer_name}</dd>
          </div>
          <div>
            <dt class="text-xs text-slate-500">Email</dt>
            <dd class="text-sm font-medium text-slate-900 break-all">{order.customer_email}</dd>
          </div>
        </dl>
      </div>
      <div class="bg-white rounded-xl ring-1 ring-slate-200 p-6">
        <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Payment</h2>
        <dl class="space-y-3">
          <div>
            <dt class="text-xs text-slate-500">Reference</dt>
            <dd class="text-sm font-mono text-slate-900">{order.reference}</dd>
          </div>
          <div>
            <dt class="text-xs text-slate-500">Provider Payment ID</dt>
            <dd class="text-sm font-mono text-slate-900 break-all">{provider_payment_id}</dd>
          </div>
        </dl>
      </div>
    </div>

    <!-- Timeline -->
    <div class="bg-white rounded-xl ring-1 ring-slate-200 p-6 mb-8">
      <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Timeline</h2>
      <ol class="divide-y divide-slate-100">
        {timeline_html}
      </ol>
    </div>

    <!-- Raw API toggle -->
    <details class="bg-white rounded-xl ring-1 ring-slate-200 group">
      <summary class="cursor-pointer px-6 py-4 flex items-center justify-between text-sm font-medium text-slate-700 hover:text-slate-900">
        <span>Raw API response</span>
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 transition group-open:rotate-180"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/></svg>
      </summary>
      <pre class="px-6 pb-6 pt-2 text-xs font-mono text-slate-700 overflow-x-auto">{raw_response_json}</pre>
    </details>

    <p class="mt-8 text-center text-xs text-slate-400">
      {"Auto-refreshing every 3 seconds while pending…" if is_pending else "Powered by Lekker Pay"}
    </p>
  </div>
</body>
</html>"""


# Endpoints

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Root endpoint — Lekker Pay demo checkout form."""
    return HTMLResponse(_render_home())


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


@app.get("/orders/{reference}")
async def get_order(
    reference: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_query: str | None = Query(None, alias="status"),
):
    """
    Get order status by reference.

    Returns:
        - HTML status page for browser clients (default)
        - JSON when `Accept: application/json` is present, or `?format=json`

    Used as:
    1. Return URL after payment (success/cancel)
    2. Status polling endpoint
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

    # Content negotiation: explicit ?format=json wins, else Accept header, else HTML default
    wants_json = (
        request.query_params.get("format") == "json"
        or "application/json" in request.headers.get("accept", "").lower()
    )

    if wants_json:
        return JSONResponse(
            content={
                "reference": order.reference,
                "provider": order.provider,
                "provider_payment_id": order.provider_payment_id,
                "amount_cents": order.amount_cents,
                "customer_email": order.customer_email,
                "customer_name": order.customer_name,
                "status": order.status,
                "webhook_received": order.webhook_received,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
            }
        )

    # Pull status hint from query (used when customer returns from provider)
    return HTMLResponse(_render_order_html(order, status_query))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "merchant-api"}


# Made with Bob