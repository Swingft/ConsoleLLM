"""
model_loader.py

최적화된 모델 로더 - 4비트 KV 캐시 및 LoRA 어댑터 지원
"""

import os
import threading
from typing import Optional, Dict, Any
from llama_cpp import Llama


class OptimizedModelLoader:
    """최적화된 GGUF 모델 로더"""

    def __init__(self):
        self.model_cache: Dict[str, Llama] = {}
        self.model_lock = threading.Lock()

    def load_model(self,
                   base_model_path: str,
                   lora_path: Optional[str] = None,
                   n_ctx: int = 4096,
                   n_gpu_layers: int = 0,
                   n_threads: Optional[int] = None,
                   enable_4bit_kv_cache: bool = True) -> Llama:
        """
        최적화된 모델 로딩

        Args:
            base_model_path: 베이스 모델 경로
            lora_path: LoRA 어댑터 경로
            n_ctx: 컨텍스트 크기
            n_gpu_layers: GPU 레이어 수
            n_threads: CPU 스레드 수
            enable_4bit_kv_cache: 4비트 KV 캐시 활성화

        Returns:
            로드된 Llama 모델
        """
        # 캐시 키 생성
        cache_key = f"{base_model_path}:{lora_path}:{n_ctx}:{n_gpu_layers}:{enable_4bit_kv_cache}"

        with self.model_lock:
            # 캐시된 모델이 있으면 반환
            if cache_key in self.model_cache:
                print(f"Using cached model: {cache_key}")
                return self.model_cache[cache_key]

            print(f"Loading new model: {base_model_path}")
            if lora_path:
                print(f"With LoRA adapter: {lora_path}")

            try:
                # 모델 로딩 매개변수 설정
                model_params = {
                    "model_path": base_model_path,
                    "n_ctx": n_ctx,
                    "n_gpu_layers": n_gpu_layers,
                    "verbose": False,
                    "use_mmap": True,
                    "use_mlock": False,
                    "rope_scaling_type": 1,
                    "rope_freq_base": 10000.0,
                    "rope_freq_scale": 1.0,
                }

                # 4비트 KV 캐시 설정
                if enable_4bit_kv_cache:
                    model_params.update({
                        "type_k": 1,  # GGML_TYPE_Q4_0
                        "type_v": 1,  # GGML_TYPE_Q4_0
                    })
                    print("4-bit KV cache enabled")

                # CPU 스레드 설정
                if n_threads:
                    model_params["n_threads"] = n_threads

                # LoRA 어댑터 설정
                if lora_path and os.path.exists(lora_path):
                    model_params["lora_path"] = lora_path

                # 모델 로드
                model = Llama(**model_params)

                # 캐시에 저장
                self.model_cache[cache_key] = model
                print(f"Model loaded successfully: {cache_key}")

                return model

            except Exception as e:
                print(f"Failed to load model with optimal settings: {e}")

                # Fallback: 최소 설정으로 다시 시도
                return self._load_fallback_model(base_model_path, lora_path)

    def _load_fallback_model(self, base_model_path: str, lora_path: Optional[str] = None) -> Llama:
        """Fallback 모델 로딩 (최소 설정)"""
        print("Attempting fallback model loading with minimal settings...")

        try:
            fallback_params = {
                "model_path": base_model_path,
                "n_ctx": 2048,
                "n_gpu_layers": 0,
                "n_threads": 1,
                "verbose": False,
                "use_mmap": False,
                "use_mlock": False,
            }

            # LoRA 없이 시도
            model = Llama(**fallback_params)
            print("Fallback model loaded successfully (without LoRA)")
            return model

        except Exception as e:
            raise RuntimeError(f"Failed to load model even with fallback settings: {e}")

    def clear_cache(self):
        """모델 캐시 정리"""
        with self.model_lock:
            for key, model in self.model_cache.items():
                try:
                    del model
                except:
                    pass
            self.model_cache.clear()
            print("Model cache cleared")

    def get_cached_models(self) -> list:
        """캐시된 모델 목록 반환"""
        with self.model_lock:
            return list(self.model_cache.keys())


# 글로벌 모델 로더 인스턴스
_global_loader = OptimizedModelLoader()


def get_model_loader() -> OptimizedModelLoader:
    """글로벌 모델 로더 반환"""
    return _global_loader


def preload_models(base_model_path: str,
                   lora_exclude_path: Optional[str] = None,
                   lora_sensitive_path: Optional[str] = None,
                   **kwargs):
    """모델들을 미리 로드"""
    loader = get_model_loader()

    print("Pre-loading models...")

    # Exclude 모델 로드
    if lora_exclude_path:
        loader.load_model(base_model_path, lora_exclude_path, **kwargs)

    # Sensitive 모델 로드
    if lora_sensitive_path:
        loader.load_model(base_model_path, lora_sensitive_path, **kwargs)

    print("All models pre-loaded successfully")