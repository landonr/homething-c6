# noble

Vendored files for the web page loader. The loader verifies the signature of
the interface bundle, and a browser gives it no `crypto.subtle`, because the
device serves the page over plain HTTP. So the loader carries its own SHA-512.

`scripts/build-ui-loader.py` bundles these files into `site/app/loader-*.js`.
A browser never loads a file from this directory.

| file | package | version |
| --- | --- | --- |
| `ed25519.js` | `@noble/ed25519` | 3.2.0 |
| `sha2.js`, `_md.js`, `_u64.js`, `utils.js` | `@noble/hashes` | 2.4.0 |

Both packages are MIT, by Paul Miller. To update one, replace its files from
`https://cdn.jsdelivr.net/npm/<package>@<version>/<file>`, change the version
in this table, then run `python3 scripts/build-ui-loader.py`.
