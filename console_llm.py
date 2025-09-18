"""
console_llm.py

ConsoleLLM 메인 실행 파일
- sensitive/exclude 모드에 따라 해당하는 분석기를 호출
"""

import argparse
import sys
import os
from pathlib import Path

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="ConsoleLLM - Swift AST 분석 시스템",
        epilog="Example: python console_llm.py --mode sensitive --base_model ./base_model.gguf --config ./swingft_config.json"
    )

    # 필수 인수
    parser.add_argument("--mode", type=str, choices=['sensitive', 'exclude'], required=True,
                       help="분석 모드: sensitive 또는 exclude")
    parser.add_argument("--base_model", type=str, required=True,
                       help="base_model.gguf 파일 경로")
    parser.add_argument("--config", type=str, required=True,
                       help="swingft_config.json 파일 절대 경로")

    # 선택적 인수
    parser.add_argument("--lora_sensitive", type=str,
                       help="lora_sensitive.gguf 파일 경로")
    parser.add_argument("--lora_exclude", type=str,
                       help="lora_exclude.gguf 파일 경로")
    parser.add_argument("--output_dir", type=str, default="./output",
                       help="출력 디렉토리 (기본값: ./output)")
    parser.add_argument("--max_workers", type=int, default=4,
                       help="병렬 처리 워커 수 (기본값: 4)")

    # 모델 설정
    parser.add_argument("--ctx", type=int, default=32768,
                       help="컨텍스트 크기 (기본값: 32768)")
    parser.add_argument("--gpu_layers", type=int, default=0,
                       help="GPU 레이어 수 (기본값: 0)")
    parser.add_argument("--threads", type=int, default=None,
                       help="CPU 스레드 수")

    args = parser.parse_args()

    try:
        if args.mode == 'sensitive':
            print("=== ConsoleLLM: SENSITIVE MODE ===")
            from sensitive_analyzer import SensitiveAnalyzer

            analyzer = SensitiveAnalyzer(
                base_model_path=args.base_model,
                lora_path=args.lora_sensitive,
                n_ctx=args.ctx,
                n_gpu_layers=args.gpu_layers,
                n_threads=args.threads
            )

            results = analyzer.analyze_project(
                config_path=args.config,
                output_dir=args.output_dir,
                max_workers=args.max_workers
            )

        elif args.mode == 'exclude':
            print("=== ConsoleLLM: EXCLUDE MODE ===")
            from exclude_analyzer import ExcludeAnalyzer

            analyzer = ExcludeAnalyzer(
                base_model_path=args.base_model,
                lora_path=args.lora_exclude,
                n_ctx=args.ctx,
                n_gpu_layers=args.gpu_layers,
                n_threads=args.threads
            )

            results = analyzer.analyze_project(
                config_path=args.config,
                output_dir=args.output_dir,
                max_workers=args.max_workers
            )

        print(f"\n=== ConsoleLLM {args.mode.upper()} 분석이 완료되었습니다. ===")

    except ImportError as e:
        print(f"Error: 필요한 모듈을 불러올 수 없습니다: {e}", file=sys.stderr)
        print("sensitive_analyzer.py 또는 exclude_analyzer.py 파일이 있는지 확인해주세요.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()