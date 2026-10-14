#!/usr/bin/env python3
"""Test pipeline creation after numpy fix."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from src.pipeline import create_default_config, FacePipeline
    config = create_default_config()
    p = FacePipeline(config)
    print('✓ Pipeline created successfully')
    print('  Camera backend:', p.camera.backend.__class__.__name__)
    print('  Detector loaded:', p.detector is not None)
    print('  Recognition models loaded:', len(p.ensemble_extractor.models))
    print('  Database path:', p.database.db_path)
    print('\n✅ Phase 1 pipeline is working!')
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)