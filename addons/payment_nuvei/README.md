# Nuvei

## Technical details

API: [Payment Page API](https://docs.nuvei.com/documentation/accept-payment/payment-page/quick-start-for-payment-page/)

This module integrates Nuvei using the generic payment with redirection flow based on form
submission provided by the `payment` module.

## Supported features

- Payment with redirection flow
- Webhook notifications

## Not implemented features

- [Tokenization with payment](https://docs.nuvei.com/documentation/features/card-operations/pci-and-tokenization/)
- [Tokenization without payment](https://docs.nuvei.com/documentation/features/card-operations/zero-authorization/)
- [Full and partial manual capture](https://docs.nuvei.com/documentation/features/financial-operations/auth-and-settle/)
- [Full and partial refunds](https://docs.nuvei.com/documentation/features/financial-operations/refund/)


## Module history

- `18.0`
  - The first version of the module is merged. nwos/nwos#181459

## Testing instructions

### Card Transactions

For transactions *above* 99 you must use the 3D-Secure cards listed here:
https://docs.nuvei.com/documentation/integration/testing/testing-cards/#3d-secure-v2-test-scenarios
(You must match the card number and cardholder name to what is listed in frictionless/etc depending
on what you are testing and then follow the expiration date/security code information from below)

### VISA (up to $99)

**Card Number:** `4761344136141390`

**Expiry Date:** Any date in the future

**Security Code:** `123`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_nuvei
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_nuvei
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_nuvei
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

