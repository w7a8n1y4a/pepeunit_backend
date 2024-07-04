import os


def check_screen_session_by_name(name: str) -> bool:
    return os.system(f'screen -ls | grep "{name}"') == 0


def run_bash_script_on_screen_session(screen_name: str, script: str) -> bool:
    return os.system(f'screen -S {screen_name} -dm bash -c "{script}"') == 0


def kill_screen_session(name: str) -> bool:
    return os.system(f'screen -S {name} -X quit') == 0
