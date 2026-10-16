"""
Main entry point for the Face Attendance System.
Phase 1: Core pipeline implementation with all stages working.
Phase 6: Local web testing UI (no Docker required).
"""

import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import (
    FacePipeline,
    create_default_config,
    create_demo_config,
)


def _run_web(config, host: str, port: int) -> None:
    import uvicorn

    from src.api.app import create_app

    app = create_app(config)
    print(f"Local web UI: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


def main():
    """Run the face recognition attendance system."""
    import argparse

    parser = argparse.ArgumentParser(description="Face Attendance System")
    parser.add_argument("--web", action="store_true", help="run the local browser UI")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="run without ONNX models (synthetic embeddings; for UI/flow testing)",
    )
    parser.add_argument("--test", action="store_true", help="legacy console test mode (demo pipeline)")
    parser.add_argument("--host", default="127.0.0.1", help="web host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="web port (default: 8000)")
    args = parser.parse_args()

    if args.web:
        config = create_demo_config() if args.demo else create_default_config()
        _run_web(config, args.host, args.port)
        return

    if args.demo or args.test:
        print("Running in DEMO mode - using synthetic models")
        config = create_demo_config()
        config.display_output = False
        pipeline = FacePipeline(config)
        pipeline.run()
        return

    print("Running in PRODUCTION mode")
    config = create_default_config()
    pipeline = FacePipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
