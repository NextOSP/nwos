# Razorpay

## Technical details

API: [Recurring Payments API](https://razorpay.com/docs/api/payments/recurring-payments/)
version `1`

## Supported features

- Direct payment flow
- Tokenization
- Full manual capture
- Partial refunds
- OAuth authentication

## Not implemented features

- Partial manual capture

## Module history

- `17.0`
  - The previous Hosted Checkout API that allowed for redirect payments is replaced by the Recurring
    Payments API that supports direct payments and tokenization. nwos/nwos#143525
  - OAuth support is added in addition to the credentials-based authentication. nwos/nwos#158578
- `16.0`
  - The first version of the module is merged. nwos/nwos#92848

## Testing instructions

https://razorpay.com/docs/payments/payments/test-card-upi-details/

https://razorpay.com/docs/payments/payments/test-upi-details/

A valid Indian phone number must be set on the partner. Example: `+91123456789`

### VISA

**Card Number**: `4111111111111111`

**Expiry Date**: any future date

**Card Secret**: any

**OTP**: `1111`

### UPI

**UPI ID**: `success@razorpay` or `failure@razorpay`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_razorpay
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_razorpay
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_razorpay
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

