import pytest

from app import settings

if settings.test_integration_clear_data:

    @pytest.mark.last
    def test_end(clear_database, client_emulator):
        client_emulator.task_queue.put("STOP")
        assert True

else:

    @pytest.mark.last
    def test_end(client_emulator):
        client_emulator.task_queue.put("STOP")
