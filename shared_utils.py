#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
shared_utils.py

ConsoleLLM 공통 유틸리티 함수들
"""

import json
import os
import subprocess
import threading
from typing import List, Dict, Optional, Tuple, Any
import re
import glob

try:
    from llama_cpp import Llama
except ImportError:
    print("Error: llama-cpp-python is not installed. Please run: pip install llama-cpp-python")
    import sys

    sys.exit(1)


class BaseAnalyzer:
    """공통 분석기 베이스 클래스"""

    def __init__(self, base_model_path: str, lora_path: str = None,
                 n_ctx: int = 32768, n_gpu_layers: int = 0, n_threads: int = None):
        """
        베이스 분석기 초기화

        Args:
            base_model_path: base_model.gguf 경로
            lora_path: LoRA 어댑터 경로 (선택사항)
            n_ctx: 컨텍스트 크기
            n_gpu_layers: GPU 레이어 수
            n_threads: CPU 스레드 수
        """
        self.base_model_path = base_model_path
        self.lora_path = lora_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads

        # 모델 인스턴스 (lazy loading)
        self.model = None
        self.model_lock = threading.Lock()

        print(f"BaseAnalyzer 초기화 완료")
        print(f"  - Base model: {base_model_path}")
        print(f"  - LoRA adapter: {lora_path}")

    def _load_model(self) -> Llama:
        """모델 로딩 (lazy loading with thread safety)"""
        with self.model_lock:
            if self.model is not None:
                return self.model

            print(f"Loading model...")

            if self.lora_path:
                self.model = Llama(
                    model_path=self.base_model_path,
                    lora_path=self.lora_path,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    n_threads=self.n_threads,
                    verbose=False
                )
            else:
                self.model = Llama(
                    model_path=self.base_model_path,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    n_threads=self.n_threads,
                    verbose=False
                )

            print(f"Model loaded successfully")
            return self.model

    def load_swingft_config(self, config_path: str) -> Dict[str, Any]:
        """swingft_config.json 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            raise ValueError(f"Failed to load config from {config_path}: {e}")

    def run_swift_analyzer(self, swift_file_path: str, analyzer_path: str) -> Optional[str]:
        """
        SwiftASTAnalyzer를 실행하여 AST 정보 추출

        Args:
            swift_file_path: Swift 파일 경로
            analyzer_path: AST 분석기 실행 파일 경로
        """
        try:
            command = [analyzer_path, swift_file_path]
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=30
            )

            if process.returncode != 0:
                print(f"Warning: AST analyzer failed for {swift_file_path}")
                return None

            output = process.stdout.strip()
            if not output:
                return None

            # JSON 부분 추출
            json_start = output.find('{')
            if json_start == -1:
                return None

            json_part = output[json_start:]

            # JSON 유효성 검사
            try:
                json.loads(json_part)
                return json_part
            except json.JSONDecodeError:
                return None

        except Exception as e:
            print(f"Warning: AST analysis failed for {swift_file_path}: {e}")
            return None

    def extract_json_from_output(self, text: str) -> Tuple[str, List[str]]:
        """모델 출력에서 JSON 추출 및 파싱"""
        if not text:
            return "", []

        # 완전한 JSON 블록 파싱 시도
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

        # 정규식 fallback
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

    def find_swift_files_with_identifiers(self, project_path: str, identifiers: List[str]) -> List[str]:
        """프로젝트에서 특정 식별자를 포함한 Swift 파일들을 찾음"""
        matching_files = []
        swift_files = glob.glob(os.path.join(project_path, "**/*.swift"), recursive=True)

        print(f"Scanning {len(swift_files)} Swift files for identifiers: {identifiers}")

        for swift_file in swift_files:
            try:
                with open(swift_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 각 식별자가 파일에 포함되어 있는지 확인
                for identifier in identifiers:
                    # 와일드카드 처리
                    if identifier.endswith('*'):
                        prefix = identifier[:-1]
                        if prefix in content:
                            matching_files.append(swift_file)
                            break
                    elif identifier.startswith('**'):
                        # **Wildcard는 모든 파일 포함
                        matching_files.append(swift_file)
                        break
                    elif identifier in content:
                        matching_files.append(swift_file)
                        break

            except (UnicodeDecodeError, OSError) as e:
                print(f"Warning: Could not read {swift_file}: {e}")
                continue

        unique_files = list(set(matching_files))
        print(f"Found {len(unique_files)} files containing the specified identifiers")
        return unique_files

    def get_all_swift_files(self, project_path: str) -> List[str]:
        """프로젝트의 모든 Swift 파일들을 찾음"""
        swift_files = glob.glob(os.path.join(project_path, "**/*.swift"), recursive=True)
        print(f"Found {len(swift_files)} Swift files in project")
        return swift_files