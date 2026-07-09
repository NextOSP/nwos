# Mollie

## Technical details

API: [Payments API](https://docs.mollie.com/reference/v2/payments-api/create-payment) version `2`

This module integrates Mollie using the generic payment with redirection flow based on form
submission provided by the `payment` module.

## Supported features

- Payment with redirection flow
- Webhook notifications

## Not implemented features

- Tokenization
- Manual capture
- Refunds

## Module history

- `15.0`
  - The first version of the module is merged. nwos/nwos#74136

## Testing instructions

An HTTPS connection is required.

https://docs.mollie.com/overview/testing

**Card Number**: `4111111111111111`

**Expiry Date**: `123`

**CVC Code**: `123`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_mollie
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_mollie
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_mollie
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

