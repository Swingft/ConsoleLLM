#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sensitive_analyzer.py

Sensitive 모드 전용 분석기
- exclude.obfuscation의 식별자들을 포함한 Swift 파일들만 분석
- 보안 취약점 식별에 특화
"""

import os
import json
from typing import List, Dict, Any
from pathlib import Path
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from shared_utils import BaseAnalyzer


class SensitiveAnalyzer(BaseAnalyzer):
    """보안 취약점 분석 전용 클래스"""

    def __init__(self, base_model_path: str, lora_path: str = None,
                 n_ctx: int = 32768, n_gpu_layers: int = 0, n_threads: int = None):
        super().__init__(base_model_path, lora_path, n_ctx, n_gpu_layers, n_threads)
        # Sensitive용 AST 분석기 경로
        self.ast_analyzer_path = "./SwiftASTAnalyzer_sensitive/.build/release/SwiftASTAnalyzer"
        print(f"SensitiveAnalyzer 초기화 - AST 분석기: {self.ast_analyzer_path}")

    def create_model_input(self, swift_file_path: str, ast_json: str) -> tuple[str, str]:
        """
        보안 분석용 모델 입력 프롬프트 생성

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

        system_prompt = """You are an expert security code auditor.
Your task is to identify all sensitive identifiers in the provided Swift code and explain your reasoning.
Analyze both the source code and its corresponding AST symbol information.

Focus on identifying:
- Security-sensitive functions (authentication, encryption, data storage)
- API keys, tokens, passwords, or sensitive data variables
- Network communication functions that handle sensitive data
- Database operations with sensitive information
- Keychain operations
- Biometric authentication functions
- Any identifiers that could expose security vulnerabilities

Based on your analysis, provide your response as a JSON object with two keys: "reasoning" and "identifiers".

"reasoning": A step-by-step explanation of why the identified identifiers are considered sensitive. For secure code, explain why it is safe.
"identifiers": A JSON list of strings containing only the base name of each sensitive identifier. For secure code, this should be an empty list [].

Your response must be ONLY the JSON object."""

        user_prompt = f"""**Swift Source Code:**
```swift
{swift_code}
```

**AST Symbol Information (JSON):**
```json
{ast_json}
```

Task: Perform a security audit on the above Swift code and return ONLY a JSON object with 'reasoning' and 'identifiers' keys. Focus on finding security-sensitive identifiers."""

        return system_prompt, user_prompt

    def generate_analysis(self, swift_file_path: str) -> Dict[str, Any]:
        """
        단일 Swift 파일에 대한 보안 분석 수행

        Args:
            swift_file_path: Swift 파일 경로

        Returns:
            분석 결과 딕셔너리
        """
        # AST 분석
        ast_json = self.run_swift_analyzer(swift_file_path, self.ast_analyzer_path)
        if not ast_json:
            return {
                "file_path": swift_file_path,
                "error": "AST analysis failed",
                "reasoning": "",
                "identifiers": []
            }

        # 모델 입력 생성
        system_prompt, user_prompt = self.create_model_input(swift_file_path, ast_json)

        # 모델 추론
        try:
            model = self._load_model()

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = model.create_chat_completion(
                messages=messages,
                temperature=0.1,  # 보안 분석에서는 더 낮은 temperature 사용
                top_p=0.9,
                max_tokens=4096,
            )

            raw_output = response['choices'][0]['message']['content']

            # JSON 파싱
            reasoning, identifiers = self.extract_json_from_output(raw_output)

            return {
                "file_path": swift_file_path,
                "reasoning": reasoning,
                "identifiers": identifiers,
                "raw_output": raw_output,
                "ast_json": ast_json
            }

        except Exception as e:
            return {
                "file_path": swift_file_path,
                "error": f"Model inference failed: {e}",
                "reasoning": "",
                "identifiers": []
            }

    def analyze_project(self, config_path: str, output_dir: str = "./output_sensitive",
                        max_workers: int = 4) -> Dict[str, Any]:
        """
        전체 프로젝트 보안 분석

        Args:
            config_path: swingft_config.json 경로
            output_dir: 출력 디렉토리
            max_workers: 병렬 처리 워커 수

        Returns:
            분석 결과 요약
        """
        print(f"\n=== SensitiveAnalyzer: 보안 취약점 분석 시작 ===")

        # 설정 로드
        config = self.load_swingft_config(config_path)
        project_input_path = config['project']['input']

        # exclude.obfuscation의 식별자들을 분석 대상으로 설정
        target_identifiers = config.get('exclude', {}).get('obfuscation', [])

        if not target_identifiers:
            print("No target identifiers found in exclude.obfuscation")
            return {"files_analyzed": 0, "results": []}

        print(f"Target identifiers from exclude.obfuscation: {target_identifiers}")

        # 식별자를 포함한 Swift 파일 찾기
        swift_files = self.find_swift_files_with_identifiers(project_input_path, target_identifiers)

        if not swift_files:
            print("No Swift files found with target identifiers")
            return {"files_analyzed": 0, "results": []}

        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)

        # 병렬 처리로 분석 실행
        print(f"\nStarting security analysis with {max_workers} workers...")
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 작업 제출
            future_to_file = {
                executor.submit(self.generate_analysis, swift_file): swift_file
                for swift_file in swift_files
            }

            # 결과 수집
            for future in concurrent.futures.as_completed(future_to_file):
                swift_file = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)

                    # 개별 결과 파일 저장
                    filename = os.path.basename(swift_file).replace('.swift', '_sensitive.json')
                    output_path = os.path.join(output_dir, filename)

                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)

                    # 진행 상황 출력
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

        # 요약 통계
        successful_results = [r for r in results if 'error' not in r]
        failed_results = [r for r in results if 'error' in r]

        total_sensitive_identifiers = sum(len(r['identifiers']) for r in successful_results)

        # 모든 식별된 보안 취약점 수집
        all_sensitive_identifiers = []
        for result in successful_results:
            all_sensitive_identifiers.extend(result['identifiers'])
        unique_sensitive_identifiers = list(set(all_sensitive_identifiers))

        summary = {
            "mode": "sensitive",
            "files_analyzed": len(swift_files),
            "successful": len(successful_results),
            "failed": len(failed_results),
            "total_sensitive_identifiers_found": total_sensitive_identifiers,
            "unique_sensitive_identifiers": unique_sensitive_identifiers,
            "results": results
        }

        # 요약 파일 저장
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

        return summary