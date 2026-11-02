# Shopfront API

## POST /api/register

Body: `{ "email": string, "password": string }`

- `password` must be at least 8 characters.
- Returns `201 { id }` or `400 { errors: string[] }`.

## POST /api/password/reset

Body: `{ "token": string, "password": string }`. Same password rule as registration.

## GET /api/orders

Returns orders with a `date` field formatted as `YYYY-MM-DD`.

## GET /api/reports/daily

Sales totals per day, keyed by `YYYY-MM-DD`.
