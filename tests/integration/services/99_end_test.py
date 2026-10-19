def test_end(clean_leftovers, client_emulator, live_unit_groups):
    assert len(live_unit_groups) == 3
    client_emulator.task_queue.put("STOP")
