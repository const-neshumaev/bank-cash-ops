import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Keep throttle counters from leaking between tests."""
    cache.clear()
    yield
    cache.clear()
