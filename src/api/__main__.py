"""Run the local web UI: ``python -m src.api [--real] [--host H] [--port P]``."""

import argparse

from src.api.app import create_app
from src.pipeline import create_default_config, create_demo_config


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Face Attendance local web UI")
    parser.add_argument("--real", action="store_true", help="use real ONNX models (default: demo)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    config = create_default_config() if args.real else create_demo_config()
    app = create_app(config)
    print(f"Local web UI: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
