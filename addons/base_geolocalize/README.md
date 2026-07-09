Partner geolocalize
===================

Contacts geolocation API to convert partner addresses into GPS coordinates.

Configure
---------
You can configure in General Settings the default provider of the geolocation API service.

A method `_call_<service>` should be implemented in object `base.geocoder` that accepts an address string as parameter and return (latitude, longitude) tuple for this to work.
If no default provider is set, the first one will be used by default.

An optional method `_geo_query_address_<service>` which takes address fields as parameters can be defined to encode the query string for the provider.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i base_geolocalize
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i base_geolocalize
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u base_geolocalize
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

