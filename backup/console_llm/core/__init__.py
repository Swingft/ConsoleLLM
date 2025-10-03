#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
console_llm/core/__init__.py

ConsoleLLM 핵심 모듈 초기화
"""

from .base_analyzer import BaseAnalyzer
from .model_loader import OptimizedModelLoader, get_model_loader, preload_models
from .utils import (
    validate_file_exists,
    load_json_config,
    save_json_result,
    get_relative_path,
    ensure_directory,
    format_file_size,
    get_swift_files_count
)

__all__ = [
    # 기본 분석기
    'BaseAnalyzer',

    # 모델 로더
    'OptimizedModelLoader',
    'get_model_loader',
    'preload_models',

    # 유틸리티 함수들
    'validate_file_exists',
    'load_json_config',
    'save_json_result',
    'get_relative_path',
    'ensure_directory',
    'format_file_size',
    'get_swift_files_count'
]