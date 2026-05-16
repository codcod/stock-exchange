import os

import uvicorn

uvicorn.run(
    'services.gateway.app:app',
    host='0.0.0.0',
    port=int(os.getenv('PORT', '8000')),
    reload=False,
)
