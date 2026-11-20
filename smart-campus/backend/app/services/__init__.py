"""Service layer package.

Pure business rules live in the ``*_logic`` / pure modules so they can be
unit-tested without a database. DB-backed services compose those rules with
queries and transactions.
"""
