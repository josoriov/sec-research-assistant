"""Extraction tests: heading tracking, table text, bounding, stable hashes."""
from extraction.parse import PROCESSING_VERSION, extract_blocks, passage_hash
from extraction.pipeline import merge_accession_metadata, submission_records

HTML = b"""
<html><body>
<div>UNITED STATES SECURITIES AND EXCHANGE COMMISSION</div>
<div>Item 1. Business</div>
<div>Apple designs, manufactures and markets smartphones and personal computers.</div>
<div>Item 7. Management's Discussion and Analysis</div>
<div>Total net sales increased during the year.</div>
<table>
  <tr><td>Net sales</td><td>100</td></tr>
  <tr><td>Cost of sales</td><td>40</td></tr>
</table>
</body></html>
"""


def test_extract_blocks_tracks_headings_and_tables():
    blocks = extract_blocks(HTML)
    sections = {block["section"] for block in blocks}
    assert "Item 1. Business" in sections
    assert "Item 7. Management's Discussion and Analysis" in sections

    business = [b for b in blocks if b["section"] == "Item 1. Business"]
    assert business and "smartphones" in business[0]["text"]
    # The heading itself is carried as the first chunk of its section.
    assert business[0]["text"].startswith("Item 1. Business")

    mda_text = " ".join(b["text"] for b in blocks
                        if b["section"] == "Item 7. Management's Discussion and Analysis")
    assert "Net sales | 100" in mda_text
    assert "Cost of sales | 40" in mda_text


def test_extract_blocks_is_bounded_and_ordered():
    long_text = " ".join(f"word{i}" for i in range(400))
    html = f"<div>Item 2. Properties</div><div>{long_text}</div>".encode()
    blocks = extract_blocks(html, max_chars=200)
    assert len(blocks) > 1
    assert [b["block_ordinal"] for b in blocks] == list(range(len(blocks)))
    assert all(len(b["text"]) <= 200 for b in blocks)
    # Re-running produces identical output (deterministic hashes/order).
    assert extract_blocks(html, max_chars=200) == blocks


def test_blocks_before_first_heading_have_no_section():
    blocks = extract_blocks(b"<div>Cover page text</div>")
    assert len(blocks) == 1
    assert blocks[0]["section"] is None


def test_table_with_block_cells_keeps_labels_and_values():
    html = (b"<div>Item 7. Results</div>"
            b"<table><tr><td>Revenue</td><td><div>100</div></td></tr>"
            b"<tr><td>Cost</td><td><p>40</p></td></tr></table>")
    blocks = extract_blocks(html)
    text = " ".join(b["text"] for b in blocks)
    assert "Revenue | 100" in text
    assert "Cost | 40" in text


def test_table_preserves_empty_cell_positions():
    html = (b"<table><tr><th>Metric</th><th>2024</th><th>2023</th></tr>"
            b"<tr><td>Revenue</td><td></td><td><div>100</div></td></tr></table>")
    text = " ".join(b["text"] for b in extract_blocks(html))
    assert "Revenue | | 100" in text


def test_nested_table_is_rendered_once():
    html = (b"<table><tr><td>Revenue"
            b"<table><tr><td>100</td></tr></table></td></tr></table>")
    text = " ".join(b["text"] for b in extract_blocks(html))
    assert text.count("Revenue") == 1
    assert text.count("100") == 1


def test_bounding_counts_joining_separators():
    html = b"<div>a</div>" * 1500
    blocks = extract_blocks(html)
    assert len(blocks) > 1
    assert all(len(b["text"]) <= 1500 for b in blocks)
    # No text is dropped by the grouping.
    assert sum(b["text"].count("a") for b in blocks) == 1500


def test_long_heading_respects_custom_bound():
    heading = "Item 7. " + "x" * 60
    blocks = extract_blocks(f"<div>{heading}</div>".encode(), max_chars=40)
    assert blocks
    assert all(len(b["text"]) <= 40 for b in blocks)


def test_passage_hash_depends_on_content_section_and_version():
    base = passage_hash(PROCESSING_VERSION, "Item 1.", "hello")
    assert base == passage_hash(PROCESSING_VERSION, "Item 1.", "hello")
    assert base != passage_hash(PROCESSING_VERSION, "Item 1.", "world")
    assert base != passage_hash(PROCESSING_VERSION, "Item 2.", "hello")
    assert base != passage_hash("some-other-version", "Item 1.", "hello")


# --- accession metadata from root and older-history snapshots (F014) ---------

def test_submission_records_reads_root_and_columnar_history():
    root = {"filings": {"recent": {"accessionNumber": ["a", "b"], "form": ["10-K", "10-K"]}}}
    history = {"accessionNumber": ["c"], "form": ["10-K"], "reportDate": ["2015-09-26"]}
    assert [r["accessionNumber"] for r in submission_records(root)] == ["a", "b"]
    assert [r["accessionNumber"] for r in submission_records(history)] == ["c"]


def test_merge_accession_metadata_keeps_older_accessions_and_fills_gaps():
    newest = {"filings": {"recent": {
        "accessionNumber": ["new"], "form": ["10-K"], "filingDate": ["2025-10-31"],
        "reportDate": ["2025-09-27"], "primaryDocument": ["new.htm"],
    }}}
    older = {"accessionNumber": ["old"], "form": ["10-K"], "filingDate": ["2016-10-26"],
             "reportDate": ["2016-09-24"], "primaryDocument": ["old.htm"]}
    merged = merge_accession_metadata([newest, older])
    # An accession only present in older history is retained.
    assert merged["old"]["reportDate"] == "2016-09-24"
    assert merged["new"]["form"] == "10-K"


def test_merge_never_blanks_known_metadata_with_absence():
    newest = {"filings": {"recent": {
        "accessionNumber": ["x"], "form": [None], "filingDate": [None],
        "reportDate": [None], "primaryDocument": [None],
    }}}
    older = {"accessionNumber": ["x"], "form": ["10-K"], "filingDate": ["2015-10-28"],
             "reportDate": ["2015-09-26"], "primaryDocument": ["x.htm"]}
    merged = merge_accession_metadata([newest, older])
    assert merged["x"]["form"] == "10-K"
    assert merged["x"]["filingDate"] == "2015-10-28"


def test_merge_treats_blank_fields_as_missing():
    newest = {"filings": {"recent": {
        "accessionNumber": ["x"], "form": [""], "filingDate": ["   "],
        "reportDate": [""], "primaryDocument": [""],
    }}}
    older = {"accessionNumber": ["x"], "form": ["10-K"], "filingDate": ["2015-10-28"],
             "reportDate": ["2015-09-26"], "primaryDocument": ["x.htm"]}
    merged = merge_accession_metadata([newest, older])
    assert merged["x"] == {
        "accessionNumber": "x", "form": "10-K", "filingDate": "2015-10-28",
        "reportDate": "2015-09-26", "primaryDocument": "x.htm",
    }


# --- extraction run: empty documents are recorded as failures (F017) ---------

class _FakeConn:
    def close(self):
        pass


def _patch_run(monkeypatch, html):
    from extraction import pipeline
    recorded = {}

    monkeypatch.setattr(pipeline.db, "connect", lambda: _FakeConn())
    monkeypatch.setattr(pipeline, "_minio_client", lambda: None)
    monkeypatch.setattr(pipeline.db, "ensure_schema", lambda conn: None)
    monkeypatch.setattr(pipeline.db, "load_filing_manifests", lambda conn: [
        {"id": 1, "cik": 1, "accession": "a", "url": "u", "object_key": "k"}
    ])
    monkeypatch.setattr(pipeline.db, "load_submission_objects", lambda conn, cik: [])
    monkeypatch.setattr(pipeline, "_read_object", lambda client, bucket, key: html)
    monkeypatch.setattr(pipeline.db, "upsert_document",
                        lambda conn, **kwargs: recorded.update(kwargs))
    monkeypatch.setattr(pipeline.db, "replace_blocks", lambda conn, **kwargs: 0)
    return pipeline, recorded


def test_run_records_no_usable_text_for_empty_document(monkeypatch):
    pipeline, recorded = _patch_run(
        monkeypatch, b"<html><body><span>Revenue grew 10 percent.</span></body></html>"
    )
    documents, passages, failures = pipeline.run()
    assert (documents, passages, failures) == (0, 0, 1)
    assert recorded["extraction_error"] == "no_usable_text"


def test_run_counts_documents_with_usable_text(monkeypatch):
    pipeline, recorded = _patch_run(
        monkeypatch, b"<div>Item 1. Business</div><div>We sell devices.</div>"
    )
    documents, passages, failures = pipeline.run()
    assert failures == 0 and documents == 1 and passages == 1
    assert recorded["extraction_error"] is None
