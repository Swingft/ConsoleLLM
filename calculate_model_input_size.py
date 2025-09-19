import os
import json
import subprocess
import glob
from pathlib import Path
from typing import List, Tuple, Dict, Any

# --- 설정 (사용자 환경에 맞게 경로를 수정하세요) ---

# 1. swingft 설정 파일 경로
CONFIG_PATH = './swingft_config.json'

# 2. 분석 결과 (JSON 파일)가 저장된 디렉토리
OUTPUT_DIR = './output'

# 3. SwiftASTAnalyzer 실행 파일 경로
AST_ANALYZER_PATH = './console_llm/ast_analyzers/sensitive/SwiftASTAnalyzer'


# ----------------------------------------------------

def load_project_path_from_config(config_path: str) -> str:
    """설정 파일에서 프로젝트 소스 경로('project.input')만 읽어옵니다."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    if 'project' not in config or 'input' not in config['project']:
        raise KeyError("설정 파일에 'project.input' 경로가 없습니다.")

    return config['project']['input']


def find_source_file(project_root: str, base_filename: str) -> str | None:
    """프로젝트 루트에서 주어진 이름의 파일을 재귀적으로 찾습니다."""
    try:
        # rglob을 사용해 모든 하위 디렉토리에서 파일을 효율적으로 검색
        matches = list(Path(project_root).rglob(base_filename))
        if matches:
            return str(matches[0])  # 첫 번째 일치하는 파일 반환
    except Exception as e:
        print(f"파일 검색 중 오류 발생: {e}")
        return None
    return None


def run_ast_analyzer(swift_file_path: str) -> str | None:
    """SwiftASTAnalyzer를 실행하고 결과를 문자열로 반환합니다."""
    if not os.path.exists(AST_ANALYZER_PATH):
        raise FileNotFoundError(f"AST 분석기를 찾을 수 없습니다: {AST_ANALYZER_PATH}")

    command = f'"{AST_ANALYZER_PATH}" "{swift_file_path}"'
    try:
        process = subprocess.run(
            command, shell=True, capture_output=True, text=True, encoding='utf-8', timeout=60
        )
        return process.stdout.strip() if process.returncode == 0 else None
    except Exception as e:
        print(f"AST 분석기 실행 중 오류 발생: {e}")
        return None


def get_full_prompt(swift_code: str, ast_json: str) -> str:
    """실제 모델에 입력될 전체 프롬프트 문자열을 생성합니다."""
    # 민감도 분석용 시스템 프롬프트 (내용은 실제 프롬프트에 맞춰야 합니다)
    system_prompt = """You are an expert security code auditor.
Your task is to identify all sensitive identifiers in the provided Swift code and explain your reasoning.
Analyze both the source code and its corresponding AST symbol information.
Based on your analysis, provide your response as a JSON object with two keys: "reasoning" and "identifiers".
Your response must be ONLY the JSON object."""

    # 사용자 프롬프트 템플릿
    user_prompt = f"""**Swift Source Code:**swift
{swift_code}


**AST Symbol Information (JSON):**json
{ast_json}


Task: Perform a security audit on the above Swift code and return ONLY a JSON object with 'reasoning' and 'identifiers' keys. Focus on finding security-sensitive identifiers."""

    return system_prompt + user_prompt


def calculate_size_from_output_files():
    """메인 로직: output 디렉토리 기반으로 크기 계산"""
    print("모델 입력 크기 분석을 시작합니다...")

    try:
        project_source_dir = load_project_path_from_config(CONFIG_PATH)
    except (FileNotFoundError, KeyError) as e:
        print(f"❗️오류: {e}")
        return

    # output 디렉토리에서 *_sensitive.json 파일 목록 가져오기
    output_files = glob.glob(os.path.join(OUTPUT_DIR, "*_sensitive.json"))

    # summary 파일은 분석 대상에서 제외
    analysis_targets = [f for f in output_files if not os.path.basename(f).startswith('summary')]

    if not analysis_targets:
        print(f"❗️분석 대상 파일 없음: '{OUTPUT_DIR}' 디렉토리에서 `*_sensitive.json` 파일을 찾지 못했습니다.")
        return

    print(f"📂 '{OUTPUT_DIR}'의 {len(analysis_targets)}개 결과 파일을 기반으로 원본 소스코드를 분석합니다.")
    print(f"🔎 소스코드 검색 경로: {project_source_dir}\n")
    print("-" * 85)
    print(f"{'원본 Swift 파일':<45} | {'코드 (KB)':>10} | {'AST (KB)':>10} | {'총 입력 (KB)':>12}")
    print("-" * 85)

    total_input_size_kb = 0

    for json_path in analysis_targets:
        # JSON 파일 이름에서 원본 Swift 파일 이름 추정
        swift_filename = os.path.basename(json_path).replace('_sensitive.json', '.swift')

        # 프로젝트 디렉토리에서 원본 Swift 파일 검색
        swift_filepath = find_source_file(project_source_dir, swift_filename)

        if not swift_filepath:
            print(f"{swift_filename:<45} | {'소스 없음':>10} | {'-':>10} | {'-':>12}")
            continue

        try:
            with open(swift_filepath, 'r', encoding='utf-8') as f:
                swift_code = f.read()

            ast_json = run_ast_analyzer(swift_filepath)
            if not ast_json:
                print(f"{swift_filename:<45} | {'✓':>10} | {'AST 실패':>10} | {'-':>12}")
                continue

            full_prompt = get_full_prompt(swift_code, ast_json)

            # 각 구성요소의 크기를 바이트 단위로 계산 (UTF-8 인코딩 기준) 후 KB로 변환
            code_size_kb = len(swift_code.encode('utf-8')) / 1024
            ast_size_kb = len(ast_json.encode('utf-8')) / 1024
            total_size_kb = len(full_prompt.encode('utf-8')) / 1024

            print(f"{swift_filename:<45} | {code_size_kb:10.2f} | {ast_size_kb:10.2f} | {total_size_kb:12.2f}")
            total_input_size_kb += total_size_kb

        except Exception as e:
            print(f"{swift_filename:<45} | 오류 발생: {e}")

    print("-" * 85)
    print(f"📊 총합: 모델에 입력될 데이터의 전체 크기는 약 {total_input_size_kb:.2f} KB 입니다.")
    print("\n분석이 완료되었습니다.")


if __name__ == "__main__":
    calculate_size_from_output_files()