#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
cli.py

ConsoleLLM CLI 인터페이스 - 완전 재작성
"""

import argparse
import sys
import os
from pathlib import Path

from .api import ConsoleLLM


def main():
    """CLI 메인 함수"""
    parser = argparse.ArgumentParser(
        description="ConsoleLLM - Swift/Objective-C AST 분석 시스템",
        epilog="Example: console-llm --mode exclude --project ./MyProject --base_model ./base_model.gguf"
    )

    # 필수 인수
    parser.add_argument("--mode", type=str, choices=['sensitive', 'exclude', 'both'], required=True,
                        help="분석 모드: sensitive (config 필수), exclude, both")
    parser.add_argument("--project", type=str, required=True,
                        help="분석할 프로젝트 디렉토리 경로")
    parser.add_argument("--base_model", type=str, required=True,
                        help="base_model.gguf 파일 경로")

    # LoRA 어댑터
    parser.add_argument("--lora_exclude", type=str,
                        help="exclude 모드용 Swift LoRA 어댑터 경로")
    # --- [수정된 부분 START] ---
    parser.add_argument("--lora_exclude_header", type=str,
                        help="exclude 모드용 Objective-C 헤더 LoRA 어댑터 경로")
    # --- [수정된 부분 END] ---
    parser.add_argument("--lora_sensitive", type=str,
                        help="sensitive 모드용 LoRA 어댑터 경로")

    # Config 파일 (sensitive 모드에서 필수)
    parser.add_argument("--config", type=str,
                        help="swingft_config.json 파일 경로 (sensitive 모드 시 필수)")

    # 출력 설정
    parser.add_argument("--output_dir", type=str, default="./output",
                        help="출력 디렉토리 (기본값: ./output)")
    parser.add_argument("--max_workers", type=int, default=4,
                        help="병렬 처리 워커 수 (기본값: 4)")

    # 모드 옵션
    parser.add_argument("--debug", action='store_true',
                        help="디버깅 모드: 개별 JSON 파일들과 summary 저장")
    parser.add_argument("--force_full", action='store_true',
                        help="강제 전체 분석 (exclude 모드만, 캐시 무시)")

    # 모델 설정
    parser.add_argument("--ctx", type=int, default=4096,
                        help="컨텍스트 크기 (기본값: 4096)")
    parser.add_argument("--gpu_layers", type=int, default=0,
                        help="GPU 레이어 수 (기본값: 0)")
    parser.add_argument("--threads", type=int, default=None,
                        help="CPU 스레드 수")
    parser.add_argument("--enable_4bit_kv_cache", action='store_true', default=True,
                        help="4비트 KV 캐시 활성화 (기본값: True)")
    parser.add_argument("--disable_4bit_kv_cache", action='store_true',
                        help="4비트 KV 캐시 비활성화")

    args = parser.parse_args()

    # 4비트 KV 캐시 설정
    if args.disable_4bit_kv_cache:
        args.enable_4bit_kv_cache = False

    # 입력 검증
    if not os.path.exists(args.project):
        print(f"Error: 프로젝트 디렉토리를 찾을 수 없습니다: {args.project}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.project):
        print(f"Error: 프로젝트 경로가 디렉토리가 아닙니다: {args.project}", file=sys.stderr)
        sys.exit(1)

    # 모드별 LoRA 어댑터 확인
    if args.mode in ['exclude', 'both'] and not args.lora_exclude:
        print(f"Warning: {args.mode} 모드에는 --lora_exclude가 필요합니다.")

    if args.mode in ['sensitive', 'both'] and not args.lora_sensitive:
        print(f"Warning: {args.mode} 모드에는 --lora_sensitive가 필요합니다.")

    # sensitive 모드 config 파일 확인
    if args.mode == 'sensitive' and not args.config:
        print("Error: sensitive 모드에는 --config가 필수입니다 (target identifiers 필요).", file=sys.stderr)
        sys.exit(1)

    # 소스 파일 확인
    source_files = []
    for root, dirs, files in os.walk(args.project):
        source_files.extend([f for f in files if f.endswith(('.swift', '.h'))])

    if not source_files:
        print(f"Warning: 프로젝트에 Swift 또는 Objective-C 헤더 파일이 없습니다: {args.project}")

    swift_count = sum(1 for f in source_files if f.endswith('.swift'))
    objc_count = sum(1 for f in source_files if f.endswith('.h'))
    print(f"Found {swift_count} Swift files and {objc_count} Objective-C header files")

    # 모드 설명
    if args.debug:
        print("Debug mode: 개별 JSON 파일들과 summary 저장")
    else:
        print("Standard mode: 식별자 목록 파일만 저장")

    if args.force_full:
        print("Force full analysis: 캐시 무시하고 전체 재분석")
    else:
        print("Incremental analysis: 변경된 파일만 분석")

    try:
        # ConsoleLLM 초기화
        analyzer = ConsoleLLM(
            base_model_path=args.base_model,
            lora_exclude_path=args.lora_exclude,
            # --- [수정된 부분 START] ---
            lora_exclude_header_path=args.lora_exclude_header,
            # --- [수정된 부분 END] ---
            lora_sensitive_path=args.lora_sensitive,
            n_ctx=args.ctx,
            n_gpu_layers=args.gpu_layers,
            n_threads=args.threads,
            enable_4bit_kv_cache=args.enable_4bit_kv_cache,
            auto_preload=True
        )

        # 분석 실행
        print(f"\n=== ConsoleLLM: {args.mode.upper()} MODE ===")
        print(f"프로젝트: {args.project}")
        print(f"출력 디렉토리: {args.output_dir}")
        if args.config:
            print(f"Config: {args.config}")

        if args.mode == 'exclude':
            results = analyzer.analyze_exclude(
                project_path=args.project,
                config_path=args.config,
                output_dir=args.output_dir,
                max_workers=args.max_workers,
                save_individual_files=args.debug,
                force_full_analysis=args.force_full
            )

        elif args.mode == 'sensitive':
            results = analyzer.analyze_sensitive(
                project_path=args.project,
                config_path=args.config,
                output_dir=args.output_dir,
                max_workers=args.max_workers,
                save_individual_files=args.debug
            )

        elif args.mode == 'both':
            if not args.config:
                print("Warning: sensitive 모드는 config가 필요하므로 exclude 모드만 실행됩니다.")

            results = analyzer.analyze_both(
                project_path=args.project,
                config_path=args.config,
                output_base_dir=args.output_dir,
                max_workers=args.max_workers,
                save_individual_files=args.debug,
                force_full_analysis=args.force_full
            )

        print(f"\n=== 분석이 완료되었습니다 ===")
        print(f"결과가 {args.output_dir}에 저장되었습니다.")

        # 결과 파일들 표시
        if args.mode in ['exclude', 'both']:
            exclude_txt = os.path.join(args.output_dir, "exclude",
                                       "exclude_id.txt") if args.mode == 'both' else os.path.join(args.output_dir,
                                                                                                  "exclude_id.txt")
            if os.path.exists(exclude_txt):
                print(f"Exclude 식별자: {exclude_txt}")

        if args.mode in ['sensitive', 'both']:
            sensitive_txt = os.path.join(args.output_dir, "sensitive",
                                         "sensitive_id.txt") if args.mode == 'both' else os.path.join(args.output_dir,
                                                                                                      "sensitive_id.txt")
            if os.path.exists(sensitive_txt):
                print(f"Sensitive 식별자: {sensitive_txt}")

        if args.debug:
            print("Debug files: 개별 JSON과 summary 파일들도 저장되었습니다.")
        else:
            print("캐시 파일을 이용해 다음 실행 시 빠른 증분 분석이 가능합니다.")

    except FileNotFoundError as e:
        print(f"Error: 파일을 찾을 수 없습니다: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: 설정 오류: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: 예상치 못한 오류가 발생했습니다: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()