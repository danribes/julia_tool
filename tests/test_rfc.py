from julia_tool.rfc import extract_rfc

def test_extracts_moral_rfc():
    assert extract_rfc("Contribuyente ACM950101ABC requiere atencion") == "ACM950101ABC"

def test_extracts_physical_rfc_lowercase_input():
    assert extract_rfc("rfc: xaxx010101000 saludos") == "XAXX010101000"

def test_no_rfc_returns_none():
    assert extract_rfc("no fiscal id here 12345") is None

def test_ignores_substring_without_boundary():
    # 13 chars but embedded in a longer token → not a valid standalone RFC
    assert extract_rfc("ZZZZAAA950101ABCDEF") is None
