#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sensitive_analyzer.py

Sensitive 모드 전용 분석기 - 학습 데이터와 동일한 프롬프트 구조로 수정
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
    """보안 취약점 분석 전용 클래스"""

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

    def create_model_input(self, swift_file_path: str, ast_json: str) -> tuple[str, str]:
        """
        보안 분석용 모델 입력 프롬프트 생성
        학습 데이터와 동일한 구조로 수정

        Args:
            swift_file_path: Swift 파일 경로
            ast_json: AST JSON 데이터

        Returns:
            (system_prompt, user_prompt) 튜플
        """
        try:
            with open(swift_file_path, 'r', encoding='utf-8') as f:
                swift_code = f.read()
        except Exception:
            swift_code = "// Could not read source code"

        # 학습 데이터와 동일한 구조로 system prompt 설정 (빈 문자열)
        system_prompt = ""

        # 학습 데이터와 동일한 instruction 사용
        instruction = "In the following Swift code, find all identifiers related to sensitive logic. Provide the names and reasoning as a JSON object."

        # 학습 데이터와 동일한 input 형식으로 구성
        # create_alpaca_input 함수와 동일한 형식 사용
        try:
            symbol_info_pretty = json.dumps(json.loads(ast_json), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            symbol_info_pretty = ast_json

        input_content = f"""**Swift Source Code:**
```swift
{swift_code}
```

**AST Symbol Information (JSON):**
```
{symbol_info_pretty}
```"""

        # 전체 프롬프트를 user_prompt로 구성
        user_prompt = f"{instruction}\n\n{input_content}"

        return system_prompt, user_prompt

    def extract_json_from_output(self, text: str) -> tuple[str, List[str]]:
        """
        모델 출력에서 JSON 추출 및 파싱
        Sensitive 모드에 맞게 수정 - reasoning과 identifiers 구조 처리
        """
        if not text:
            return "", []

        try:
            # JSON 블록 찾기
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

        # reasoning 추출
        reasoning_match = re.search(r'["\']reasoning["\']\s*:\s*["\'](.*?)["\']', text, re.DOTALL)
        if reasoning_match:
            reasoning_str = reasoning_match.group(1).strip()

        # identifiers 추출
        identifiers_match = re.search(r'["\']identifiers["\']\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if identifiers_match:
            content_str = identifiers_match.group(1).strip()
            if content_str:
                items = content_str.split(',')
                identifiers_list = [item.strip().strip('"\' ') for item in items if item.strip()]

        return reasoning_str, identifiers_list

    def analyze_project(self, project_path: str = None, config_path: str = None,
                        output_dir: str = "./output_sensitive", max_workers: int = 4,
                        save_individual_files: bool = False) -> Dict[str, Any]:
        """
        전체 프로젝트 보안 분석

        Args:
            project_path: Swift 프로젝트 디렉토리 경로 (우선순위 높음)
            config_path: swingft_config.json 경로 (선택사항)
            output_dir: 출력 디렉토리
            max_workers: 병렬 처리 워커 수
            save_individual_files: 개별 JSON 파일 저장 여부

        Returns:
            분석 결과 요약
        """
        print(f"\n=== SensitiveAnalyzer: 보안 취약점 분석 시작 ===")

        # 프로젝트 경로 결정 (CLI 인자 우선, 그 다음 config 파일)
        project_input_path = self.resolve_project_path(project_path, config_path)

        # config 파일에서 target_identifiers 읽기 (있는 경우에만)
        target_identifiers = []
        if config_path:
            config = self.load_swingft_config(config_path)
            target_identifiers = config.get('exclude', {}).get('obfuscation', [])

        # target_identifiers가 있으면 특정 파일만, 없으면 모든 Swift 파일 분석
        if target_identifiers:
            print(f"Target identifiers from config: {target_identifiers}")
            swift_files = self.find_swift_files_with_identifiers(project_input_path, target_identifiers)
            if not swift_files:
                print("No Swift files found with target identifiers")
                return {"files_analyzed": 0, "results": []}
        else:
            print("No target identifiers specified, analyzing all Swift files")
            swift_files = self.get_all_swift_files(project_input_path)
            if not swift_files:
                print("No Swift files found in project")
                return {"files_analyzed": 0, "results": []}

        os.makedirs(output_dir, exist_ok=True)

        # 개별 파일 저장 모드 알림
        if save_individual_files:
            print(f"Debug mode: 개별 JSON 파일들도 {output_dir}에 저장됩니다.")

        # 병렬 처리 시작 전에 모델을 메인 메모리에 미리 로드합니다.
        self.preload_model()

        print(f"\nStarting security analysis with {max_workers} workers...")
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.generate_analysis, swift_file): swift_file
                for swift_file in swift_files
            }

            for future in concurrent.futures.as_completed(future_to_file):
                swift_file = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)

                    # 개별 JSON 파일 저장 (조건부)
                    if save_individual_files:
                        filename = os.path.basename(swift_file).replace('.swift', '_sensitive.json')
                        output_path = os.path.join(output_dir, filename)

                        with open(output_path, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)

                    if 'error' in result:
                        print(f"✗ {os.path.basename(swift_file)}: {result['error']}")
                    else:
                        print(f"✓ {os.path.basename(swift_file)}: {len(result['identifiers'])} sensitive identifiers")

                except Exception as e:
                    print(f"✗ {os.path.basename(swift_file)}: Exception - {e}")
                    results.append({
                        "file_path": swift_file,
                        "error": str(e),
                        "reasoning": "",
                        "identifiers": []
                    })

        successful_results = [r for r in results if 'error' not in r]
        failed_results = [r for r in results if 'error' in r]

        # identifiers 추출 및 함수명 정리
        all_sensitive_identifiers = []
        for result in successful_results:
            identifiers = extract_sensitive_identifiers(result)
            all_sensitive_identifiers.extend(identifiers)

        # 중복 제거하고 정렬
        unique_sensitive_identifiers = clean_and_deduplicate_identifiers(all_sensitive_identifiers)

        # sensitive_id.txt 파일로 저장 (항상 생성)
        sensitive_txt_path = os.path.join(output_dir, "sensitive_id.txt")
        save_identifiers_to_txt(unique_sensitive_identifiers, sensitive_txt_path)

        # 기존 통계 계산 (호환성 유지)
        total_sensitive_identifiers = len(all_sensitive_identifiers)

        # 요약 결과 (save_individual_files가 False면 results 제외)
        summary = {
            "mode": "sensitive",
            "files_analyzed": len(swift_files),
            "successful": len(successful_results),
            "failed": len(failed_results),
            "total_sensitive_identifiers_found": total_sensitive_identifiers,
            "unique_sensitive_identifiers": unique_sensitive_identifiers,
        }

        # 개별 파일 저장 모드일 때만 results 포함
        if save_individual_files:
            summary["results"] = results

        # summary 저장 (항상 생성)
        summary_path = os.path.join(output_dir, "summary_sensitive.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n=== Security Analysis Complete ===")
        print(f"Files processed: {len(swift_files)}")
        print(f"Successful: {len(successful_results)}")
        print(f"Failed: {len(failed_results)}")
        print(f"Total sensitive identifiers found: {total_sensitive_identifiers}")
        print(f"Unique sensitive identifiers: {len(unique_sensitive_identifiers)}")
        print(f"Results saved to: {output_dir}")
        print(f"Identifiers saved to: {sensitive_txt_path}")

        if save_individual_files:
            print(f"개별 JSON 파일들도 저장되었습니다.")

        return summary