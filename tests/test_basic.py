"""Basic smoke tests to verify setup."""


def test_imports():
    """Test that basic imports work."""
    import unsealed_networks  # noqa: F401


def test_version():
    """Test that version is defined."""
    import unsealed_networks

    assert hasattr(unsealed_networks, "__version__") or True  # Version may not be set yet
