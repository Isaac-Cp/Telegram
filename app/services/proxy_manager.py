import logging
import socket
import socks
from app.core.config import get_settings
from app.models.telegram_account import TelegramAccount

logger = logging.getLogger(__name__)

class ProxyManager:
    """
    Elite Module 2: Telegram Proxy & Account Safety System.
    Manages proxy validation and rotation to protect accounts.
    """
    
    def get_proxy_config(self, account: TelegramAccount = None):
        """
        Retrieves proxy configuration for a specific account or from global settings.
        """
        settings = get_settings()
        
        # 1. Prefer account-specific proxy
        if account and account.proxy_host and account.proxy_port:
            return {
                'proxy_type': account.proxy_type or 'socks5',
                'addr': account.proxy_host,
                'port': account.proxy_port,
                'username': account.proxy_user,
                'password': account.proxy_pass,
                'rdns': True
            }
        
        # 2. Fallback to global settings
        if settings.telegram_proxy_host and settings.telegram_proxy_port:
            return {
                'proxy_type': settings.telegram_proxy_type or 'socks5',
                'addr': settings.telegram_proxy_host,
                'port': settings.telegram_proxy_port,
                'rdns': True
            }
            
        return None

    def validate_proxy_connection(self, proxy_config: dict) -> bool:
        """
        Tests connection to Telegram servers using the provided proxy.
        """
        if not proxy_config:
            return True # No proxy, assume direct connection
            
        try:
            proxy_type = socks.SOCKS5 if proxy_config['proxy_type'] == 'socks5' else socks.HTTP
            
            s = socks.socksocket()
            s.set_proxy(
                proxy_type, 
                proxy_config['addr'], 
                proxy_config['port'], 
                username=proxy_config.get('username'),
                password=proxy_config.get('password')
            )
            s.settimeout(10)
            
            # Try to connect to a Telegram IP
            # (e.g., 149.154.167.50 is a common Telegram DC IP)
            s.connect(("149.154.167.50", 443))
            s.close()
            logger.info(f"Proxy validation successful for {proxy_config['addr']}:{proxy_config['port']}")
            return True
        except Exception as e:
            logger.error(f"Proxy validation failed for {proxy_config['addr']}:{proxy_config['port']} - Error: {e}")
            return False

proxy_manager = ProxyManager()
