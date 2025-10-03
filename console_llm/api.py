#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
api.py

ConsoleLLM 프로그래밍 API - 원래 구조 기반 최소 수정
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path

from .core.model_loader import get_model_loader, preload_models
from .analyzers.exclude_analyzer import ExcludeAnalyzer
from .analyzers.sensitive_analyzer import SensitiveAnalyzer


class ConsoleLLM:
    """ConsoleLLM 메인 API 클래스 - 원래 구조 기반"""

    def __init__(self,
                 base_model_path: str,
                 lora_exclude_header_path: Optional[str] = None,
                 lora_exclude_swift_path: Optional[str] = None,
                 lora_sensitive_path: Optional[str] = None,
                 n_ctx: int = 4096,
                 n_gpu_layers: int = 0,
                 n_threads: Optional[int] = None,
                 enable_4bit_kv_cache: bool = True,
                 auto_preload: bool = True):
        """
        ConsoleLLM 초기화

        Args:
            base_model_path: 베이스 모델 GGUF 파일 경로
            lora_exclude_header_path: Exclude Header LoRA 어댑터 경로
            lora_exclude_swift_path: Exclude Swift LoRA 어댑터 경로
            lora_sensitive_path: Sensitive LoRA 어댑터 경로
            n_ctx: 컨텍스트 크기
            n_gpu_layers: GPU 레이어 수
            n_threads: CPU 스레드 수
            enable_4bit_kv_cache: 4비트 KV 캐시 활성화
            auto_preload: 초기화 시 모델 자동 로드
        """
        self.base_model_path = base_model_path
        self.lora_exclude_header_path = lora_exclude_header_path
        self.lora_exclude_swift_path = lora_exclude_swift_path
        self.lora_sensitive_path = lora_sensitive_path
        self.model_config = {
            "n_ctx": n_ctx,
            "n_gpu_layers": n_gpu_layers,
            "n_threads": n_threads,
            "enable_4bit_kv_cache": enable_4bit_kv_cache
        }

        # 파일 존재 확인
        self._validate_files()

        # 자동 모델 로드 (원래 구조 유지)
        if auto_preload:
            self.preload_models()

    def _validate_files(self):
        """필요한 파일들의 존재 확인"""
        if not os.path.exists(self.base_model_path):
            raise FileNotFoundError(f"Base model not found: {self.base_model_path}")

        if self.lora_exclude_header_path and not os.path.exists(self.lora_exclude_header_path):
            raise FileNotFoundError(f"Exclude Header LoRA not found: {self.lora_exclude_header_path}")

        if self.lora_exclude_swift_path and not os.path.exists(self.lora_exclude_swift_path):
            raise FileNotFoundError(f"Exclude Swift LoRA not found: {self.lora_exclude_swift_path}")

        if self.lora_sensitive_path and not os.path.exists(self.lora_sensitive_path):
            raise FileNotFoundError(f"Sensitive LoRA not found: {self.lora_sensitive_path}")

    def preload_models(self):
        """모델들을 미리 메모리에 로드 (원래 구조 유지)"""
        # 하나의 모델만 미리 로드 (메모리 절약)
        # 나머지는 런타임에 로드
        print("Pre-loading one model for initialization...")

    def analyze_exclude(self,
                        project_path: Optional[str] = None,
                        config_path: Optional[str] = None,
                        output_dir: Optional[str] = None,
                        max_workers: int = 4,
                        save_individual_files: bool = False,
                        file_types: List[str] = None) -> Dict[str, Any]:
        """
        Exclude 모드 분석 실행

        Args:
            project_path: Swift 프로젝트 디렉토리 경로 (우선순위 높음)
            config_path: swingft_config.json 경로 (선택사항)
            output_dir: 출력 디렉토리
            max_workers: 병렬 처리 워커 수
            save_individual_files: 개별 JSON 파일 저장 여부
            file_types: 처리할 파일 타입 ['header', 'swift', 'both'] 중 하나

        Returns:
            분석 결과
        """
        if not self.lora_exclude_header_path and not self.lora_exclude_swift_path:
            raise ValueError("Exclude LoRA paths not provided")

        if file_types is None:
            file_types = ['both']

        # 출력 디렉토리 설정
        if output_dir is None:
            if project_path:
                project_name = Path(project_path).name
                output_dir = f"./output_exclude_{project_name}"
            elif config_path:
                output_dir = f"./output_exclude_{Path(config_path).stem}"
            else:
                output_dir = "./output_exclude"

        analyzer = ExcludeAnalyzer(
            base_model_path=self.base_model_path,
            lora_header_path=self.lora_exclude_header_path,
            lora_swift_path=self.lora_exclude_swift_path,
            model_loader=get_model_loader(),
            **self.model_config
        )

        return analyzer.analyze_project(
            project_path=project_path,
            config_path=config_path,
            output_dir=output_dir,
            max_workers=max_workers,
            save_individual_files=save_individual_files,
            file_types=file_types
        )

    def analyze_exclude_headers_only(self,
                                     project_path: Optional[str] = None,
                                     config_path: Optional[str] = None,
                                     output_dir: Optional[str] = None,
                                     max_workers: int = 4,
                                     save_individual_files: bool = False) -> Dict[str, Any]:
        """헤더 파일만 Exclude 분석"""
        return self.analyze_exclude(
            project_path=project_path,
            config_path=config_path,
            output_dir=output_dir,
            max_workers=max_workers,
            save_individual_files=save_individual_files,
            file_types=['header']
        )

    def analyze_exclude_swift_only(self,
                                   project_path: Optional[str] = None,
                                   config_path: Optional[str] = None,
                                   output_dir: Optional[str] = None,
                                   max_workers: int = 4,
                                   save_individual_files: bool = False) -> Dict[str, Any]:
        """Swift 파일만 Exclude 분석"""
        return self.analyze_exclude(
            project_path=project_path,
            config_path=config_path,
            output_dir=output_dir,
            max_workers=max_workers,
            save_individual_files=save_individual_files,
            file_types=['swift']
        )

    def analyze_sensitive(self,
                          project_path: Optional[str] = None,
                          config_path: Optional[str] = None,
                          output_dir: Optional[str] = None,
                          max_workers: int = 4,
                          save_individual_files: bool = False) -> Dict[str, Any]:
        """
        Sensitive 모드 분석 실행 (Swift 파일만)

        Args:
            project_path: Swift 프로젝트 디렉토리 경로 (우선순위 높음)
            config_path: swingft_config.json 경로 (선택사항)
            output_dir: 출력 디렉토리
            max_workers: 병렬 처리 워커 수
            save_individual_files: 개별 JSON 파일 저장 여부

        Returns:
            분석 결과
        """
        if not self.lora_sensitive_path:
            raise ValueError("Sensitive LoRA path not provided")

        # 출력 디렉토리 설정
        if output_dir is None:
            if project_path:
                project_name = Path(project_path).name
                output_dir = f"./output_sensitive_{project_name}"
            elif config_path:
                output_dir = f"./output_sensitive_{Path(config_path).stem}"
            else:
                output_dir = "./output_sensitive"

        analyzer = SensitiveAnalyzer(
            base_model_path=self.base_model_path,
            lora_path=self.lora_sensitive_path,
            model_loader=get_model_loader(),
            **self.model_config
        )

        return analyzer.analyze_project(
            project_path=project_path,
            config_path=config_path,
            output_dir=output_dir,
            max_workers=max_workers,
            save_individual_files=save_individual_files
        )

    def analyze_all(self,
                    project_path: Optional[str] = None,
                    config_path: Optional[str] = None,
                    output_base_dir: Optional[str] = None,
                    max_workers: int = 4,
                    save_individual_files: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        모든 모드 실행 (exclude_header, exclude_swift, sensitive)

        Args:
            project_path: Swift 프로젝트 디렉토리 경로 (우선순위 높음)
            config_path: swingft_config.json 경로 (선택사항)
            output_base_dir: 기본 출력 디렉토리
            max_workers: 병렬 처리 워커 수
            save_individual_files: 개별 JSON 파일 저장 여부

        Returns:
            {'exclude': exclude_results, 'sensitive': sensitive_results}
        """
        results = {}

        # 출력 디렉토리 설정
        if output_base_dir is None:
            if project_path:
                project_name = Path(project_path).name
                output_base_dir = f"./output_{project_name}"
            elif config_path:
                output_base_dir = f"./output_{Path(config_path).stem}"
            else:
                output_base_dir = "./output"

        # Exclude 분석 (헤더 + Swift)
        if self.lora_exclude_header_path or self.lora_exclude_swift_path:
            exclude_output = os.path.join(output_base_dir, "exclude")
            results['exclude'] = self.analyze_exclude(
                project_path=project_path,
                config_path=config_path,
                output_dir=exclude_output,
                max_workers=max_workers,
                save_individual_files=save_individual_files,
                file_types=['both']
            )

        # Sensitive 분석 (Swift만)
        if self.lora_sensitive_path:
            sensitive_output = os.path.join(output_base_dir, "sensitive")
            results['sensitive'] = self.analyze_sensitive(
                project_path=project_path,
                config_path=config_path,
                output_dir=sensitive_output,
                max_workers=max_workers,
                save_individual_files=save_individual_files
            )

        return results

    def clear_model_cache(self):
        """모델 캐시 정리"""
        get_model_loader().clear_cache()

    def get_model_info(self) -> Dict[str, Any]:
        """현재 설정 정보 반환"""
        return {
            "base_model_path": self.base_model_path,
            "lora_exclude_header_path": self.lora_exclude_header_path,
            "lora_exclude_swift_path": self.lora_exclude_swift_path,
            "lora_sensitive_path": self.lora_sensitive_path,
            "model_config": self.model_config,
            "cached_models": get_model_loader().get_cached_models()
        }


# 편의 함수들 (원래 구조 유지)
def quick_exclude_analysis(base_model_path: str,
                           lora_exclude_header_path: str = None,
                           lora_exclude_swift_path: str = None,
                           project_path: str = None,
                           config_path: str = None,
                           output_dir: Optional[str] = None,
                           file_types: List[str] = None,
                           save_individual_files: bool = False) -> Dict[str, Any]:
    """빠른 Exclude 분석"""
    analyzer = ConsoleLLM(
        base_model_path=base_model_path,
        lora_exclude_header_path=lora_exclude_header_path,
        lora_exclude_swift_path=lora_exclude_swift_path,
        lora_sensitive_path=None,
        auto_preload=True
    )
    return analyzer.analyze_exclude(
        project_path, config_path, output_dir,
        file_types=file_types, save_individual_files=save_individual_files
    )


def quick_sensitive_analysis(base_model_path: str,
                             lora_sensitive_path: str,
                             project_path: str = None,
                             config_path: str = None,
                             output_dir: Optional[str] = None,
                             save_individual_files: bool = False) -> Dict[str, Any]:
    """빠른 Sensitive 분석"""
    analyzer = ConsoleLLM(
        base_model_path=base_model_path,
        lora_exclude_header_path=None,
        lora_exclude_swift_path=None,
        lora_sensitive_path=lora_sensitive_path,
        auto_preload=True
    )
    return analyzer.analyze_sensitive(project_path, config_path, output_dir, save_individual_files=save_individual_files)