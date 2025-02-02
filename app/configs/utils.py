from pathlib import Path

from app import settings


def get_emqx_link():
    if settings.mqtt_secure:
        return f'{settings.mqtt_http_type}://{settings.mqtt_host}'
    else:
        return f'{settings.mqtt_http_type}://{settings.mqtt_host}:{settings.mqtt_api_port}'


def is_valid_ip_address(domain: str) -> bool:
    ip_address_and_port = domain.split(':')

    try:
        if len(ip_address_and_port) == 2:
            port = int(ip_address_and_port[1])

            assert port >= 0 and port <= 65536

            address = ip_address_and_port[0].split('.')
            if len(address) == 4:
                valid_list = [int(number) <= 255 and int(number) >= 0 for number in address]
                assert valid_list.count(True) == 4

                return True
        elif len(ip_address_and_port) == 1:

            address = ip_address_and_port[0].split('.')
            if len(address) == 4:
                valid_list = [int(number) <= 255 and int(number) >= 0 for number in address]
                assert valid_list.count(True) == 4

                return True

    except ValueError:
        pass
    except AssertionError:
        pass

    return False


def get_directory_size(directory: str) -> int:
    return sum(f.stat().st_size for f in Path(directory).rglob('*') if f.is_file())
