# [syzygy-tables.info](https://syzygy-tables.info)

User interface and public API for probing Syzygy endgame tablebases.

[![Screenshot of the longest winning 6-piece endgame](/screenshot.png)](https://syzygy-tables.info/?fen=6N1/5KR1/2n5/8/8/8/2n5/1k6%20w%20-%20-%200%201)

## Running

Build JavaScript and CSS files. Requires node.js and npm:

    npm install

Install Python dependencies with poetry:

    poetry install

Then start the server on port 5000.

    poetry run python -m syzygy_tables_info

You can optionally copy `config.default.ini` to `config.ini` and adjust
configuration variables.

## API

This website is based on a [public API](https://github.com/niklasf/lila-tablebase) hosted by [lichess.org](https://tablebase.lichess.ovh).

## Hacking

Have a look at `syzygy_tables_info` for server side code.

The client side code is in `src/main.ts`. Run `npm run prepare` to rebuild.

## License

This project is licensed under the AGPL-3.0+.

<a href="https://syzygy-tables.info/legal#thanks">Thanks to the maintainers of all dependencies</a> and special thanks to Ronald de Man for [his endgame tablebases](https://github.com/syzygy1/tb)!
