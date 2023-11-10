import typer

def start_app(reload: bool = False):
    import uvicorn
    uvicorn.run(
        "main:app",
        host = "0.0.0.0",
        port = 8080,
        reload = reload
    )

if __name__ == "__main__":
    typer.run(start_app)