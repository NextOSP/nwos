# PayU

## Technical details

API: [PayU Hosted Checkout](https://docs.payu.in/docs/prebuilt-checkout-page-integration)

This module integrates PayU using the generic payment with redirection flow based on form
submission provided by the payment module.

## Supported features

- Payment with redirection flow
- OAuth authentication

## Module history

- `19.0`
  - The first version of the module is merged. nwos/nwos#267962

## Testing instructions

https://docs.payu.in/docs/test-cards-upi-id-and-wallets

### VISA

**Card Number**: `4012001037141112`

**Expiry Date**: any date in the future

**CVC Code**: any

**OTP**: `123456`

### MasterCard

**Card Number**: `5123456789012346`

**Expiry Date**: any date in the future

**CVC Code**: any

**OTP**: `123456`

### UPI

**UPI ID**: `anything@payu`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_payu
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_payu
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_payu
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

