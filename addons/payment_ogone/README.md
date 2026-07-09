# Ogone

## Technical details

APIs:

- [Hosted Payment Page](https://support.legacy.worldline-solutions.com/integration-solutions/integrations/hosted-payment-page?com.dotmarketing.htmlpage.language=1&skiprules=true&com.dotmarketing.htmlpage.language=1&skiprules=true)
- [Direct Link](https://support.legacy.worldline-solutions.com/integration-solutions/integrations/directlink?com.dotmarketing.htmlpage.language=1&skiprules=true&com.dotmarketing.htmlpage.language=1&skiprules=true)

This module relies on a combination of two APIs to implement a payment with redirection flow that
allows for tokenization. The Hosted Payment Page API is integrated using the generic payment with
redirection flow based on form submission provided by the `payment` module. The Direct Link API
is used for token payments.

## Supported features

- Payment with redirection flow
- Webhook notifications
- Tokenization with payment

## Not implemented features

- Tokenization without payment

## Module history

- `16.0`
  - The module is deprecated and can no longer be installed from the web client. nwos/nwos#99025
- `15.2`
  - Webhook notifications that cannot be processed are discarded to prevent automatic disabling of
    the webhook. nwos/nwos#81607
- `14.3`
  - The FlexCheckout API is removed and with it the support for payment method validations.
    nwos/nwos#72624
  - The FlexCheckout API is introduced to handle payment method validations that were performed in
    a non-secure way through the Hosted Payment Page API. nwos/nwos#56187
  - The module is renamed from `payment_ingenico` to `payment_ogone`. nwos/nwos#56187

## Testing instructions

Test card numbers are specific to the Ogone account. From Ogone's Backoffice, find them in
Configuration > Technical information > Test info.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_ogone
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_ogone
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_ogone
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

