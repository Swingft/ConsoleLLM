__version__ = "1.0.0"
__author__ = "ConsoleLLM Team"
__license__ = "MIT"

from .api import ConsoleLLM, quick_exclude_analysis, quick_sensitive_analysis
from .core.model_loader import get_model_loader, preload_models
from .analyzers import ExcludeAnalyzer, SensitiveAnalyzer

__all__ = [
    # 메인 API 클래스
    'ConsoleLLM',

    # 빠른 분석 함수들
    'quick_exclude_analysis',
    'quick_sensitive_analysis',

    # 분석기 클래스들
    'ExcludeAnalyzer',
    'SensitiveAnalyzer',

    # 모델 로더 함수들
    'get_model_loader',
    'preload_models'
]


# 패키지 정보
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