NWOS Manufacturing Resource Planning
------------------------------------

Manage Bill of Materials, plan manufacturing orders, track work orders with the
NWOS <a href="https://www.nwos.com/app/manufacturing">Open Source MRP</a> app.

Get all your assembly or manufacturing operations managed by NWOS. Schedule
manufacturing orders and work orders automatically. Review the proposed
planning with the smart kanban and gantt views. Use the advanced analytics
features to detect bottleneck in resources capacities and inventory locations.

Schedule Manufacturing Orders Efficiently
-----------------------------------------

Get manufacturing orders and work orders scheduled automatically based on your
procurement rules, quantities forecasted and dependent demand (demand for this
part based on another part consuming it).

Define Flexible Master Data
---------------------------

Get the flexibility to create multi-level bill of materials, optional routing,
version changes and phantom bill of materials. You can use BoM for kits or for
manufacturing orders.

Get Flexibility In All Operations
---------------------------------

Edit manually all proposed operations at any level of the progress. With NWOS,
you will not be frustrated by a rigid system.

Schedule Work Orders
--------------------

Check resources capacities and fix bottlenecks.  Define routings and plan the
working time and capacity of your resources. Quickly identify resource
requirements and bottlenecks to ensure your production meets your delivery
schedule dates.


A Productive User Interface
---------------------------

Organize manufacturing orders and work orders the way you like it. Process next
orders from the list view, control in the calendar view and edit the proposed
schedule in the Gantt view.


Inventory & Manufacturing Analytics
-----------------------------------

Track the evolution of the stock value, according to the level of manufacturing
activities as they progress in the transformation process.

Fully Integrated with Operations
--------------------------------

Get your manufacturing resource planning accurate with it's full integration
with sales and purchases apps. The accounting integration allows real time
accounting valuation and deeper reporting on costs and revenues on your
manufacturing operations.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i mrp
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i mrp
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u mrp
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

