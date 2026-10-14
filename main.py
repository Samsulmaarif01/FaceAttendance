"""
Main entry point for the Face Attendance System.
Phase 1: Core pipeline implementation with all stages working.
"""

import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import create_default_config, FacePipeline


def main():
    """Run the face recognition attendance system."""
    # Parse command line arguments
    if "--test" in sys.argv:
        # Run in test mode
        print("Running in TEST mode - using dummy models")
        config = create_default_config()
        config.detection_model_path = ""  # Will trigger dummy detection
        config.recognition_models = []   # Will trigger dummy matching
        pipeline = FacePipeline(config)
        pipeline.run()
    else:
        # Run in production mode
        print("Running in PRODUCTION mode")
        config = create_default_config()
        pipeline = FacePipeline(config)
        pipeline.run()


if __name__ == "__main__":
    main()