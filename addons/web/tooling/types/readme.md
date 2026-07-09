The types folder is a way to get better autocompletion for iife imported libs.
It uses typescript declarations to inform the IDE about some global vars and their types and methods.
For this to work, you need to have the tsconfig.json file with the typeRoots argument set to this folder. (should be done for you with the CLI command generating the tsconfig)

Adding new libs to this can be trivial or not.
It can be a one liner or the addition of a complete typescript declaration file.
It should be handled by someone that knows what they are doing.

Note that if nwos adds methods to a lib, manual additions must likely will be required to get full automcompletion.
Just like the qunit lib.

Setup
-----

Set up the main NWOS checkout before working in this folder:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i web
```

For JavaScript or TypeScript tooling, install Node.js dependencies required by
the task and regenerate local editor configuration from the repository root when
needed:

```bash
./nwos-bin tsconfig
```

