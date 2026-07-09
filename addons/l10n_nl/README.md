Accounting chart for Netherlands
================================

This module is specially made to manage the accounting functionality
according to the Dutch best practice.

This module contains the Dutch Chart of Accounts and the VAT schema.
This schema is made for the most common Companies and therefore suitable
to be used for almost every Company.

The VAT accounts are linked promptly to generate the required reports. Examples
of this reports intercommunitaire transactions.

After installation of this module the configuration will be activated.
Select the Chart of Accounts named "Netherlands - Accounting".

Hereafter entering the name of the Company, total digits of Chart of Accounts,
Bank Account Number and the default Currency.

Note: total digits configured by default are 6.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i l10n_nl
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i l10n_nl
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u l10n_nl
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

