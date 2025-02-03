import pytest
from tests import TestConfig

def pytest_configure():
    """Initialize TestConfig when pytest starts."""
    TestConfig.init_from_env()
