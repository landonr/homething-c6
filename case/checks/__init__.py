"""The case's checks, one module per feature, mirroring model/.

check.py is the entry point and calls main() from checks.cli. Every pass
builds the real thing through case.py's own builders rather than a copy, so a
check that stops exercising the shipped geometry stops passing.
"""
