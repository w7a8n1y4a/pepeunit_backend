def test_end(clean_leftovers, client_emulator):
    client_emulator.task_queue.put("STOP")
