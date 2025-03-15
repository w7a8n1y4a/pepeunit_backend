import pytest

from app import settings

if settings.test_integration_clear_data:

    @pytest.mark.last
    def test_end(clear_database):
        assert True
