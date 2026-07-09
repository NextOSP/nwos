# Buckaroo

## Technical details

API: [Buckaroo Payment Engine](https://www.pronamic.nl/wp-content/uploads/2013/04/BPE-3.0-Gateway-HTML.1.02.pdf)
version `3.0`

This module integrates Buckaroo using the generic payment with redirection flow based on form
submission provided by the `payment` module.

## Supported features

- Payment with redirection flow

## Not implemented features

- Webhook notifications

## Module history

- `15.2`
  - The support for webhook notifications is added. nwos/nwos#82922

## Testing instructions

Buckaroo's hosted payment page allows to simulate payments and select the outcome without any
payment details when selecting the payment method PayPal.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_buckaroo
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_buckaroo
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_buckaroo
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

