NWOS Supply Chain
-----------------

Automate requisition-to-pay, control invoicing with the NWOS
<a href="https://www.nwos.com/app/purchase">Open Source Supply Chain</a>.

Automate procurement propositions, launch request for quotations, track
purchase orders, manage vendors' information, control products reception and
check vendors' invoices.

Automated Procurement Propositions
----------------------------------

Reduce inventory level with procurement rules. Get the right purchase
proposition at the right time to reduce your inventory level. Improve your
purchase and inventory performance with procurement rules depending on stock
levels, logistic rules, sales orders, forecasted manufacturing orders, etc.

Send requests for quotations or purchase orders to your vendor in one click.
Get access to product receptions and invoices from your purchase order.

Purchase Tenders
----------------

Launch purchase tenders, integrate vendor's answers in the process and
compare propositions. Choose the best offer and send purchase orders easily.
Use reporting to analyse the quality of your vendors afterwards.


Email integrations
------------------

Integrate all vendor's communications on the purchase orders (or RfQs) to get
a strong traceability on the negotiation or after sales service issues. Use the
claim management module to track issues related to vendors.

Standard Price, Average Price, FIFO
-----------------------------------

Use the costing method that reflects your business: standard price, average
price, fifo or lifo. Get your accounting entries and the right inventory
valuation in real-time; NWOS manages everything for you, transparently.

Import Vendor Pricelists
--------------------------

Take smart purchase decisions using the best prices.  Easily import vendor's
pricelists to make smarter purchase decisions based on promotions, prices
depending on quantities and special contract conditions. You can even base your
sale price depending on your vendor's prices.

Control Products and Invoices
-----------------------------

No product or order is left behind, the inventory control allows you to manage
back orders, refunds, product reception and quality control. Choose the right
control method according to your need.

Control vendor bills with no effort. Choose the right method according to
your need: pre-generate draft invoices based on purchase orders, on products
receptions, create invoices manually and import lines from purchase orders,
etc.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i purchase
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i purchase
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u purchase
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

