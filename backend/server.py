import os
import sys
from pathlib import Path

# Let system Python load packages installed in backend/.venv
venv_site = Path(__file__).resolve().parent / '.venv' / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
if venv_site.exists():
    sys.path.insert(0, str(venv_site))

try:
    import uvicorn
except ImportError as exc:
    raise RuntimeError('uvicorn is missing. Install backend dependencies first.') from exc

from app.main import app as fastapi_app


class ApiPrefixAdapter:
    def __init__(self, inner_app):
        self.inner_app = inner_app

    async def __call__(self, scope, receive, send):
        if scope['type'] in {'http', 'websocket'}:
            path = scope.get('path', '')
            if path == '/api' or path.startswith('/api/'):
                new_scope = dict(scope)
                stripped = path[4:] or '/'
                new_scope['path'] = stripped
                root_path = scope.get('root_path', '')
                new_scope['root_path'] = f"{root_path}/api" if root_path else '/api'
                return await self.inner_app(new_scope, receive, send)
        return await self.inner_app(scope, receive, send)


def main() -> None:
    host = '0.0.0.0'
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv('PORT', '8765'))
    uvicorn.run(ApiPrefixAdapter(fastapi_app), host=host, port=port, log_level='info')


if __name__ == '__main__':
    main()
