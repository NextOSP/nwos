# SIPS

## Technical details

API: [SIPS Paypage](https://docs.sips.worldline-solutions.com/en/WLSIPS.317-UG-Sips-Paypage-POST.html#Data-field-element-syntax_)

<!-- https://documentation.sips.worldline.com/en/WLSIPS.316-UG-Sips-Paypage-JSON.html = 404 -->

This module integrates SIPS using the generic payment with redirection flow based on form
submission provided by the `payment` module.

## Supported features

- Payment with redirection flow
- Webhook notifications

## Module history

- `15.2`
  - An HTTP 404 "Forbidden" error is raised instead of a Validation error when the authenticity of
    the webhook notification cannot be verified. nwos/nwos#81607

## Testing instructions

### VISA

**Card Number**: `4100000000000000`

### MasterCard

**Card Number**: `5100000000000000`

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_sips
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i payment_sips
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u payment_sips
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

