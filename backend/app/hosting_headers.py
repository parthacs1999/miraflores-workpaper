"""Response hardening for the externally authenticated restricted deployment."""
class HostedSecurityHeaders:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        async def hardened(message):
            if message['type']=='http.response.start':
                values={b'cache-control':b'no-store, private',b'pragma':b'no-cache',b'vary':b'Cookie, Origin, Cf-Access-Jwt-Assertion',b'x-content-type-options':b'nosniff',b'x-frame-options':b'DENY',b'referrer-policy':b'no-referrer',b'strict-transport-security':b'max-age=31536000',b'content-security-policy':b"frame-ancestors 'none'; object-src 'none'; base-uri 'self'"}
                message={**message,'headers':[(k,v) for k,v in message['headers'] if k.lower() not in values]+list(values.items())}
            await send(message)
        return await self.app(scope,receive,hardened)
