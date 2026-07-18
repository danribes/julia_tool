import fitz  # PyMuPDF
from julia_tool.classify import extract_pdf_text


def test_extracts_text(tmp_path):
    p = str(tmp_path / "doc.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "REQUERIMIENTO de obligaciones")
    doc.save(p)
    doc.close()
    text = extract_pdf_text(p)
    assert "REQUERIMIENTO" in text
