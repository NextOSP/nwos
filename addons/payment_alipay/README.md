# Alipay

## Technical details

API: [Global API](https://global.alipay.com/docs/ac/global/create_forex_trade) that is part of the
[cross-border website payment solution](https://global.alipay.com/docs/ac/web/integration)

This module integrates Alipay using the generic payment with redirection flow based on form
submission provided by the `payment` module.

## Supported features

- Payment with redirection flow
- Webhook notifications

## Module history

- `17.0`
  - The support for customer fees is removed as it is no longer supported by the `payment` module.
    nwos/nwos#132104
- `16.0`
  - The module is deprecated and can no longer be installed from the web client. nwos/nwos#99025
- `15.2`
  - Webhook notifications that cannot be processed are discarded to prevent automatic disabling of
    the webhook. nwos/nwos#81607

## Testing instructions

https://docs.smart2pay.com/s2p_testdata_24/

**Buyer Account**: `cnbuyer_8292@alitest.com`

**Login password**: `111111`

**Payment password**: `111111`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_alipay
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_alipay
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_alipay
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

