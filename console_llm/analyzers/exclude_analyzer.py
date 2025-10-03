#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
exclude_analyzer.py

Exclude 모드 전용 분석기 - 원래 구조 그대로, Header 지원만 추가
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import glob

from ..core.base_analyzer import BaseAnalyzer
from ..core.model_loader import OptimizedModelLoader
from ..core.utils import (
    extract_symbol_names_from_exclude_result,
    save_identifiers_to_txt,
    clean_and_deduplicate_identifiers
)


class ExcludeAnalyzer(BaseAnalyzer):
    """난독화 제외 분석 전용 클래스 - 원래 구조 유지"""

    def __init__(self, base_model_path: str,
                 lora_header_path: str = None, lora_swift_path: str = None,
                 model_loader: Optional[OptimizedModelLoader] = None,
                 n_ctx: int = 4096, n_gpu_layers: int = 0, n_threads: int = None,
                 enable_4bit_kv_cache: bool = True):

        super().__init__(base_model_path, None, model_loader,
                         n_ctx, n_gpu_layers, n_threads, enable_4bit_kv_cache)

        self.lora_header_path = lora_header_path
        self.lora_swift_path = lora_swift_path

        current_dir = Path(__file__).parent.parent
        self.ast_analyzer_path = current_dir / "ast_analyzers" / "exclude" / "SwiftASTAnalyzer"

        print(f"ExcludeAnalyzer 초기화")
        print(f"  - Header LoRA: {lora_header_path}")
        print(f"  - Swift LoRA: {lora_swift_path}")
        print(f"  - AST 분석기: {self.ast_analyzer_path}")

    def preload_model(self):
        """중복 로딩 방지를 위해 preload 건너뛰기"""
        print("Skipping preload to avoid duplicate model loading")

    def split_header_file(self, file_path: str, threshold_kb: int = 25) -> List[str]:
        """헤더 파일을 간단하게 분할"""
        threshold_bytes = threshold_kb * 1024
        content = None
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise ValueError(f"Cannot read file: {file_path}")

        if len(content.encode('utf-8')) <= threshold_bytes:
            return [content]

        lines = content.splitlines(keepends=True)
        parts = []
        current_part = []
        current_size = 0

        for line in lines:
            line_size = len(line.encode('utf-8'))
            if current_size + line_size > threshold_bytes and current_part:
                parts.append("".join(current_part))
                current_part = [line]
                current_size = line_size
            else:
                current_part.append(line)
                current_size += line_size

        if current_part:
            parts.append("".join(current_part))

        return parts if parts else [content]

    def create_model_input(self, file_path: str, ast_json: str = None, file_type: str = "swift") -> tuple[str, str]:
        """모델 입력 프롬프트 생성 - 파일 타입에 따라 다르게 처리"""
        if file_type == "header":
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    header_content = f.read()
            except Exception as e:
                print(f"Warning: Could not read header file {file_path}: {e}")
                header_content = "// Could not read header file"

            system_prompt = ""
            instruction = "Identify which Objective-C identifiers should be excluded from obfuscation and provide detailed reasoning."

            input_content = f"""**Objective-C Header File:**```objc{header_content}```Analyze the public API declarations and identify all identifiers that must be excluded from obfuscation."""
            user_prompt = f"{instruction}\n\n{input_content}"
            return system_prompt, user_prompt
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    swift_code = f.read()
            except Exception:
                swift_code = "// Could not read source code"

            try:
                symbol_info_dict = json.loads(ast_json) if ast_json else {}
            except json.JSONDecodeError:
                symbol_info_dict = {}

            system_prompt = ""
            instruction = "Identify which identifiers in the Swift code should be excluded from obfuscation based on the provided AST analysis, and provide detailed reasoning."
            input_data = {
                "swift_code": swift_code,
                "symbol_info": symbol_info_dict
            }
            user_prompt = f"{instruction}\n\nInput: {json.dumps(input_data, ensure_ascii=False, indent=2)}"
            return system_prompt, user_prompt

    def generate_analysis(self, file_path: str, file_type: str = "swift") -> Dict[str, Any]:
        """단일 파일에 대한 분석 수행 - 파일 타입에 따라 다르게 처리"""
        if file_type == "header":
            ast_json = None
            lora_path = self.lora_header_path
            max_tokens = 4096
        else:
            ast_json = self.run_swift_analyzer(file_path)
            if not ast_json:
                return {
                    "file_path": file_path,
                    "error": "AST analysis failed",
                    "reasoning": "",
                    "identifiers": []
                }
            lora_path = self.lora_swift_path
            max_tokens = 4096

        if not lora_path:
            return {
                "file_path": file_path,
                "error": f"LoRA path not provided for {file_type} files",
                "reasoning": "",
                "identifiers": []
            }

        system_prompt, user_prompt = self.create_model_input(file_path, ast_json, file_type)

        try:
            model = self.model_loader.load_model(
                base_model_path=self.base_model_path,
                lora_path=lora_path,
                **self.model_config
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = model.create_chat_completion(
                messages=messages,
                temperature=0.1,
                top_p=0.9,
                max_tokens=max_tokens,
                stop=None,
            )

            raw_output = response['choices'][0]['message']['content']

            if not raw_output or len(raw_output.strip()) < 10:
                print(f"Warning: Short or empty output for {file_path}")
                print(f"Output length: {len(raw_output) if raw_output else 0}")

            reasoning, identifiers = self.extract_json_from_output(raw_output)

            result = {
                "file_path": file_path,
                "file_type": file_type,
                "reasoning": reasoning,
                "identifiers": identifiers,
                "raw_output": raw_output
            }

            if ast_json:
                result["ast_json"] = ast_json

            return result

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Error details for {file_path}:")
            print(error_detail)

            return {
                "file_path": file_path,
                "file_type": file_type,
                "error": f"Model inference failed: {e}",
                "error_detail": error_detail,
                "reasoning": "",
                "identifiers": []
            }

    def generate_header_analysis(self, header_file_path: str) -> List[Dict[str, Any]]:
        """헤더 파일 분석 (분할 지원)"""
        try:
            parts = self.split_header_file(header_file_path)
            results = []

            for part_idx, part_content in enumerate(parts):
                temp_file = f"{header_file_path}_temp_part{part_idx}"
                try:
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write(part_content)

                    result = self.generate_analysis(temp_file, "header")

                    if len(parts) > 1:
                        result["file_path"] = f"{header_file_path}_part{part_idx + 1}"
                        result["part_index"] = part_idx + 1
                        result["total_parts"] = len(parts)
                    else:
                        result["file_path"] = header_file_path

                    results.append(result)

                finally:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

            return results

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Error in generate_header_analysis for {header_file_path}:")
            print(error_detail)

            return [{
                "file_path": header_file_path,
                "file_type": "header",
                "error": f"Header processing failed: {e}",
                "error_detail": error_detail,
                "reasoning": "",
                "identifiers": []
            }]

    def extract_json_from_output(self, text: str) -> tuple[str, List[str]]:
        """모델 출력에서 JSON을 추출하고 파싱하는 함수"""
        if not text:
            return "", []

        def _parse_json_data(data: Dict) -> (Optional[str], Optional[List[str]]):
            if not isinstance(data, dict):
                return None, None

            reasoning = data.get("reasoning", "")
            identifiers = []

            exclusions = data.get("exclusions", [])
            if isinstance(exclusions, list):
                for item in exclusions:
                    if isinstance(item, dict) and "identifier" in item:
                        identifiers.append(item["identifier"])

            if not identifiers:
                found_ids = data.get("identifiers", [])
                if isinstance(found_ids, list):
                    identifiers.extend(str(i) for i in found_ids if i)

            return reasoning, identifiers

        def _parse_with_regex(content: str) -> (str, List[str]):
            reasoning_str = ""
            reasoning_match = re.search(r'["\']reasoning["\']\s*:\s*["\'](.*?)["\']', content, re.DOTALL)
            if reasoning_match:
                reasoning_str = reasoning_match.group(1).strip().replace('\\n', '\n')

            ids = []
            exclusions_match = re.search(r'["\']exclusions["\']\s*:\s*\[(.*?)\]', content, re.DOTALL)
            if exclusions_match:
                ids.extend(re.findall(r'["\']identifier["\']\s*:\s*["\']([^"\']+)["\']', exclusions_match.group(1)))

            identifiers_match = re.search(r'["\']identifiers["\']\s*:\s*\[(.*?)\]', content, re.DOTALL)
            if identifiers_match:
                ids.extend(re.findall(r'["\']([^"\']+)["\']', identifiers_match.group(1)))

            return reasoning_str, ids

        try:
            outer_data = json.loads(text)

            # 리스트인 경우 처리 추가
            if isinstance(outer_data, list):
                # 리스트의 각 항목에서 identifier 추출
                identifiers = []
                for item in outer_data:
                    if isinstance(item, dict):
                        if "identifier" in item:
                            identifiers.append(item["identifier"])
                        elif "name" in item:
                            identifiers.append(item["name"])
                    elif isinstance(item, str):
                        identifiers.append(item)
                return "", sorted(list(set(identifiers)))

            # 딕셔너리인 경우 기존 로직
            if isinstance(outer_data, dict):
                raw_output_content = outer_data.get("raw_output")
                if isinstance(raw_output_content, str) and raw_output_content.strip().startswith('{'):
                    try:
                        inner_data = json.loads(raw_output_content)
                        reasoning, identifiers = _parse_json_data(inner_data)
                        if reasoning is not None and identifiers is not None:
                            return reasoning, sorted(list(set(identifiers)))
                    except json.JSONDecodeError:
                        reasoning, identifiers = _parse_with_regex(raw_output_content)
                        return reasoning, sorted(list(set(identifiers)))

                reasoning, identifiers = _parse_json_data(outer_data)
                if reasoning is not None and identifiers is not None:
                    return reasoning, sorted(list(set(identifiers)))

        except json.JSONDecodeError:
            reasoning, identifiers = _parse_with_regex(text)
            return reasoning, sorted(list(set(identifiers)))

        return "", []

    def get_all_swift_files(self, project_path: str) -> List[str]:
        """프로젝트의 모든 Swift 파일들을 찾음"""
        swift_files = glob.glob(os.path.join(project_path, "**/*.swift"), recursive=True)
        print(f"Found {len(swift_files)} Swift files in project")
        return swift_files

    def get_all_header_files(self, project_path: str) -> List[str]:
        """프로젝트의 모든 Header 파일들을 찾음"""
        header_files = glob.glob(os.path.join(project_path, "**/*.h"), recursive=True)
        print(f"Found {len(header_files)} Header files in project")
        return header_files

    def analyze_project(self, project_path: str = None, config_path: str = None,
                        output_dir: str = "./output_exclude", max_workers: int = 4,
                        save_individual_files: bool = False,
                        file_types: List[str] = None) -> Dict[str, Any]:
        """전체 프로젝트 난독화 제외 분석"""
        if file_types is None:
            file_types = ['both']

        print(f"\n=== ExcludeAnalyzer: 난독화 제외 대상 분석 시작 ===")
        print(f"File types: {file_types}")

        project_input_path = self.resolve_project_path(project_path, config_path)

        files_to_process = []

        if 'both' in file_types or 'header' in file_types:
            if self.lora_header_path:
                header_files = self.get_all_header_files(project_input_path)
                files_to_process.extend([('header', f) for f in header_files])
            else:
                print("Warning: Header LoRA path not provided, skipping header files")

        if 'both' in file_types or 'swift' in file_types:
            if self.lora_swift_path:
                swift_files = self.get_all_swift_files(project_input_path)
                files_to_process.extend([('swift', f) for f in swift_files])
            else:
                print("Warning: Swift LoRA path not provided, skipping Swift files")

        if not files_to_process:
            print("No files to process")
            return {"files_analyzed": 0, "results": []}

        os.makedirs(output_dir, exist_ok=True)
        if save_individual_files:
            print(f"Debug mode: 개별 JSON 파일들도 {output_dir}에 저장됩니다.")

        print(f"\nStarting obfuscation exclusion analysis with {max_workers} workers...")

        all_results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {}

            for file_type, file_path in files_to_process:
                if file_type == 'header':
                    future = executor.submit(self.generate_header_analysis, file_path)
                else:
                    future = executor.submit(self.generate_analysis, file_path, 'swift')
                future_to_file[future] = (file_type, file_path)

            for future in concurrent.futures.as_completed(future_to_file):
                file_type, file_path = future_to_file[future]
                try:
                    result = future.result()

                    if isinstance(result, list):
                        all_results.extend(result)

                        if save_individual_files:
                            for part_result in result:
                                filename = os.path.basename(part_result['file_path']).replace('.h',
                                                                                              '_exclude.json').replace(
                                    '.swift', '_exclude.json')
                                output_path = os.path.join(output_dir, filename)
                                with open(output_path, 'w', encoding='utf-8') as f:
                                    json.dump(part_result, f, ensure_ascii=False, indent=2)

                        successful_parts = [r for r in result if 'error' not in r]
                        failed_parts = [r for r in result if 'error' in r]

                        if failed_parts:
                            print(
                                f"✗ {os.path.basename(file_path)}: {len(failed_parts)}/{len(result)} parts failed")
                            for failed in failed_parts:
                                if 'error_detail' in failed:
                                    print(f"  Error detail: {failed['error']}")
                        else:
                            total_identifiers = sum(len(r['identifiers']) for r in successful_parts)
                            print(
                                f"✓ {os.path.basename(file_path)}: {len(result)} parts, {total_identifiers} identifiers")

                    else:
                        all_results.append(result)

                        if save_individual_files:
                            filename = os.path.basename(file_path).replace('.swift', '_exclude.json').replace('.h',
                                                                                                              '_exclude.json')
                            output_path = os.path.join(output_dir, filename)
                            with open(output_path, 'w', encoding='utf-8') as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)

                        if 'error' in result:
                            print(f"✗ {os.path.basename(file_path)}: {result['error']}")
                            if 'error_detail' in result:
                                print(f"  Error detail: {result.get('error_detail', '')[:200]}...")
                        else:
                            print(
                                f"✓ {os.path.basename(file_path)}: {len(result['identifiers'])} exclusion identifiers")

                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"✗ {os.path.basename(file_path)}: Exception - {e}")
                    print(f"  Traceback: {error_detail[:200]}...")

                    error_result = {
                        "file_path": file_path,
                        "file_type": file_type,
                        "error": str(e),
                        "error_detail": error_detail,
                        "reasoning": "",
                        "identifiers": []
                    }
                    all_results.append(error_result)

        successful_results = [r for r in all_results if 'error' not in r]
        failed_results = [r for r in all_results if 'error' in r]

        all_symbol_names = []
        for result in successful_results:
            symbol_names = extract_symbol_names_from_exclude_result(result)
            all_symbol_names.extend(symbol_names)

        unique_symbol_names = clean_and_deduplicate_identifiers(all_symbol_names)
        exclude_txt_path = os.path.join(output_dir, "exclude_id.txt")
        save_identifiers_to_txt(unique_symbol_names, exclude_txt_path)

        header_results = [r for r in all_results if r.get('file_type') == 'header']
        swift_results = [r for r in all_results if r.get('file_type') == 'swift']

        summary = {
            "mode": "exclude",
            "file_types_processed": file_types,
            "total_files_analyzed": len(files_to_process),
            "total_results": len(all_results),
            "successful": len(successful_results),
            "failed": len(failed_results),
            "header_files_processed": len([f for t, f in files_to_process if t == 'header']),
            "header_results": len(header_results),
            "swift_files_processed": len([f for t, f in files_to_process if t == 'swift']),
            "swift_results": len(swift_results),
            "total_exclude_identifiers_found": len(all_symbol_names),
            "unique_exclude_identifiers": unique_symbol_names,
        }

        if save_individual_files:
            summary["results"] = all_results

        summary_path = os.path.join(output_dir, "summary_exclude.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n=== Exclude Analysis Complete ===")
        print(f"Files processed: {len(files_to_process)}")
        print(f"Results generated: {len(all_results)}")
        print(f"  - Header results: {len(header_results)}")
        print(f"  - Swift results: {len(swift_results)}")
        print(f"Successful: {len(successful_results)}")
        print(f"Failed: {len(failed_results)}")
        print(f"Total exclusion identifiers found: {len(all_symbol_names)}")
        print(f"Unique exclusion identifiers: {len(unique_symbol_names)}")
        print(f"Results saved to: {output_dir}")
        print(f"Identifiers saved to: {exclude_txt_path}")

        if save_individual_files:
            print(f"개별 JSON 파일들도 저장되었습니다.")

        return summary
