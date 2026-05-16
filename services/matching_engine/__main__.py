import os

import uvicorn

from services.matching_engine.app import app

uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8003')))
