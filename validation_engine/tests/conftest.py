import pytest

from services.cache_service import reset_cache


@pytest.fixture(autouse=True)
def clear_validation_cache():

    reset_cache()
    yield
    reset_cache()
