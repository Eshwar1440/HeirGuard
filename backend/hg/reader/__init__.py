"""M2: the AI document reader (structured extraction through hg.llm)."""

from hg.reader.read import UnsupportedFileError, build_document, extraction_schema, read_document

__all__ = ["UnsupportedFileError", "build_document", "extraction_schema", "read_document"]
