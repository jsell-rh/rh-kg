"""Test the main package initialization."""


def test_import_main_package() -> None:
    """Test that the main package can be imported without errors."""
    import kg  # noqa: F401

    # Package should import successfully
    assert True


class TestPackageStructure:
    """Test the package structure and imports."""

    def test_core_module_import(self) -> None:
        """Test that core module can be imported."""
        from kg import core  # noqa: F401

    def test_cli_module_import(self) -> None:
        """Test that CLI module can be imported."""
        from kg import cli  # noqa: F401

    def test_validation_module_import(self) -> None:
        """Test that validation module can be imported."""
        from kg import validation  # noqa: F401

    def test_storage_module_import(self) -> None:
        """Test that storage module can be imported."""
        from kg import storage  # noqa: F401

    def test_api_module_import(self) -> None:
        """Test that API module can be imported."""
        from kg import api  # noqa: F401
