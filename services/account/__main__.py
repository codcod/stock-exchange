import os

import uvicorn

from services.account.app import app

uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8006')))
