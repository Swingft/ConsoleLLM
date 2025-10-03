#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
api.py

ConsoleLLM 프로그래밍 API - 완전 재작성
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path

from .core.model_loader import get_model_loader
from .analyzers.exclude_analyzer import ExcludeAnalyzer
from .analyzers.sensitive_analyzer import SensitiveAnalyzer


class ConsoleLLM:
    """ConsoleLLM 메인 API 클래스"""

    def __init__(self,
                 base_model_path: str,
                 lora_exclude_path: Optional[str] = None,
                 lora_exclude_header_path: Optional[str] = None,
                 lora_sensitive_path: Optional[str] = None,
                 n_ctx: int = 4096,
                 n_gpu_layers: int = 0,
                 n_threads: Optional[int] = None,
                 enable_4bit_kv_cache: bool = True,
                 auto_preload: bool = True):
        """ConsoleLLM 초기화"""
        self.base_model_path = base_model_path
        self.lora_exclude_path = lora_exclude_path
        self.lora_exclude_header_path = lora_exclude_header_path
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

        if self.lora_exclude_header_path and not os.path.exists(self.lora_exclude_header_path):
            raise FileNotFoundError(f"Exclude header LoRA not found: {self.lora_exclude_header_path}")

        if self.lora_sensitive_path and not os.path.exists(self.lora_sensitive_path):
            raise FileNotFoundError(f"Sensitive LoRA not found: {self.lora_sensitive_path}")

    def preload_models(self):
        """모델들을 미리 메모리에 로드"""
        model_loader = get_model_loader()

        # 기본 모델들만 미리 로드 (필요시 동적 로드)
        if self.lora_exclude_path:
            model_loader.load_model(
                base_model_path=self.base_model_path,
                lora_path=self.lora_exclude_path,
                **self.model_config
            )

        if self.lora_sensitive_path:
            model_loader.load_model(
                base_model_path=self.base_model_path,
                lora_path=self.lora_sensitive_path,
                **self.model_config
            )

    def analyze_exclude(self,
                        project_path: Optional[str] = None,
                        config_path: Optional[str] = None,
                        output_dir: Optional[str] = None,
                        max_workers: int = 4,
                        save_individual_files: bool = False,
                        force_full_analysis: bool = False) -> Dict[str, Any]:
        """Exclude 모드 분석 실행"""
        if not self.lora_exclude_path:
            raise ValueError("Exclude LoRA path not provided")

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
            lora_path=self.lora_exclude_path,
            lora_header_path=self.lora_exclude_header_path,
            model_loader=get_model_loader(),
            **self.model_config
        )

        return analyzer.analyze_project(
            project_path=project_path,
            config_path=config_path,
            output_dir=output_dir,
            max_workers=max_workers,
            save_individual_files=save_individual_files,
            force_full_analysis=force_full_analysis
        )

    def analyze_sensitive(self,
                          project_path: Optional[str] = None,
                          config_path: Optional[str] = None,
                          output_dir: Optional[str] = None,
                          max_workers: int = 4,
                          save_individual_files: bool = False) -> Dict[str, Any]:
        """Sensitive 모드 분석 실행 (config 필수)"""
        if not self.lora_sensitive_path:
            raise ValueError("Sensitive LoRA path not provided")

        if not config_path:
            raise ValueError("Sensitive analysis requires config file with target identifiers")

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

    def analyze_both(self,
                     project_path: Optional[str] = None,
                     config_path: Optional[str] = None,
                     output_base_dir: Optional[str] = None,
                     max_workers: int = 4,
                     save_individual_files: bool = False,
                     force_full_analysis: bool = False) -> Dict[str, Dict[str, Any]]:
        """Exclude와 Sensitive 모드 모두 실행"""
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

        # Exclude 분석
        if self.lora_exclude_path:
            exclude_output = os.path.join(output_base_dir, "exclude")
            try:
                results['exclude'] = self.analyze_exclude(
                    project_path=project_path,
                    config_path=config_path,
                    output_dir=exclude_output,
                    max_workers=max_workers,
                    save_individual_files=save_individual_files,
                    force_full_analysis=force_full_analysis
                )
            except Exception as e:
                print(f"Exclude analysis failed: {e}")
                results['exclude'] = {"error": str(e)}

        # Sensitive 분석
        if self.lora_sensitive_path:
            sensitive_output = os.path.join(output_base_dir, "sensitive")
            try:
                results['sensitive'] = self.analyze_sensitive(
                    project_path=project_path,
                    config_path=config_path,
                    output_dir=sensitive_output,
                    max_workers=max_workers,
                    save_individual_files=save_individual_files
                )
            except ValueError as e:
                print(f"Sensitive analysis skipped: {e}")
                results['sensitive'] = {"error": str(e)}
            except Exception as e:
                print(f"Sensitive analysis failed: {e}")
                results['sensitive'] = {"error": str(e)}

        return results

    def analyze_batch(self,
                      project_paths: List[str],
                      config_paths: Optional[List[str]] = None,
                      output_base_dir: Optional[str] = None,
                      max_workers: int = 4,
                      save_individual_files: bool = False,
                      force_full_analysis: bool = False) -> Dict[str, Dict[str, Any]]:
        """여러 프로젝트에 대해 배치 분석 실행"""
        results = {}

        if not project_paths:
            raise ValueError("project_paths가 필요합니다")

        # config_paths가 없으면 None 리스트로 채움
        if not config_paths:
            config_paths = [None] * len(project_paths)
        elif len(config_paths) != len(project_paths):
            raise ValueError("project_paths와 config_paths의 길이가 일치해야 합니다")

        for i, project_path in enumerate(project_paths):
            config_path = config_paths[i] if i < len(config_paths) else None
            project_name = Path(project_path).name

            print(f"\n=== Processing {project_name} ===")

            if output_base_dir:
                output_dir = os.path.join(output_base_dir, project_name)
            else:
                output_dir = None

            try:
                results[project_name] = self.analyze_both(
                    project_path=project_path,
                    config_path=config_path,
                    output_base_dir=output_dir,
                    max_workers=max_workers,
                    save_individual_files=save_individual_files,
                    force_full_analysis=force_full_analysis
                )
            except Exception as e:
                print(f"Error processing {project_name}: {e}")
                results[project_name] = {"error": str(e)}

        return results

    def clear_model_cache(self):
        """모델 캐시 정리"""
        get_model_loader().clear_cache()

    def get_model_info(self) -> Dict[str, Any]:
        """현재 설정 정보 반환"""
        return {
            "base_model_path": self.base_model_path,
            "lora_exclude_path": self.lora_exclude_path,
            "lora_exclude_header_path": self.lora_exclude_header_path,
            "lora_sensitive_path": self.lora_sensitive_path,
            "model_config": self.model_config,
            "cached_models": get_model_loader().get_cached_models()
        }


# 편의 함수들
def quick_exclude_analysis(base_model_path: str,
                           lora_exclude_path: str,
                           project_path: str,
                           config_path: Optional[str] = None,
                           output_dir: Optional[str] = None,
                           lora_exclude_header_path: Optional[str] = None,
                           save_individual_files: bool = False,
                           force_full_analysis: bool = False) -> Dict[str, Any]:
    """빠른 Exclude 분석"""
    analyzer = ConsoleLLM(
        base_model_path=base_model_path,
        lora_exclude_path=lora_exclude_path,
        lora_exclude_header_path=lora_exclude_header_path,
        lora_sensitive_path=None,
        auto_preload=True
    )
    return analyzer.analyze_exclude(
        project_path=project_path,
        config_path=config_path,
        output_dir=output_dir,
        save_individual_files=save_individual_files,
        force_full_analysis=force_full_analysis
    )


def quick_sensitive_analysis(base_model_path: str,
                             lora_sensitive_path: str,
                             project_path: str,
                             config_path: str,
                             output_dir: Optional[str] = None,
                             save_individual_files: bool = False) -> Dict[str, Any]:
    """빠른 Sensitive 분석 (config 필수)"""
    analyzer = ConsoleLLM(
        base_model_path=base_model_path,
        lora_exclude_path=None,
        lora_sensitive_path=lora_sensitive_path,
        auto_preload=True
    )
    return analyzer.analyze_sensitive(
        project_path=project_path,
        config_path=config_path,
        output_dir=output_dir,
        save_individual_files=save_individual_files
    )