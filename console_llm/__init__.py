__version__ = "1.0.0"
__author__ = "ConsoleLLM Team"
__license__ = "MIT"

import sys
import os

# 패키지 경로 설정
package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

try:
    from .api import ConsoleLLM, quick_exclude_analysis, quick_sensitive_analysis
    from .core.model_loader import get_model_loader, preload_models
    from .analyzers import ExcludeAnalyzer, SensitiveAnalyzer
except ImportError as e:
    print(f"Warning: Import error in ConsoleLLM: {e}")
    # Fallback imports
    ConsoleLLM = None
    ExcludeAnalyzer = None
    SensitiveAnalyzer = None

__all__ = [
    'ConsoleLLM',
    'quick_exclude_analysis',
    'quick_sensitive_analysis',
    'ExcludeAnalyzer',
    'SensitiveAnalyzer',
    'get_model_loader',
    'preload_models'
]

def get_version():
    """버전 정보 반환"""
    return __version__

def get_info():
    """패키지 정보 반환"""
    return {
        "name": "ConsoleLLM",
        "version": __version__,
        "author": __author__,
        "license": __license__,
        "description": "Swift 코드 분석 시스템"
    }