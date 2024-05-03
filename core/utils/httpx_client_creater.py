from httpx import AsyncClient, AsyncHTTPTransport, RequestError

async def create_httpx_client(proxy: str):
    transport = AsyncHTTPTransport(retries=5)
    client = AsyncClient(transport=transport, timeout=10, proxies=proxy)

    connection = await check_connection(client)
    if connection:
        return client

async def check_connection(http_client: AsyncClient):
    try:
        response = await http_client.get('https://couriers.glovoapp.com/')
        if response.is_success:
            return True
        else:
            return False
    except RequestError:
        return False
