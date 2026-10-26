from hg.data_gen.forms import FORM_FIELDS
from hg.reader.vocab import VOCAB, describe, fields_for
from hg.schemas import DocType


def test_vocab_matches_the_specimen_forms():
    for doc_type, specs in FORM_FIELDS.items():
        assert [f.name for f in fields_for(doc_type)] == [s.name for s in specs], doc_type
        assert [f.kind for f in fields_for(doc_type)] == [s.kind for s in specs], doc_type


def test_vocab_covers_every_doc_type():
    assert set(VOCAB) == set(DocType.__args__)
    assert "certified_copy (yes_no)" in describe()
