import requests

class ProxyManager:
    PROXY_TYPES = {'http': 'http', 'https': 'https', 'socks5': 'socks5h'}
    def __init__(self, proxy_url=None, use_tor=False):
        self.proxy_url = proxy_url
        self.use_tor = use_tor
    def get_proxy_dict(self):
        if self.use_tor:
            return {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
        elif self.proxy_url:
            return {'http': self.proxy_url, 'https': self.proxy_url}
        return None
    def apply_to_session(self, session):
        proxies = self.get_proxy_dict()
        if proxies:
            session.proxies = proxies
        return session
