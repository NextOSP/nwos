Your Contact Form
-----------------

### Integrate contact forms with your leads

This simple application integrates a contact form in your "Contact us" page.
Forms submissions create leads automatically in <a href="https://www.nwos.com/app/crm">NWOS CRM</a>.

Easy Contact Page
-----------------

Get your leads filled up automatically with your contact form integration. This
application allows a better qualification of the lead which is perfect to link
them to marketing campaigns.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i website_crm
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i website_crm
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u website_crm
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

