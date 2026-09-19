"""Verify the case against the board. Forty-five passes, each catching what
the others cannot.

The passes live in checks/, one module per feature, mirroring model/. Each
module's own docstring says what its passes catch and why nothing else covers
it. checks/cli.py holds main(), which is the report's order and the argument
handling.

    python check.py                 every pass
    python check.py --only ir       one feature's passes, building only the
                                    solids those passes probe

Every run also writes export/c6remote-checks.json, the same report in machine
form, carrying each failure's own point or box in the case frame wherever the
pass recorded one. That is what the c6remote-explode viewer draws the failures
from.
"""

from checks.cli import main

if __name__ == "__main__":
    main()
