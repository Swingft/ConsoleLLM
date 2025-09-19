#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
cli.py

ConsoleLLM CLI 인터페이스
"""

import argparse
import sys
import os
from pathlib import Path

from .api import ConsoleLLM


def main():
    """CLI 메인 함수"""
    parser = argparse.ArgumentParser(
        description="ConsoleLLM - Swift AST 분석 시스템",
        epilog="Example: console-llm --mode sensitive --base_model ./base_model.gguf --config ./swingft_config.json"
    )

    # 필수 인수
    parser.add_argument("--mode", type=str, choices=['sensitive', 'exclude', 'both'], required=True,
                        help="분석 모드: sensitive, exclude 또는 both")
    parser.add_argument("--base_model", type=str, required=True,
                        help="base_model.gguf 파일 경로")
    parser.add_argument("--config", type=str, required=True,
                        help="swingft_config.json 파일 절대 경로")

    # LoRA 어댑터
    parser.add_argument("--lora_sensitive", type=str,
                        help="lora_sensitive.gguf 파일 경로")
    parser.add_argument("--lora_exclude", type=str,
                        help="lora_exclude.gguf 파일 경로")

    # 출력 설정
    parser.add_argument("--output_dir", type=str, default="./output",
                        help="출력 디렉토리 (기본값: ./output)")
    parser.add_argument("--max_workers", type=int, default=4,
                        help="병렬 처리 워커 수 (기본값: 4)")

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

    try:
        # ConsoleLLM 초기화
        analyzer = ConsoleLLM(
            base_model_path=args.base_model,
            lora_exclude_path=args.lora_exclude,
            lora_sensitive_path=args.lora_sensitive,
            n_ctx=args.ctx,
            n_gpu_layers=args.gpu_layers,
            n_threads=args.threads,
            enable_4bit_kv_cache=args.enable_4bit_kv_cache,
            auto_preload=True
        )

        # 분석 실행
        if args.mode == 'sensitive':
            if not args.lora_sensitive:
                print("Warning: sensitive 모드에는 --lora_sensitive가 필요합니다. base model만 사용합니다.")

            print("=== ConsoleLLM: SENSITIVE MODE ===")
            results = analyzer.analyze_sensitive(
                config_path=args.config,
                output_dir=args.output_dir,
                max_workers=args.max_workers
            )

        elif args.mode == 'exclude':
            if not args.lora_exclude:
                print("Warning: exclude 모드에는 --lora_exclude가 필요합니다. base model만 사용합니다.")

            print("=== ConsoleLLM: EXCLUDE MODE ===")
            results = analyzer.analyze_exclude(
                config_path=args.config,
                output_dir=args.output_dir,
                max_workers=args.max_workers
            )

        elif args.mode == 'both':
            print("=== ConsoleLLM: BOTH MODES ===")
            results = analyzer.analyze_both(
                config_path=args.config,
                output_base_dir=args.output_dir,
                max_workers=args.max_workers
            )

        print(f"\n=== ConsoleLLM {args.mode.upper()} 분석이 완료되었습니다. ===")
        print(f"결과가 {args.output_dir}에 저장되었습니다.")

    except FileNotFoundError as e:
        print(f"Error: 파일을 찾을 수 없습니다: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: 설정 오류: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()