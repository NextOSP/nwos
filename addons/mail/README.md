NWOS Enterprise Social Network
------------------------------

Connect with experts, follow what interests you, share documents and promote
best practices with NWOS <a href="https://www.nwos.com/app/discuss">Enterprise Social Network</a>. Get work done with
effective collaboration across departments, geographies, documents and business
applications. All of this while decreasing email overload.

Connect with experts
--------------------

Next time you have a question for the marketing, sales, R&D or any other
department, don't send an email blast-post the question to NWOS and get answers
from the right persons.

Follow what interests you
-------------------------

Want to get informed about new product features, hot deals, bottlenecks in
projects or any other event? Just follow what interests you to get the
information you need what you need; no more, no less.

Get Things Done
---------------

You can process (not only read) the inbox and easily mark messages for future
actions. Start feeling the pleasure of having an empty inbox every day; no more
overload of information.

Promote best practices
----------------------

Cut back on meetings and email chains by working together in groups of
interests. Create a group to let people share files, discuss ideas, and vote to
promote best practices.

Improve Access to Information and Expertise
-------------------------------------------

Break down information silos. Search across your existing systems to find the
answers and expertise you need to complete projects quickly.

Collaborate securely
--------------------

Set the right security policy; public, private or on invitation only --
according to the information sensitivity.

A Twitter-like Network For My Company
---------------------------------------

Make every employee feel more connected and engaged with twitter-like features
for your own company. Follow people, share best practices, 'like' top ideas,
etc.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i mail
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i mail
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u mail
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

