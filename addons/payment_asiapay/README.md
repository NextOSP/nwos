# AsiaPay

## Technical details

API: Client Post Through Browser version `3.67`

This module integrates AsiaPay using the generic payment with redirection flow based on form
submission provided by the `payment` module.

The entire API reference and the integration guide can be found on the
[Integration Guide](https://www.paydollar.com/pdf/op/enpdintguide.pdf).

## Supported features

- Payment with redirection flow
- Webhook notifications

## Not implemented features

- Manual capture
- Refunds
- Express checkout
- Multi-currency processing

## Module history

- `16.2`
  - The field "AsiaPay Brand" is added to select the API to use. nwos/nwos#110357
- `16.1`
  - The "AsiaPay Currency" field is replaced by the generic "Currencies" field of `payment`.
    nwos/nwos#101018
- `16.0`
  - The first version of the module is merged. nwos/nwos#98441

## Testing instructions

### VISA

**Card Number**: `4335900000140045`

**Expiry Date**: `07/2030`

**CVC Code**: `123`

**Name**: `testing card`

**3DS Password**: `password`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_asiapay
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_asiapay
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_asiapay
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

