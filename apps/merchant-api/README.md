# Merchant API

FastAPI application demonstrating end-to-end payment processing with Lekker Pay.

## Features

- ✅ **POST /checkout** - Create payment and get redirect URL
- ✅ **POST /webhooks/{provider}** - Receive and verify payment webhooks
- ✅ **GET /orders/{reference}** - Query order status
- ✅ PostgreSQL for order persistence
- ✅ Redis for webhook idempotency
- ✅ PayFast sandbox integration

## Quick Start

### Using Docker Compose (Recommended)

```bash
# From project root
docker-compose up -d

# View logs
docker-compose logs -f merchant-api

# API will be available at http://localhost:8000
```

### Local Development

```bash
cd apps/merchant-api

# Install dependencies
pip install -r requirements.txt
pip install -e ../../packages/lekker-pay

# Set environment variables (or create .env file)
export DATABASE_URL="postgresql+asyncpg://lekker_pay:lekker_pay_dev@localhost:5432/lekker_pay"
export REDIS_URL="redis://localhost:6379/0"
export PAYFAST_MERCHANT_ID="10000100"
export PAYFAST_MERCHANT_KEY="46f0cd694581a"
export PAYFAST_PASSPHRASE="jt7NOE43FZPn"
export PAYFAST_SANDBOX="true"

# Run application
uvicorn app.main:app --reload
```

## Testing End-to-End

### 1. Start Services

```bash
docker-compose up -d
```

### 2. Set Up Cloudflared Tunnel

```bash
# Install cloudflared
# Windows: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
# Mac: brew install cloudflared
# Linux: See Cloudflare docs

# Start tunnel
cloudflared tunnel --url http://localhost:8000
```

This will output a public URL like: `https://random-words-1234.trycloudflare.com`

### 3. Update Webhook Base URL

Update the `WEBHOOK_BASE_URL` environment variable in `compose.yml` or set it:

```bash
export WEBHOOK_BASE_URL="https://your-cloudflared-url.trycloudflare.com"
```

Restart the service:

```bash
docker-compose restart merchant-api
```

### 4. Test Payment Flow

1. Open browser to `http://localhost:8000`
2. Fill in the checkout form
3. Click "Create Payment"
4. You'll be redirected to PayFast sandbox
5. Complete payment using test card
6. Webhook will be received at your cloudflared URL
7. Order status will be updated in database

### 5. Verify Webhook

Check logs to see webhook processing:

```bash
docker-compose logs -f merchant-api | grep webhook
```

## API Endpoints

### GET /

Simple HTML checkout form for testing.

### POST /checkout

Create a new payment checkout.

**Request:**
```json
{
  "amount_cents": 10000,
  "customer_email": "test@example.com",
  "customer_name": "Test Customer",
  "provider": "payfast"
}
```

**Response:**
```json
{
  "reference": "ORDER-ABC123",
  "redirect_url": "https://sandbox.payfast.co.za/eng/process?...",
  "amount_cents": 10000,
  "provider": "payfast"
}
```

### POST /webhooks/{provider}

Receive payment webhooks from providers.

**Headers:**
- Provider-specific signature headers

**Body:**
- Raw webhook payload (provider-specific format)

**Response:**
```json
{
  "status": "ok",
  "message": "Webhook processed"
}
```

### GET /orders/{reference}

Get order status.

**Response:**
```json
{
  "reference": "ORDER-ABC123",
  "provider": "payfast",
  "provider_payment_id": "1234567",
  "amount_cents": 10000,
  "customer_email": "test@example.com",
  "customer_name": "Test Customer",
  "status": "paid",
  "webhook_received": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:31:00Z"
}
```

## Database Schema

### orders table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| reference | VARCHAR(100) | Unique order reference |
| provider | VARCHAR(50) | Payment provider name |
| provider_payment_id | VARCHAR(255) | Provider's payment ID |
| amount_cents | INTEGER | Amount in cents |
| customer_email | VARCHAR(255) | Customer email |
| customer_name | VARCHAR(255) | Customer name |
| status | VARCHAR(50) | Order status (pending/paid/failed/cancelled/refunded) |
| redirect_url | VARCHAR(500) | Payment redirect URL |
| webhook_received | BOOLEAN | Whether webhook was received |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | postgresql+asyncpg://... | PostgreSQL connection URL |
| REDIS_URL | redis://localhost:6379/0 | Redis connection URL |
| PAYFAST_MERCHANT_ID | 10000100 | PayFast merchant ID |
| PAYFAST_MERCHANT_KEY | 46f0cd694581a | PayFast merchant key |
| PAYFAST_PASSPHRASE | jt7NOE43FZPn | PayFast passphrase |
| PAYFAST_SANDBOX | true | Use PayFast sandbox |
| WEBHOOK_BASE_URL | http://localhost:8000 | Base URL for webhooks |

## Architecture

```
Browser → FastAPI → Lekker Pay → PayFast API
                ↓
            PostgreSQL (orders)
                ↓
              Redis (idempotency)
                ↑
PayFast Webhook → FastAPI → Update Order
```

## Security Features

- ✅ Webhook signature verification (constant-time comparison)
- ✅ Idempotency via Redis (24hr TTL)
- ✅ SQL injection protection (SQLAlchemy ORM)
- ✅ Input validation (Pydantic models)
- ✅ HTTPS required for production webhooks

## Troubleshooting

### Webhook not received

1. Check cloudflared tunnel is running
2. Verify WEBHOOK_BASE_URL is set correctly
3. Check PayFast sandbox webhook logs
4. Inspect merchant-api logs: `docker-compose logs -f merchant-api`

### Database connection error

1. Ensure PostgreSQL is running: `docker-compose ps postgres`
2. Check DATABASE_URL is correct
3. Verify database exists: `docker-compose exec postgres psql -U lekker_pay -d lekker_pay`

### Redis connection error

1. Ensure Redis is running: `docker-compose ps redis`
2. Check REDIS_URL is correct
3. Test connection: `docker-compose exec redis redis-cli ping`

## Made with Bob 🤖