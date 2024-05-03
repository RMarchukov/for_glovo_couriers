import re

def parse_proxies(text: str) -> list:
    proxy_list = []
    for proxy in text.splitlines():
        proxy_split = re.split('[@://]', proxy)
        proxy_split = list(filter(lambda x: x.strip() != '', proxy_split))

        if len(proxy_split) >= 4:
            for port in proxy_split:
                if port.isnumeric():
                    port_index = proxy_split.index(port)
                    host_index = port_index - 1

                    if port_index == len(proxy_split) - 1:
                        login_index = port_index - 3
                        password_index = port_index - 2
                    else:
                        login_index = port_index + 1
                        password_index = port_index + 2

                    proxy_list.append(f'http://{proxy_split[login_index]}:{proxy_split[password_index]}@{proxy_split[host_index]}:{proxy_split[port_index]}')
                    break

    return proxy_list
