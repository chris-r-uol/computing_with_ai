def test_package_imports_and_reports_version():
    import cwai
    assert isinstance(cwai.__version__, str)
    assert cwai.__version__
