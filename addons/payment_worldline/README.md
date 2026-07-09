# Worldline

## Technical details

API: [Worldline Direct API](https://docs.direct.worldline-solutions.com/en/api-reference)
version `2`

This module integrates Worldline using the generic payment with redirection flow based on form
submission provided by the `payment` module.

This is achieved by following the [Hosted Checkout Page]
(https://docs.direct.worldline-solutions.com/en/integration/basic-integration-methods/hosted-checkout-page)
guide.

## Supported features

- Payment with redirection flow
- Webhook notifications
- Tokenization with payment

## Not implemented features

- Tokenization without payment
- Manual capture
- Refunds

## Module history

- `18.0`
  - The first version of the module is merged. nwos/nwos#175194.

## Testing instructions

https://docs.direct.worldline-solutions.com/en/integration/how-to-integrate/test-cases/index

Use any name, any date in the future, and any 3 or 4 digits CVC.

### VISA

**Card Number**: `4330264936344675`

### 3D Secure 2 (VISA)

**Card Number**: `4874970686672022`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_worldline
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_worldline
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_worldline
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

