#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
exclude_analyzer.py

Exclude 모드 전용 분석기 - Swift와 Objective-C 헤더 파일 지원
"""

import os
import json
import re
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from ..core.base_analyzer import BaseAnalyzer
from ..core.model_loader import OptimizedModelLoader
from ..core.utils import (
    extract_symbol_names_from_exclude_result,
    save_identifiers_to_txt,
    clean_and_deduplicate_identifiers
)


class ExcludeAnalyzer(BaseAnalyzer):
    """난독화 제외 분석 전용 클래스 - Swift와 Objective-C 헤더 파일 지원"""

    def __init__(self, base_model_path: str, lora_path: str = None,
                 lora_header_path: str = None,
                 model_loader: Optional[OptimizedModelLoader] = None,
                 n_ctx: int = 4096, n_gpu_layers: int = 0, n_threads: int = None,
                 enable_4bit_kv_cache: bool = True):
        super().__init__(base_model_path, lora_path, model_loader,
                         n_ctx, n_gpu_layers, n_threads, enable_4bit_kv_cache)

        # LoRA 경로들
        self.lora_swift_path = lora_path  # Swift용 LoRA
        self.lora_header_path = lora_header_path  # 헤더용 LoRA

        # AST 분석기 경로 설정
        current_dir = Path(__file__).parent.parent
        self.ast_analyzer_path = current_dir / "ast_analyzers" / "exclude" / "SwiftASTAnalyzer"

        print(f"ExcludeAnalyzer 초기화")
        print(f"  - Swift LoRA: {self.lora_swift_path}")
        print(f"  - Header LoRA: {self.lora_header_path}")
        print(f"  - AST 분석기: {self.ast_analyzer_path}")

    def create_model_input_swift(self, source_file_path: str, ast_json: str) -> tuple[str, str]:
        """Swift 파일용 모델 입력 프롬프트 생성"""
        try:
            with open(source_file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception:
            source_code = "// Could not read source code"

        try:
            symbol_info_dict = json.loads(ast_json)
        except json.JSONDecodeError:
            symbol_info_dict = {}

        system_prompt = ""
        instruction = "Identify which identifiers in the Swift code should be excluded from obfuscation based on the provided AST analysis, and provide detailed reasoning."

        input_data = {
            "swift_code": source_code,
            "symbol_info": symbol_info_dict
        }

        user_prompt = f"{instruction}\n\nInput: {json.dumps(input_data, ensure_ascii=False, indent=2)}"
        return system_prompt, user_prompt

    def create_model_input_header(self, source_file_path: str) -> tuple[str, str]:
        """Objective-C 헤더 파일용 모델 입력 프롬프트 생성 (AST 없음)"""
        try:
            with open(source_file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception:
            source_code = "// Could not read source code"

        system_prompt = ""
        instruction = "Identify which identifiers in the Objective-C header file should be excluded from obfuscation. Focus on public interfaces, exposed APIs, and framework dependencies."

        input_data = {
            "header_code": source_code,
            "file_type": "objective-c_header"
        }

        user_prompt = f"{instruction}\n\nInput: {json.dumps(input_data, ensure_ascii=False, indent=2)}"
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
                exclusions = data.get("exclusions", [])

                identifiers = []
                for exclusion in exclusions:
                    if isinstance(exclusion, dict) and "identifier" in exclusion:
                        identifiers.append(exclusion["identifier"])
                    elif isinstance(exclusion, str):
                        identifiers.append(exclusion)

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

        exclusions_match = re.search(r'["\']exclusions["\']\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if exclusions_match:
            content_str = exclusions_match.group(1).strip()
            if content_str:
                identifier_matches = re.findall(r'["\']identifier["\']\s*:\s*["\']([^"\']+)["\']', content_str)
                identifiers_list = identifier_matches

        return reasoning_str, identifiers_list

    def generate_analysis_swift(self, source_file_path: str) -> Dict[str, Any]:
        """Swift 파일 분석"""
        ast_json = self.run_swift_analyzer(source_file_path)
        if not ast_json:
            return {
                "file_path": source_file_path,
                "error": "AST analysis failed",
                "identifiers": []
            }

        system_prompt, user_prompt = self.create_model_input_swift(source_file_path, ast_json)

        try:
            # Swift용 LoRA로 모델 로드
            model = self.model_loader.load_model(
                base_model_path=self.base_model_path,
                lora_path=self.lora_swift_path,
                **self.model_config
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = model.create_chat_completion(
                messages=messages,
                temperature=0.2,
                top_p=0.95,
                max_tokens=4096,
            )

            raw_output = response['choices'][0]['message']['content']
            reasoning, identifiers = self.extract_json_from_output(raw_output)

            return {
                "file_path": source_file_path,
                "identifiers": identifiers,
                "raw_output": raw_output if hasattr(self, '_debug_mode') and self._debug_mode else None,
                "ast_json": ast_json if hasattr(self, '_debug_mode') and self._debug_mode else None
            }

        except Exception as e:
            return {
                "file_path": source_file_path,
                "error": f"Model inference failed: {e}",
                "identifiers": []
            }

    def generate_analysis_header(self, source_file_path: str) -> Dict[str, Any]:
        """Objective-C 헤더 파일 분석 (AST 없음)"""
        system_prompt, user_prompt = self.create_model_input_header(source_file_path)

        try:
            # 헤더용 LoRA로 모델 로드
            model = self.model_loader.load_model(
                base_model_path=self.base_model_path,
                lora_path=self.lora_header_path,
                **self.model_config
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = model.create_chat_completion(
                messages=messages,
                temperature=0.2,
                top_p=0.95,
                max_tokens=4096,
            )

            raw_output = response['choices'][0]['message']['content']
            reasoning, identifiers = self.extract_json_from_output(raw_output)

            return {
                "file_path": source_file_path,
                "identifiers": identifiers,
                "raw_output": raw_output if hasattr(self, '_debug_mode') and self._debug_mode else None
            }

        except Exception as e:
            return {
                "file_path": source_file_path,
                "error": f"Model inference failed: {e}",
                "identifiers": []
            }

    def separate_files_by_type(self, source_files: List[str]) -> tuple[List[str], List[str]]:
        """파일들을 Swift와 헤더로 분리"""
        swift_files = [f for f in source_files if f.endswith('.swift')]
        header_files = [f for f in source_files if f.endswith('.h')]
        return swift_files, header_files

    def analyze_files_by_type(self, source_files: List[str], cache_path: str,
                              max_workers: int = 4) -> Dict[str, Any]:
        """파일 타입별로 단계적 분석"""
        swift_files, header_files = self.separate_files_by_type(source_files)

        print(f"Analysis plan:")
        print(f"  - Swift files: {len(swift_files)}")
        print(f"  - Header files: {len(header_files)}")

        # 캐시 로드
        file_cache = self.load_file_cache(cache_path)
        current_files = {f: self.calculate_file_hash(f) for f in source_files}

        # 분석이 필요한 파일들 분류
        swift_to_analyze = []
        headers_to_analyze = []
        cached_results = []

        for file_path, current_hash in current_files.items():
            if current_hash is None:
                continue

            relative_path = os.path.relpath(file_path)

            if relative_path not in file_cache:
                # 새 파일
                if file_path.endswith('.swift'):
                    swift_to_analyze.append(file_path)
                elif file_path.endswith('.h'):
                    headers_to_analyze.append(file_path)
            elif file_cache[relative_path].get("hash") != current_hash:
                # 수정된 파일
                if file_path.endswith('.swift'):
                    swift_to_analyze.append(file_path)
                elif file_path.endswith('.h'):
                    headers_to_analyze.append(file_path)
            else:
                # 캐시 사용
                cached_data = file_cache[relative_path]
                cached_results.append({
                    "file_path": file_path,
                    "identifiers": cached_data.get("identifiers", [])
                })

        # 삭제된 파일들 정리
        current_relative_paths = set(os.path.relpath(f) for f in source_files)
        for cached_path in list(file_cache.keys()):
            if cached_path not in current_relative_paths:
                del file_cache[cached_path]

        print(f"Incremental analysis summary:")
        print(f"  - Swift files to analyze: {len(swift_to_analyze)}")
        print(f"  - Header files to analyze: {len(headers_to_analyze)}")
        print(f"  - Files using cache: {len(cached_results)}")

        all_results = list(cached_results)

        # 1단계: Swift 파일들 분석
        if swift_to_analyze:
            if self.lora_swift_path:
                print(f"\nStep 1: Analyzing {len(swift_to_analyze)} Swift files...")
                swift_results = self._analyze_files_with_workers(
                    swift_to_analyze, max_workers, "swift", file_cache, current_files
                )
                all_results.extend(swift_results)
            else:
                print("Warning: No Swift LoRA provided, skipping Swift files")

        # 2단계: 헤더 파일들 분석
        if headers_to_analyze:
            if self.lora_header_path:
                print(f"\nStep 2: Analyzing {len(headers_to_analyze)} header files...")
                header_results = self._analyze_files_with_workers(
                    headers_to_analyze, max_workers, "header", file_cache, current_files
                )
                all_results.extend(header_results)
            else:
                print("Warning: No header LoRA provided, skipping header files")

        # 캐시 저장
        self.save_file_cache(file_cache, cache_path)

        successful_results = [r for r in all_results if 'error' not in r]
        failed_results = [r for r in all_results if 'error' in r]

        return {
            "analysis_results": [r for r in all_results if r not in cached_results],
            "successful_results": successful_results,
            "failed_results": failed_results,
            "cache_used": len(swift_to_analyze) == 0 and len(headers_to_analyze) == 0,
            "file_cache": file_cache
        }

    def _analyze_files_with_workers(self, files_to_analyze: List[str], max_workers: int,
                                    file_type: str, file_cache: dict, current_files: dict) -> List[Dict[str, Any]]:
        """워커를 사용한 파일 분석"""
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            if file_type == "swift":
                future_to_file = {
                    executor.submit(self.generate_analysis_swift, source_file): source_file
                    for source_file in files_to_analyze
                }
            else:  # header
                future_to_file = {
                    executor.submit(self.generate_analysis_header, source_file): source_file
                    for source_file in files_to_analyze
                }

            for future in concurrent.futures.as_completed(future_to_file):
                source_file = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)

                    # 캐시 업데이트
                    relative_path = os.path.relpath(source_file)
                    file_hash = current_files[source_file]

                    if 'error' not in result:
                        file_cache[relative_path] = {
                            "hash": file_hash,
                            "identifiers": result.get("identifiers", [])
                        }
                        print(f"✓ {os.path.basename(source_file)}: {len(result['identifiers'])} exclusion identifiers")
                    else:
                        print(f"✗ {os.path.basename(source_file)}: {result['error']}")

                except Exception as e:
                    print(f"✗ {os.path.basename(source_file)}: Exception - {e}")
                    results.append({
                        "file_path": source_file,
                        "error": str(e),
                        "identifiers": []
                    })

        return results

    def get_cache_file_path(self, output_dir: str) -> str:
        """캐시 파일 경로 반환"""
        return os.path.join(output_dir, "exclude_file_cache.json")

    def analyze_project(self, project_path: str = None, config_path: str = None,
                        output_dir: str = "./output_exclude", max_workers: int = 4,
                        save_individual_files: bool = False, force_full_analysis: bool = False) -> Dict[str, Any]:
        """전체 프로젝트 분석 (Swift + 헤더 파일 지원)"""
        print(f"\n=== ExcludeAnalyzer: 난독화 제외 대상 분석 시작 ===")

        # 프로젝트 경로 결정
        try:
            project_input_path = self.resolve_project_path(project_path, config_path)
        except ValueError as e:
            return {"files_analyzed": 0, "error": str(e)}

        # 모든 소스 파일 찾기
        source_files = self.get_all_source_files(project_input_path)

        if not source_files:
            print("No source files found in project")
            return {"files_analyzed": 0, "results": []}

        os.makedirs(output_dir, exist_ok=True)
        self._debug_mode = save_individual_files

        # 캐시 파일 경로
        cache_path = self.get_cache_file_path(output_dir)

        # 단계별 분석 수행
        if not force_full_analysis:
            analysis_result = self.analyze_files_by_type(source_files, cache_path, max_workers)
        else:
            print("Performing full analysis (cache ignored)...")
            # 강제 전체 분석 시에는 기존 로직 사용하되, 파일 타입별로 처리
            analysis_result = self._force_full_analysis(source_files, cache_path, max_workers)

        successful_results = analysis_result["successful_results"]
        failed_results = analysis_result["failed_results"]

        # 개별 파일 저장 (디버그 모드)
        if save_individual_files and analysis_result.get("analysis_results"):
            print(f"Debug mode: 개별 JSON 파일들도 {output_dir}에 저장됩니다.")
            for result in analysis_result["analysis_results"]:
                if result["file_path"].endswith('.swift'):
                    filename = os.path.basename(result["file_path"]).replace('.swift', '_exclude.json')
                elif result["file_path"].endswith('.h'):
                    filename = os.path.basename(result["file_path"]).replace('.h', '_exclude_header.json')
                else:
                    filename = os.path.basename(result["file_path"]) + '_exclude.json'

                output_path = os.path.join(output_dir, filename)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

        # 식별자 추출 및 정리
        all_symbol_names = []
        for result in successful_results:
            symbol_names = extract_symbol_names_from_exclude_result(result)
            all_symbol_names.extend(symbol_names)

        unique_symbol_names = clean_and_deduplicate_identifiers(all_symbol_names)

        # exclude_id.txt 파일로 저장
        exclude_txt_path = os.path.join(output_dir, "exclude_id.txt")
        save_identifiers_to_txt(unique_symbol_names, exclude_txt_path)

        # 요약 결과
        summary = {
            "mode": "exclude",
            "files_analyzed": len(source_files),
            "successful": len(successful_results),
            "failed": len(failed_results),
            "total_exclude_identifiers_found": len(all_symbol_names),
            "unique_exclude_identifiers": unique_symbol_names,
        }

        # 디버그 모드일 때만 results와 summary 포함
        if save_individual_files:
            summary["results"] = successful_results + failed_results
            summary_path = os.path.join(output_dir, "summary_exclude.json")
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n=== Exclude Analysis Complete ===")
        print(f"Files processed: {len(source_files)}")
        print(f"Successful: {len(successful_results)}")
        print(f"Failed: {len(failed_results)}")
        print(f"Total exclusion identifiers found: {len(all_symbol_names)}")
        print(f"Unique exclusion identifiers: {len(unique_symbol_names)}")
        print(f"Results saved to: {output_dir}")
        print(f"Identifiers saved to: {exclude_txt_path}")

        return summary

    def _force_full_analysis(self, source_files: List[str], cache_path: str, max_workers: int) -> Dict[str, Any]:
        """강제 전체 분석"""
        swift_files, header_files = self.separate_files_by_type(source_files)
        all_results = []
        file_cache = {}

        # Swift 파일들 분석
        if swift_files and self.lora_swift_path:
            print(f"Full analysis: Processing {len(swift_files)} Swift files...")
            swift_results = self._analyze_files_with_workers(
                swift_files, max_workers, "swift", file_cache,
                {f: self.calculate_file_hash(f) for f in swift_files}
            )
            all_results.extend(swift_results)

        # 헤더 파일들 분석
        if header_files and self.lora_header_path:
            print(f"Full analysis: Processing {len(header_files)} header files...")
            header_results = self._analyze_files_with_workers(
                header_files, max_workers, "header", file_cache,
                {f: self.calculate_file_hash(f) for f in header_files}
            )
            all_results.extend(header_results)

        # 캐시 저장
        self.save_file_cache(file_cache, cache_path)

        return {
            "analysis_results": all_results,
            "successful_results": [r for r in all_results if 'error' not in r],
            "failed_results": [r for r in all_results if 'error' in r],
            "cache_used": False,
            "file_cache": file_cache
        }