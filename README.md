[syzygy-tables.info](https://syzygy-tables.info)
================================================

User interface and public API for probing Syzygy endgame tablebases.

[![Screenshot of the longest winning 6-piece endgame](/screenshot.png)](https://syzygy-tables.info/?fen=6N1/5KR1/2n5/8/8/8/2n5/1k6%20w%20-%20-%200%201)

Running
-------

Build JavaScript and CSS files using Gulp. Requires node.js and npm:

    npm install

Install dependencies with Python (>= 3.7) and [pipenv](https://pipenv.readthedocs.io/en/latest/):

    PIPENV_VENV_IN_PROJECT=1 pipenv install

Then start the server on port 5000.

    PIPENV_VENV_IN_PROJECT=1 pipenv run server

You can optionally copy `config.default.ini` to `config.ini` and adjust
configuration variables.

API / Backend
-------------

This website is based on a [public API](https://github.com/niklasf/lila-tablebase) hosted by [lichess.org](https://tablebase.lichess.ovh).

Hacking
-------

Have a look at `server.py` for server side code. The client side code is in
`src/client.js`. Run `npm run prepare` to rebuild.

License
-------

This project is licensed under the AGPL-3.0+.

<a href="https://syzygy-tables.info/legal#thanks">Thanks to all dependencies</a> and special thanks to Ronald de Man for [his endgame tablebases](https://github.com/syzygy1/tb)!
