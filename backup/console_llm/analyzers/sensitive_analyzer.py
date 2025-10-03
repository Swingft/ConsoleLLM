#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sensitive_analyzer.py

Sensitive 모드 전용 분석기 - config 기반 타겟 분석 (완전 재작성)
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from ..core.base_analyzer import BaseAnalyzer
from ..core.model_loader import OptimizedModelLoader
from ..core.utils import (
    extract_sensitive_identifiers,
    save_identifiers_to_txt,
    clean_and_deduplicate_identifiers
)


class SensitiveAnalyzer(BaseAnalyzer):
    """보안 취약점 분석 전용 클래스 - config 기반 타겟 분석"""

    def __init__(self, base_model_path: str, lora_path: str = None,
                 model_loader: Optional[OptimizedModelLoader] = None,
                 n_ctx: int = 4096, n_gpu_layers: int = 0, n_threads: int = None,
                 enable_4bit_kv_cache: bool = True):
        super().__init__(base_model_path, lora_path, model_loader,
                         n_ctx, n_gpu_layers, n_threads, enable_4bit_kv_cache)

        # AST 분석기 경로 설정
        current_dir = Path(__file__).parent.parent
        self.ast_analyzer_path = current_dir / "ast_analyzers" / "sensitive" / "SwiftASTAnalyzer"

        print(f"SensitiveAnalyzer 초기화 - AST 분석기: {self.ast_analyzer_path}")

    def create_model_input(self, source_file_path: str, ast_json: str) -> tuple[str, str]:
        """보안 분석용 모델 입력 프롬프트 생성"""
        try:
            with open(source_file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception:
            source_code = "// Could not read source code"

        system_prompt = ""
        instruction = "In the following Swift code, find all identifiers related to sensitive logic. Provide the names and reasoning as a JSON object."

        try:
            symbol_info_pretty = json.dumps(json.loads(ast_json), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            symbol_info_pretty = ast_json

        input_content = f"""**Swift Source Code:**
```swift
{source_code}
```

**AST Symbol Information (JSON):**
```
{symbol_info_pretty}
```"""

        user_prompt = f"{instruction}\n\n{input_content}"
        return system_prompt, user_prompt

    def extract_json_from_output(self, text: str) -> tuple[str, List[str]]:
        """모델 출력에서 JSON 추출 및 파싱"""
        if not text:
            return "", []

        try:
            start_index = text.find('{')
            end_index = text.rfind('}')
            if start_index != -1 and end_index != -1 and start_index < end_index:
                json_str = text[start_index:end_index + 1]
                data = json.loads(json_str)

                reasoning = data.get("reasoning", "")
                identifiers = data.get("identifiers", [])

                if isinstance(reasoning, str) and isinstance(identifiers, list):
                    return reasoning, [str(item) for item in identifiers]
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback 처리
        reasoning_str = ""
        identifiers_list = []

        reasoning_match = re.search(r'["\']reasoning["\']\s*:\s*["\'](.*?)["\']', text, re.DOTALL)
        if reasoning_match:
            reasoning_str = reasoning_match.group(1).strip()

        identifiers_match = re.search(r'["\']identifiers["\']\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if identifiers_match:
            content_str = identifiers_match.group(1).strip()
            if content_str:
                items = content_str.split(',')
                identifiers_list = [item.strip().strip('"\' ') for item in items if item.strip()]

        return reasoning_str, identifiers_list

    def get_cache_file_path(self, output_dir: str) -> str:
        """캐시 파일 경로 반환"""
        return os.path.join(output_dir, "sensitive_file_cache.json")

    def get_target_identifiers_from_config(self, config_path: str = None) -> List[str]:
        """config 파일에서 target_identifiers 읽기"""
        if not config_path:
            return []

        if not os.path.exists(config_path):
            print(f"Warning: Config file not found: {config_path}")
            return []

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # exclude.obfuscation에서 타겟 식별자 읽기
            target_identifiers = config.get('exclude', {}).get('obfuscation', [])

            if target_identifiers:
                print(f"Loaded {len(target_identifiers)} target identifiers from config")
            else:
                print("No target identifiers found in config file")

            return target_identifiers

        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
            return []

    def find_files_with_target_identifiers(self, project_path: str, target_identifiers: List[str]) -> List[str]:
        """타겟 식별자를 포함한 파일들 찾기"""
        return self.find_source_files_with_identifiers(project_path, target_identifiers)

    def analyze_target_files(self, target_files: List[str], cache_path: str, max_workers: int = 4) -> Dict[str, Any]:
        """타겟 파일들 분석 (캐시 지원)"""
        if not target_files:
            return {
                "analysis_results": [],
                "successful_results": [],
                "failed_results": [],
                "cache_used": False
            }

        # 캐시 로드
        file_cache = self.load_file_cache(cache_path)
        current_files = {f: self.calculate_file_hash(f) for f in target_files}

        files_to_analyze = []
        cached_results = []

        for file_path, current_hash in current_files.items():
            if current_hash is None:
                continue

            relative_path = os.path.relpath(file_path)

            if relative_path not in file_cache:
                # 새 파일
                files_to_analyze.append(file_path)
            elif file_cache[relative_path].get("hash") != current_hash:
                # 수정된 파일
                files_to_analyze.append(file_path)
            else:
                # 캐시 사용
                cached_data = file_cache[relative_path]
                cached_results.append({
                    "file_path": file_path,
                    "identifiers": cached_data.get("identifiers", [])
                })

        # 삭제된 파일들 정리
        current_relative_paths = set(os.path.relpath(f) for f in target_files)
        for cached_path in list(file_cache.keys()):
            if cached_path not in current_relative_paths:
                del file_cache[cached_path]

        print(f"Target files analysis:")
        print(f"  - Total target files: {len(target_files)}")
        print(f"  - Files to analyze: {len(files_to_analyze)}")
        print(f"  - Files using cache: {len(cached_results)}")

        # 분석할 파일이 없으면 캐시된 결과만 반환
        if not files_to_analyze:
            return {
                "analysis_results": [],
                "successful_results": cached_results,
                "failed_results": [],
                "cache_used": True,
                "file_cache": file_cache
            }

        # 새 파일들 분석
        self.preload_model()
        print(f"Starting analysis of {len(files_to_analyze)} files with {max_workers} workers...")

        analysis_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.generate_analysis, source_file): source_file
                for source_file in files_to_analyze
            }

            for future in concurrent.futures.as_completed(future_to_file):
                source_file = future_to_file[future]
                try:
                    result = future.result()
                    analysis_results.append(result)

                    # 캐시 업데이트
                    relative_path = os.path.relpath(source_file)
                    file_hash = current_files[source_file]

                    if 'error' not in result:
                        file_cache[relative_path] = {
                            "hash": file_hash,
                            "identifiers": result.get("identifiers", [])
                        }
                        print(f"✓ {os.path.basename(source_file)}: {len(result['identifiers'])} sensitive identifiers")
                    else:
                        print(f"✗ {os.path.basename(source_file)}: {result['error']}")

                except Exception as e:
                    print(f"✗ {os.path.basename(source_file)}: Exception - {e}")
                    analysis_results.append({
                        "file_path": source_file,
                        "error": str(e),
                        "identifiers": []
                    })

        # 캐시 저장
        self.save_file_cache(file_cache, cache_path)

        # 결과 분류
        successful_analysis = [r for r in analysis_results if 'error' not in r]
        failed_analysis = [r for r in analysis_results if 'error' in r]

        all_successful = cached_results + successful_analysis

        return {
            "analysis_results": analysis_results,
            "successful_results": all_successful,
            "failed_results": failed_analysis,
            "cache_used": False,
            "file_cache": file_cache
        }

    def analyze_project(self, project_path: str = None, config_path: str = None,
                        output_dir: str = "./output_sensitive", max_workers: int = 4,
                        save_individual_files: bool = False) -> Dict[str, Any]:
        """프로젝트 보안 분석 (config 기반 타겟 분석)"""
        print(f"\n=== SensitiveAnalyzer: 보안 취약점 분석 시작 ===")

        # 프로젝트 경로 결정
        try:
            project_input_path = self.resolve_project_path(project_path, config_path)
        except ValueError as e:
            return {
                "mode": "sensitive",
                "files_analyzed": 0,
                "successful": 0,
                "failed": 0,
                "total_sensitive_identifiers_found": 0,
                "unique_sensitive_identifiers": [],
                "error": str(e)
            }

        # config에서 타겟 식별자 읽기 (필수)
        target_identifiers = self.get_target_identifiers_from_config(config_path)

        if not target_identifiers:
            print("Error: No target identifiers found in config file. Sensitive analysis requires target identifiers.")
            return {
                "mode": "sensitive",
                "files_analyzed": 0,
                "successful": 0,
                "failed": 0,
                "total_sensitive_identifiers_found": 0,
                "unique_sensitive_identifiers": [],
                "error": "No target identifiers in config"
            }

        print(f"Target identifiers: {target_identifiers}")

        # 타겟 파일들 찾기
        target_files = self.find_files_with_target_identifiers(project_input_path, target_identifiers)

        if not target_files:
            print("No source files found with target identifiers")
            return {
                "mode": "sensitive",
                "files_analyzed": 0,
                "successful": 0,
                "failed": 0,
                "total_sensitive_identifiers_found": 0,
                "unique_sensitive_identifiers": [],
                "error": "No files found with target identifiers"
            }

        os.makedirs(output_dir, exist_ok=True)

        # 디버그 모드 설정
        if hasattr(self, '_debug_mode'):
            self._debug_mode = save_individual_files
        else:
            self._debug_mode = save_individual_files

        # 캐시 파일 경로
        cache_path = self.get_cache_file_path(output_dir)

        # 타겟 파일들 분석
        analysis_result = self.analyze_target_files(target_files, cache_path, max_workers)

        successful_results = analysis_result["successful_results"]
        failed_results = analysis_result["failed_results"]

        # 개별 파일 저장 (디버그 모드)
        if save_individual_files and analysis_result["analysis_results"]:
            print(f"Debug mode: 개별 JSON 파일들도 {output_dir}에 저장됩니다.")
            for result in analysis_result["analysis_results"]:
                filename = os.path.basename(result["file_path"]).replace('.swift', '_sensitive.json').replace('.h',
                                                                                                              '_sensitive.json')
                output_path = os.path.join(output_dir, filename)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

        # 식별자 추출 및 정리
        all_sensitive_identifiers = []
        for result in successful_results:
            identifiers = extract_sensitive_identifiers(result)
            all_sensitive_identifiers.extend(identifiers)

        unique_sensitive_identifiers = clean_and_deduplicate_identifiers(all_sensitive_identifiers)

        # sensitive_id.txt 파일로 저장 (항상 생성)
        sensitive_txt_path = os.path.join(output_dir, "sensitive_id.txt")
        save_identifiers_to_txt(unique_sensitive_identifiers, sensitive_txt_path)

        # 요약 결과
        summary = {
            "mode": "sensitive",
            "files_analyzed": len(target_files),
            "successful": len(successful_results),
            "failed": len(failed_results),
            "total_sensitive_identifiers_found": len(all_sensitive_identifiers),
            "unique_sensitive_identifiers": unique_sensitive_identifiers,
        }

        # 디버그 모드일 때만 results와 summary 포함
        if save_individual_files:
            summary["results"] = successful_results + failed_results

            # summary 저장
            summary_path = os.path.join(output_dir, "summary_sensitive.json")
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n=== Security Analysis Complete ===")
        print(f"Target files processed: {len(target_files)}")
        print(f"Successful: {len(successful_results)}")
        print(f"Failed: {len(failed_results)}")
        print(f"Total sensitive identifiers found: {len(all_sensitive_identifiers)}")
        print(f"Unique sensitive identifiers: {len(unique_sensitive_identifiers)}")
        print(f"Results saved to: {output_dir}")
        print(f"Identifiers saved to: {sensitive_txt_path}")

        if save_individual_files:
            print(f"Debug mode: 개별 JSON 파일들과 summary도 저장되었습니다.")

        return summary