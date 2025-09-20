#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils.py

공통 유틸리티 함수들
"""

import os
import json
import glob
import re
from typing import Dict, Any, List
from pathlib import Path


def validate_file_exists(file_path: str, description: str = "File") -> None:
    """파일 존재 확인"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{description} not found: {file_path}")


def load_json_config(config_path: str) -> Dict[str, Any]:
    """JSON 설정 파일 로드"""
    validate_file_exists(config_path, "Config file")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file {config_path}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load config from {config_path}: {e}")


def save_json_result(result: Dict[str, Any], output_path: str) -> None:
    """JSON 결과 저장"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise ValueError(f"Failed to save result to {output_path}: {e}")


def get_relative_path(base_path: str, target_path: str) -> str:
    """상대 경로 계산"""
    return os.path.relpath(target_path, base_path)


def ensure_directory(dir_path: str) -> None:
    """디렉토리 생성 (존재하지 않을 경우)"""
    os.makedirs(dir_path, exist_ok=True)


def format_file_size(size_bytes: int) -> str:
    """파일 크기를 읽기 쉬운 형태로 포맷"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_swift_files_count(project_path: str) -> int:
    """프로젝트의 Swift 파일 개수 반환"""
    swift_files = glob.glob(os.path.join(project_path, "**/*.swift"), recursive=True)
    return len(swift_files)


def get_file_info(file_path: str) -> Dict[str, Any]:
    """파일 정보 반환"""
    if not os.path.exists(file_path):
        return {"exists": False}

    stat = os.stat(file_path)
    return {
        "exists": True,
        "size": stat.st_size,
        "size_formatted": format_file_size(stat.st_size),
        "modified": stat.st_mtime,
        "is_file": os.path.isfile(file_path),
        "is_dir": os.path.isdir(file_path)
    }


def create_output_directory(base_dir: str, mode: str, config_name: str = None) -> str:
    """출력 디렉토리 생성"""
    if config_name:
        output_dir = os.path.join(base_dir, f"{mode}_{config_name}")
    else:
        output_dir = os.path.join(base_dir, mode)

    ensure_directory(output_dir)
    return output_dir


def sanitize_filename(filename: str) -> str:
    """파일명에서 특수문자 제거"""
    # 특수문자를 언더스코어로 변경
    sanitized = re.sub(r'[^\w\-_.]', '_', filename)
    # 연속된 언더스코어를 하나로 변경
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized


def merge_identifiers(results: List[Dict[str, Any]]) -> List[str]:
    """여러 결과에서 식별자들을 병합하고 중복 제거"""
    all_identifiers = []
    for result in results:
        if 'identifiers' in result and isinstance(result['identifiers'], list):
            all_identifiers.extend(result['identifiers'])
    return list(set(all_identifiers))


def filter_valid_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """오류가 없는 유효한 결과만 필터링"""
    return [r for r in results if 'error' not in r]


def calculate_success_rate(results: List[Dict[str, Any]]) -> float:
    """성공률 계산"""
    if not results:
        return 0.0

    successful = len(filter_valid_results(results))
    return (successful / len(results)) * 100.0


def generate_summary_stats(results: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
    """결과 요약 통계 생성"""
    valid_results = filter_valid_results(results)
    all_identifiers = merge_identifiers(valid_results)

    return {
        "mode": mode,
        "total_files": len(results),
        "successful": len(valid_results),
        "failed": len(results) - len(valid_results),
        "success_rate": calculate_success_rate(results),
        "total_identifiers_found": sum(len(r.get('identifiers', [])) for r in valid_results),
        "unique_identifiers": all_identifiers,
        "unique_identifiers_count": len(all_identifiers)
    }


# === 새로 추가된 함수들 ===

def extract_function_name(identifier_string: str) -> str:
    """함수명에서 파라미터와 반환타입 제거"""
    if not identifier_string:
        return identifier_string

    # "functionName(param1: Type, param2: Type) -> ReturnType" -> "functionName"
    if '(' in identifier_string:
        return identifier_string.split('(')[0].strip()
    return identifier_string.strip()


def extract_symbol_names_from_exclude_result(result: Dict[str, Any]) -> List[str]:
    """Exclude 결과에서 symbol_name만 추출"""
    symbol_names = []

    if 'identifiers' not in result:
        return symbol_names

    for identifier in result['identifiers']:
        if isinstance(identifier, str):
            # JSON 문자열인 경우 파싱 시도
            try:
                parsed = json.loads(identifier)
                if isinstance(parsed, dict) and 'symbol_name' in parsed:
                    symbol_name = extract_function_name(parsed['symbol_name'])
                    if symbol_name:
                        symbol_names.append(symbol_name)
                else:
                    # JSON이지만 symbol_name이 없는 경우, 문자열 자체를 사용
                    symbol_name = extract_function_name(str(parsed))
                    if symbol_name:
                        symbol_names.append(symbol_name)
            except (json.JSONDecodeError, TypeError):
                # JSON이 아닌 일반 문자열인 경우
                symbol_name = extract_function_name(identifier)
                if symbol_name:
                    symbol_names.append(symbol_name)
        elif isinstance(identifier, dict) and 'symbol_name' in identifier:
            # 이미 파싱된 딕셔너리인 경우
            symbol_name = extract_function_name(identifier['symbol_name'])
            if symbol_name:
                symbol_names.append(symbol_name)
        else:
            # 기타 타입인 경우 문자열로 변환
            symbol_name = extract_function_name(str(identifier))
            if symbol_name:
                symbol_names.append(symbol_name)

    return symbol_names


def extract_sensitive_identifiers(result: Dict[str, Any]) -> List[str]:
    """Sensitive 결과에서 identifiers 추출 및 함수명 정리"""
    identifiers = []

    if 'identifiers' not in result:
        return identifiers

    for identifier in result['identifiers']:
        clean_identifier = extract_function_name(str(identifier))
        if clean_identifier:
            identifiers.append(clean_identifier)

    return identifiers


def save_identifiers_to_txt(identifiers: List[str], output_path: str) -> None:
    """식별자 목록을 텍스트 파일로 저장"""
    # 출력 디렉토리 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for identifier in identifiers:
                f.write(f"{identifier}\n")
    except Exception as e:
        raise ValueError(f"Failed to save identifiers to {output_path}: {e}")


def clean_and_deduplicate_identifiers(identifiers: List[str]) -> List[str]:
    """식별자 목록을 정리하고 중복 제거 후 정렬"""
    cleaned = []
    for identifier in identifiers:
        clean_id = extract_function_name(str(identifier))
        if clean_id:  # 빈 문자열 제외
            cleaned.append(clean_id)

    # 중복 제거 및 정렬
    return sorted(list(set(cleaned)))