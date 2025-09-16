import typer
import os

def start_app(reload: bool = False):
    import uvicorn
    # Cloud Run asigna el puerto dinámicamente
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "main:app",
        host = "0.0.0.0",
        port = port,
        reload = reload
    )

if __name__ == "__main__":
    typer.run(start_app)