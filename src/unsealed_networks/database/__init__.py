"""Database module for document storage and search."""

from .loader import load_documents
from .schema import init_database

__all__ = ["init_database", "load_documents"]
