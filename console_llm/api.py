#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
api.py

ConsoleLLM 프로그래밍 API - 외부에서 쉽게 사용할 수 있는 인터페이스
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path

from .core.model_loader import get_model_loader, preload_models
from .analyzers.exclude_analyzer import ExcludeAnalyzer
from .analyzers.sensitive_analyzer import SensitiveAnalyzer


class ConsoleLLM:
    """ConsoleLLM 메인 API 클래스"""

    def __init__(self,
                 base_model_path: str,
                 lora_exclude_path: Optional[str] = None,
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
            lora_exclude_path: Exclude LoRA 어댑터 경로
            lora_sensitive_path: Sensitive LoRA 어댑터 경로
            n_ctx: 컨텍스트 크기
            n_gpu_layers: GPU 레이어 수
            n_threads: CPU 스레드 수
            enable_4bit_kv_cache: 4비트 KV 캐시 활성화
            auto_preload: 초기화 시 모델 자동 로드
        """
        self.base_model_path = base_model_path
        self.lora_exclude_path = lora_exclude_path
        self.lora_sensitive_path = lora_sensitive_path
        self.model_config = {
            "n_ctx": n_ctx,
            "n_gpu_layers": n_gpu_layers,
            "n_threads": n_threads,
            "enable_4bit_kv_cache": enable_4bit_kv_cache
        }

        # 파일 존재 확인
        self._validate_files()

        # 자동 모델 로드
        if auto_preload:
            self.preload_models()

    def _validate_files(self):
        """필요한 파일들의 존재 확인"""
        if not os.path.exists(self.base_model_path):
            raise FileNotFoundError(f"Base model not found: {self.base_model_path}")

        if self.lora_exclude_path and not os.path.exists(self.lora_exclude_path):
            raise FileNotFoundError(f"Exclude LoRA not found: {self.lora_exclude_path}")

        if self.lora_sensitive_path and not os.path.exists(self.lora_sensitive_path):
            raise FileNotFoundError(f"Sensitive LoRA not found: {self.lora_sensitive_path}")

    def preload_models(self):
        """모델들을 미리 메모리에 로드"""
        preload_models(
            base_model_path=self.base_model_path,
            lora_exclude_path=self.lora_exclude_path,
            lora_sensitive_path=self.lora_sensitive_path,
            **self.model_config
        )

    def analyze_exclude(self,
                        config_path: str,
                        output_dir: Optional[str] = None,
                        max_workers: int = 4) -> Dict[str, Any]:
        """
        Exclude 모드 분석 실행

        Args:
            config_path: swingft_config.json 경로
            output_dir: 출력 디렉토리
            max_workers: 병렬 처리 워커 수

        Returns:
            분석 결과
        """
        if not self.lora_exclude_path:
            raise ValueError("Exclude LoRA path not provided")

        if output_dir is None:
            output_dir = f"./output_exclude_{Path(config_path).stem}"

        analyzer = ExcludeAnalyzer(
            base_model_path=self.base_model_path,
            lora_path=self.lora_exclude_path,
            model_loader=get_model_loader(),
            **self.model_config
        )

        return analyzer.analyze_project(
            config_path=config_path,
            output_dir=output_dir,
            max_workers=max_workers
        )

    def analyze_sensitive(self,
                          config_path: str,
                          output_dir: Optional[str] = None,
                          max_workers: int = 4) -> Dict[str, Any]:
        """
        Sensitive 모드 분석 실행

        Args:
            config_path: swingft_config.json 경로
            output_dir: 출력 디렉토리
            max_workers: 병렬 처리 워커 수

        Returns:
            분석 결과
        """
        if not self.lora_sensitive_path:
            raise ValueError("Sensitive LoRA path not provided")

        if output_dir is None:
            output_dir = f"./output_sensitive_{Path(config_path).stem}"

        analyzer = SensitiveAnalyzer(
            base_model_path=self.base_model_path,
            lora_path=self.lora_sensitive_path,
            model_loader=get_model_loader(),
            **self.model_config
        )

        return analyzer.analyze_project(
            config_path=config_path,
            output_dir=output_dir,
            max_workers=max_workers
        )

    def analyze_both(self,
                     config_path: str,
                     output_base_dir: Optional[str] = None,
                     max_workers: int = 4) -> Dict[str, Dict[str, Any]]:
        """
        Exclude와 Sensitive 모드 모두 실행

        Args:
            config_path: swingft_config.json 경로
            output_base_dir: 기본 출력 디렉토리
            max_workers: 병렬 처리 워커 수

        Returns:
            {'exclude': exclude_results, 'sensitive': sensitive_results}
        """
        results = {}

        if output_base_dir is None:
            output_base_dir = f"./output_{Path(config_path).stem}"

        if self.lora_exclude_path:
            exclude_output = os.path.join(output_base_dir, "exclude")
            results['exclude'] = self.analyze_exclude(
                config_path=config_path,
                output_dir=exclude_output,
                max_workers=max_workers
            )

        if self.lora_sensitive_path:
            sensitive_output = os.path.join(output_base_dir, "sensitive")
            results['sensitive'] = self.analyze_sensitive(
                config_path=config_path,
                output_dir=sensitive_output,
                max_workers=max_workers
            )

        return results

    def analyze_batch(self,
                      config_paths: List[str],
                      output_base_dir: Optional[str] = None,
                      max_workers: int = 4) -> Dict[str, Dict[str, Any]]:
        """
        여러 설정 파일에 대해 배치 분석 실행

        Args:
            config_paths: 설정 파일 경로 리스트
            output_base_dir: 기본 출력 디렉토리
            max_workers: 병렬 처리 워커 수

        Returns:
            각 설정 파일별 분석 결과
        """
        results = {}

        for config_path in config_paths:
            config_name = Path(config_path).stem
            print(f"\n=== Processing {config_name} ===")

            if output_base_dir:
                output_dir = os.path.join(output_base_dir, config_name)
            else:
                output_dir = None

            try:
                results[config_name] = self.analyze_both(
                    config_path=config_path,
                    output_base_dir=output_dir,
                    max_workers=max_workers
                )
            except Exception as e:
                print(f"Error processing {config_name}: {e}")
                results[config_name] = {"error": str(e)}

        return results

    def clear_model_cache(self):
        """모델 캐시 정리"""
        get_model_loader().clear_cache()

    def get_model_info(self) -> Dict[str, Any]:
        """현재 설정 정보 반환"""
        return {
            "base_model_path": self.base_model_path,
            "lora_exclude_path": self.lora_exclude_path,
            "lora_sensitive_path": self.lora_sensitive_path,
            "model_config": self.model_config,
            "cached_models": get_model_loader().get_cached_models()
        }


# 편의 함수들
def quick_exclude_analysis(base_model_path: str,
                           lora_exclude_path: str,
                           config_path: str,
                           output_dir: Optional[str] = None) -> Dict[str, Any]:
    """빠른 Exclude 분석"""
    analyzer = ConsoleLLM(
        base_model_path=base_model_path,
        lora_exclude_path=lora_exclude_path,
        lora_sensitive_path=None,
        auto_preload=True
    )
    return analyzer.analyze_exclude(config_path, output_dir)


def quick_sensitive_analysis(base_model_path: str,
                             lora_sensitive_path: str,
                             config_path: str,
                             output_dir: Optional[str] = None) -> Dict[str, Any]:
    """빠른 Sensitive 분석"""
    analyzer = ConsoleLLM(
        base_model_path=base_model_path,
        lora_exclude_path=None,
        lora_sensitive_path=lora_sensitive_path,
        auto_preload=True
    )
    return analyzer.analyze_sensitive(config_path, output_dir)