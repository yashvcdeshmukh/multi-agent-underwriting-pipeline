"""The package imports and reports its version."""


def test_package_imports():
    import underwriting  # noqa: F401

    assert underwriting.__version__ == "0.1.0"
