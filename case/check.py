"""Verify the case against the board. Twenty-seven passes, each catching what
the others cannot.

The passes live in checks/, one module per feature, mirroring model/. Each
module's own docstring says what its passes catch and why nothing else covers
it. checks/cli.py holds main(), which is the report's order and the argument
handling.

    python check.py                 every pass
    python check.py --only ir       one feature's passes, building only the
                                    solids those passes probe
"""

from checks.cli import main

if __name__ == "__main__":
    main()
