import julia_tool


def test_version_present():
    assert isinstance(julia_tool.__version__, str)
    assert julia_tool.__version__
