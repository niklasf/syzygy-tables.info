[syzygy-tables.info](https://syzygy-tables.info)
================================================

User interface and public API for probing Syzygy endgame tablebases.

[![Screenshot of the longest winning 6-piece endgame](/screenshot.png)](https://syzygy-tables.info/?fen=6N1/5KR1/2n5/8/8/8/2n5/1k6%20w%20-%20-%200%201)

Running
-------

Build JavaScript and CSS files using Gulp. Requires node.js and npm:

    npm install -g gulp-cli
    npm install
    gulp

Install dependencies with Python (>= 3.6) and [pipenv](https://pipenv.readthedocs.io/en/latest/):

    pipenv install

Then start the server on port 5000.

    pipenv run server

You can optionally copy `config.default.ini` to `config.ini` and adjust
configuration variables.

API / Backend
-------------

This website is based on a [public API](https://github.com/niklasf/lila-tablebase) hosted by [lichess.org](https://tablebase.lichess.ovh).

Hacking
-------

Have a look at `server.py` for server side code. The client side code is in
`src/client.js`. `gulp watch` can be useful.

License
-------

This project is licensed under the AGPL-3.0+ with the following dependencies:

* [python-chess](https://github.com/niklasf/python-chess) ([GPL-3.0+](https://github.com/niklasf/python-chess/blob/master/LICENSE))
* [chessground](https://github.com/ornicar/chessground) ([GPL-3.0+](https://github.com/ornicar/chessground/blob/master/LICENSE))
* [chess.js](https://github.com/jhlywa/chess.js) ([MIT](https://github.com/jhlywa/chess.js/blob/master/LICENSE))
* [aiohttp](http://aiohttp.readthedocs.org/en/stable/) ([Apache 2](https://github.com/KeepSafe/aiohttp/blob/master/LICENSE.txt))
* [Jinja](http://jinja.pocoo.org/) ([BSD](https://github.com/mitsuhiko/jinja2/blob/master/LICENSE))
* [htmlmin](https://htmlmin.readthedocs.org/en/latest/) ([BSD](https://github.com/mankyd/htmlmin/blob/master/LICENSE))
* [Bootstrap](http://getbootstrap.com/) ([MIT](https://github.com/twbs/bootstrap/blob/master/LICENSE))
* [zepto.js](http://zeptojs.com/) ([MIT](https://github.com/madrobby/zepto/blob/master/MIT-LICENSE))

Thanks to all of them and special thanks to Ronald de Man for [his endgame tablebases](https://github.com/syzygy1/tb)!
