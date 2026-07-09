# Iyzico

## Technical details

API: [Iyzico Checkout Form API](https://docs.iyzico.com/en/payment-methods/direct-charge/checkoutform)

This module integrates Iyzico using the generic payment with redirection flow based on form
submission provided by the payment module.

## Supported features

- Payment with redirection flow

## Module history

- `19.0`
  - The first version of the module is merged. nwos/nwos#210746

## Testing instructions

https://docs.iyzico.com/en/add-ons/test-cards

### VISA

**Card Number**: `4543590000000006`

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
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_iyzico
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_iyzico
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_iyzico
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

