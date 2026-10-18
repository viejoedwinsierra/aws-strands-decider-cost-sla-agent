from fastapi import FastAPI

app = FastAPI(title="EXP-002 baseline API", version="0.1.0")


@app.get('/health')
def health():
    return {'status': 'ok', 'mode': 'standalone'}
