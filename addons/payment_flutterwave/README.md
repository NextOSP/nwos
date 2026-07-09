# Flutterwave

## Technical details

API: [Flutterwave standard](https://developer.flutterwave.com/v3.0.0/docs/flutterwave-standard-1)
version `3`

This module integrates Flutterwave using the generic payment with redirection flow based on form
submission provided by the `payment` module.

## Supported features

- Payment with redirection flow
- Webhook notifications
- Tokenization with payment

## Not implemented features

- Manual capture
- Refunds

## Module history

- `15.4`
  - The first version of the module is merged. nwos/nwos#85514

## Testing instructions

https://developer.flutterwave.com/v3.0.0/docs/testing

### MasterCard

**Card Number**: `5531886652142950`

**Expiry Date**: `09/32`

**CVC Code**: `564`

**OPT**: `12345`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_flutterwave
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_flutterwave
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_flutterwave
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

