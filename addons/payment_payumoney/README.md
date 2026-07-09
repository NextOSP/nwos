# PayUmoney

## Technical details

API: [PayUMoney Payment Gateway](https://www.payumoney.com/pdf/PayUMoney-Technical-Integration-Document.pdf)

This module integrates PayUmoney using the generic payment with redirection flow based on form
submission provided by the `payment` module.

## Supported features

- Payment with redirection flow

## Module history

- `16.0`
  - The module is deprecated and can no longer be installed from the web client. nwos/nwos#99025

## Testing instructions

**Phone**: `123456`

**Email**: `test@example.com`

**Card Number**: `4012001037141112`

**Expiry**: any date in the future

**CVV**: `123`

**TOTP**: `123456`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_payumoney
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_payumoney
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_payumoney
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

