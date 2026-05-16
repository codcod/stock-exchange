import uvicorn

uvicorn.run('services.gateway.app:app', host='0.0.0.0', port=8000, reload=True)
