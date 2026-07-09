# Amazon Payment Services

## Technical details

API: [Redirection API](https://paymentservices-reference.payfort.com/docs/api/build/index.html#redirection)

This module integrates Amazon Payment Services using the generic payment with redirection flow based
on form submission provided by the `payment` module.

## Supported features

- Payment with redirection flow
- Webhook notifications

## Not implemented features

- [Tokenization with or without payment](https://paymentservices-reference.payfort.com/docs/api/build/index.html#safe-tokenization)

## Module history

- `16.0`
  - The first version of the module is merged. nwos/nwos#95860

## Testing instructions

https://paymentservices.amazon.com/docs/EN/12.html

### VISA

**Card Number**: `4111111111111111`

**Expiry Date**: any date in the future

**CVC Code**: any

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_aps
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_aps
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_aps
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

