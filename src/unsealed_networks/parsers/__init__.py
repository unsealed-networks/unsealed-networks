"""Document parsers for extracting structured metadata."""

from .classifier import DocumentClassifier
from .email_parser import EmailParser
from .legal_parser import LegalDocumentParser
from .news_parser import NewsArticleParser

__all__ = [
    "DocumentClassifier",
    "EmailParser",
    "LegalDocumentParser",
    "NewsArticleParser",
]
