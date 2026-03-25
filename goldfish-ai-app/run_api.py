from src.api import create_app


if __name__ == "__main__":
    import os
    import uvicorn

    app = create_app()
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
