# ConsoleLLM

**Swift 코드 분석 시스템 - LLM 기반 난독화 제외 대상 및 보안 민감 로직 식별자 분석**

ConsoleLLM은 LLM(Large Language Model)을 활용하여 Swift 코드의 보안 민감 로직 식별자와 난독화 제외 대상을 식별하는 모듈화된 분석 시스템입니다. 메모리 효율성을 위해 4비트 K_M 방식으로 양자화된 모델을 사용합니다.

## 주요 기능

- **Exclude 모드**: 난독화에서 제외되어야 할 식별자 분석
- **Sensitive 모드**: 보안 민감 로직 식별자 분석
- **Metal GPU 가속**: Apple Silicon에서 Metal GPU 활용 지원
- **병렬 처리**: 멀티 워커를 통한 효율적인 파일 처리
- **AST 분석**: Swift AST를 활용한 정밀한 코드 분석
- **4비트 양자화**: 베이스 모델과 LoRA 어댑터 모두 4비트 K_M 방식으로 양자화하여 메모리 효율성 극대화

## 시스템 요구사항

### 지원 플랫폼
- **권장**: Apple Silicon Mac (M1/M2/M3) - Metal GPU 가속 지원
- **지원**: Intel Mac (CPU 전용, 성능 제한)

### 필요 환경
- macOS 11.0 이상
- Python 3.8 이상
- 메모리: 최소 16GB (24GB+ 권장)
- Xcode Command Line Tools

## 프로젝트 구조

```
ConsoleLLM/
├── console_llm/                    # 메인 패키지
│   ├── __init__.py                 # 패키지 초기화
│   ├── api.py                      # 프로그래밍 API
│   ├── cli.py                      # CLI 인터페이스
│   ├── core/                       # 핵심 모듈
│   │   ├── __init__.py
│   │   ├── base_analyzer.py        # 베이스 분석기
│   │   ├── model_loader.py         # 최적화된 모델 로더
│   │   └── utils.py                # 공통 유틸리티
│   ├── analyzers/                  # 분석기 모듈
│   │   ├── __init__.py
│   │   ├── exclude_analyzer.py     # Exclude 분석기
│   │   └── sensitive_analyzer.py   # Sensitive 분석기
│   └── ast_analyzers/              # AST 분석 실행파일
│       ├── exclude/
│       │   └── SwiftASTAnalyzer    # Exclude용 AST 분석기
│       └── sensitive/
│           └── SwiftASTAnalyzer    # Sensitive용 AST 분석기
├── setup.py                       # 패키지 설정
├── requirements.txt                # 의존성 목록
├── swingft_config.json            # 프로젝트 설정 파일
├── base_model.gguf                # 베이스 모델 파일
├── lora_exclude.gguf              # Exclude LoRA 어댑터
└── lora_sensitive.gguf            # Sensitive LoRA 어댑터
```

## 설치 방법

### 1. 사전 준비

```bash
# Xcode Command Line Tools 설치
xcode-select --install

# conda 환경 생성 (Apple Silicon용)
CONDA_SUBDIR=osx-arm64 conda create -n consolellm_arm64 python=3.10 -c conda-forge
conda activate consolellm_arm64
```

### 2. 의존성 설치

#### Apple Silicon Mac
```bash
# 옵션 1: conda를 통한 설치 (권장)
conda search llama-cpp-python -c conda-forge
conda install -c conda-forge llama-cpp-python=0.3.16  # 사용 가능한 최신 버전

# 옵션 2: Metal 지원 pip 설치 (대안)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/metal

# ConsoleLLM 설치
pip install -e .
```

#### Intel Mac
```bash
# CPU 전용 llama-cpp-python 설치
conda install -c conda-forge llama-cpp-python

# ConsoleLLM 설치
pip install -e .
```

## 사용 방법

### CLI 사용

#### 기본 사용법
```bash
# Sensitive 분석
console-llm --mode sensitive \
  --base_model ./base_model.gguf \
  --lora_sensitive ./lora_sensitive.gguf \
  --config ./swingft_config.json

# Exclude 분석
console-llm --mode exclude \
  --base_model ./base_model.gguf \
  --lora_exclude ./lora_exclude.gguf \
  --config ./swingft_config.json

# 두 모드 모두 실행
console-llm --mode both \
  --base_model ./base_model.gguf \
  --lora_exclude ./lora_exclude.gguf \
  --lora_sensitive ./lora_sensitive.gguf \
  --config ./swingft_config.json
```

#### 성능 최적화 설정

**Apple Silicon Mac (권장 설정)**:
```bash
console-llm --mode sensitive \
  --base_model ./base_model.gguf \
  --lora_sensitive ./lora_sensitive.gguf \
  --config ./swingft_config.json \
  --gpu_layers 24 \
  --ctx 16384 \
  --enable_4bit_kv_cache \
  --max_workers 1
```

**Intel Mac (안전 설정)**:
```bash
console-llm --mode sensitive \
  --base_model ./base_model.gguf \
  --lora_sensitive ./lora_sensitive.gguf \
  --config ./swingft_config.json \
  --gpu_layers 0 \
  --ctx 8192 \
  --threads 4 \
  --max_workers 1
```

#### 실행 시간 측정
```bash
time console-llm --mode sensitive \
  --base_model ./base_model.gguf \
  --lora_sensitive ./lora_sensitive.gguf \
  --config ./swingft_config.json \
  --gpu_layers 24 \
  --ctx 16384 \
  --max_workers 1
```

### 프로그래밍 API 사용

#### 기본 사용법
```python
from console_llm.api import ConsoleLLM

# ConsoleLLM 초기화
analyzer = ConsoleLLM(
    base_model_path="./base_model.gguf",
    lora_exclude_path="./lora_exclude.gguf",
    lora_sensitive_path="./lora_sensitive.gguf",
    n_ctx=16384,
    n_gpu_layers=24,
    enable_4bit_kv_cache=True
)

# 단일 분석
exclude_result = analyzer.analyze_exclude("./swingft_config.json")
sensitive_result = analyzer.analyze_sensitive("./swingft_config.json")

# 두 모드 모두 실행
both_results = analyzer.analyze_both("./swingft_config.json")

print(f"Exclude: {exclude_result['files_analyzed']} 파일 분석")
print(f"Sensitive: {sensitive_result['files_analyzed']} 파일 분석")
```

#### 배치 분석
```python
from console_llm.api import ConsoleLLM

analyzer = ConsoleLLM(
    base_model_path="./base_model.gguf",
    lora_sensitive_path="./lora_sensitive.gguf"
)

# 여러 프로젝트 배치 분석
config_files = [
    "./project1/config.json",
    "./project2/config.json", 
    "./project3/config.json"
]

batch_results = analyzer.analyze_batch(
    config_paths=config_files,
    output_base_dir="./batch_results"
)

for project_name, result in batch_results.items():
    print(f"{project_name}: 완료")
```

#### 빠른 분석 (편의 함수)
```python
from console_llm.api import quick_exclude_analysis, quick_sensitive_analysis

# 빠른 Exclude 분석
result = quick_exclude_analysis(
    base_model_path="./base_model.gguf",
    lora_exclude_path="./lora_exclude.gguf",
    config_path="./swingft_config.json"
)

# 빠른 Sensitive 분석
result = quick_sensitive_analysis(
    base_model_path="./base_model.gguf",
    lora_sensitive_path="./lora_sensitive.gguf",
    config_path="./swingft_config.json"
)
```

## 설정 파일 (swingft_config.json)

```json
{
  "_comment_path": "프로젝트 절대 경로 설정",
  "project": {
    "input": "/path/to/your/swift/project",
    "output": "/path/to/output/directory",
    "build_target": "YourSwiftProject"
  },
  "options": {
    "Obfuscation_classNames": true,
    "Obfuscation_methodNames": true,
    "Obfuscation_variableNames": true,
    "Obfuscation_controlFlow": true,
    "Delete_debug_symbols": true,
    "Encryption_strings": true
  },
  "exclude": {
    "obfuscation": [
      "AppearanceConfigurationTests",
      "configureDescriptionLabel",
      "stackView",
      "OnboardPageViewControllerDelegate"
    ],
    "encryption": [
      "someString",
      "**Wildcard"
    ]
  },
  "include": {
    "obfuscation": [
      "collectionView",
      "data",
      "isSelected"
    ],
    "encryption": [
      "sensitiveData"
    ]
  }
}
```

## CLI 옵션 상세 설명

### 필수 옵션
- `--mode`: 분석 모드 (`sensitive`, `exclude`, `both`)
- `--base_model`: 베이스 모델 GGUF 파일 경로
- `--config`: 설정 파일 경로

### 모델 관련 옵션
- `--lora_sensitive`: Sensitive LoRA 어댑터 경로
- `--lora_exclude`: Exclude LoRA 어댑터 경로

### 성능 튜닝 옵션
- `--gpu_layers`: GPU에서 처리할 레이어 수 (0-32)
- `--ctx`: 컨텍스트 크기 (토큰 수)
- `--threads`: CPU 스레드 수
- `--max_workers`: 병렬 처리 워커 수
- `--enable_4bit_kv_cache`: 4비트 KV 캐시 활성화 (기본값)
- `--disable_4bit_kv_cache`: 4비트 KV 캐시 비활성화

### 출력 옵션
- `--output_dir`: 출력 디렉토리 경로

## 성능 최적화 가이드

### Apple Silicon Mac 최적화

**권장 설정**:
```bash
--gpu_layers 24          # Metal GPU 최대 활용
--ctx 16384             # 적정 컨텍스트 크기
--enable_4bit_kv_cache  # Metal 최적화
--max_workers 1         # 메모리 안정성
```

**고성능 설정** (32GB+ 메모리):
```bash
--gpu_layers 32
--ctx 32768
--max_workers 2
```

### Intel Mac 최적화

**안전 설정**:
```bash
--gpu_layers 0          # CPU 전용
--ctx 8192             # 작은 컨텍스트
--threads 8            # CPU 코어 수
--max_workers 1        # 안정성 우선
--enable_4bit_kv_cache
```

## 출력 결과

### 분석 결과 구조

각 Swift 파일별로 다음과 같은 JSON 결과가 생성됩니다:

```json
{
  "file_path": "/path/to/SwiftFile.swift",
  "reasoning": "단계별 분석 근거",
  "identifiers": [
    "identifier1",
    "identifier2"
  ],
  "raw_output": "모델 원본 출력",
  "ast_json": "AST 분석 결과"
}
```

### 요약 결과

```json
{
  "mode": "sensitive",
  "files_analyzed": 5,
  "successful": 5,
  "failed": 0,
  "total_sensitive_identifiers_found": 12,
  "unique_sensitive_identifiers": [
    "authToken", 
    "apiKey",
    "userPassword"
  ],
  "results": [...]
}
```

## 내부망 배포 (Offline/Internal Network Deployment)

인터넷 연결이 제한된 내부망 환경을 위해, 모든 의존성과 모델이 포함된 올인원(All-in-one) 패키지를 제공합니다. 각 아키텍처에 맞는 패키지를 사용해 쉽게 배포할 수 있습니다.

### 패키지 구조

#### Intel Mac용 패키지
```
ConsoleLLM_Intel.zip
├── console_llm/                    # ConsoleLLM 소스 코드
├── dependencies/                   # 오프라인 의존성
│   └── llama_cpp_python-*.whl     # Intel Mac용 wheel 파일
├── models/                         # AI 모델 파일
│   ├── base_model.gguf
│   ├── lora_exclude.gguf
│   └── lora_sensitive.gguf
├── install_intel.sh               # Intel Mac 설치 스크립트
├── setup.py                       # 패키지 설정
├── requirements.txt               # 의존성 목록
└── README_Intel.md                # Intel Mac 전용 설명서
```

#### Apple Silicon용 패키지
```
ConsoleLLM_AppleSilicon.zip
├── console_llm/                    # ConsoleLLM 소스 코드
├── dependencies/                   # 오프라인 의존성
│   └── llama_cpp_python-*.whl     # Apple Silicon용 wheel 파일
├── models/                         # AI 모델 파일
│   ├── base_model.gguf
│   ├── lora_exclude.gguf
│   └── lora_sensitive.gguf
├── install_apple.sh               # Apple Silicon 설치 스크립트
├── setup.py                       # 패키지 설정
├── requirements.txt               # 의존성 목록
└── README_AppleSilicon.md          # Apple Silicon 전용 설명서
```

### 배포 절차

#### 1. 패키지 전달 및 압축 해제
아키텍처에 맞는 패키지 파일(`.zip`)을 대상 서버나 PC에 전달한 후, 원하는 위치에 압축을 해제합니다.

```bash
# 패키지 압축 해제
unzip ConsoleLLM_AppleSilicon.zip  # 또는 ConsoleLLM_Intel.zip
cd ConsoleLLM_AppleSilicon          # 압축 해제된 폴더로 이동
```

#### 2. 설치 스크립트 실행
터미널을 열고 압축 해제된 폴더로 이동한 뒤, 환경에 맞는 설치 스크립트를 실행합니다. 이 스크립트는 패키지 내부에 포함된 `.whl` 파일을 사용하여 오프라인으로 핵심 의존성을 설치하고 `ConsoleLLM`을 시스템에 등록합니다.

**Apple Silicon Mac**:
```bash
# 스크립트 실행 권한 부여 (필요시)
chmod +x install_apple.sh

# 설치 진행
bash install_apple.sh
```

**Intel Mac**:
```bash
# 스크립트 실행 권한 부여 (필요시)
chmod +x install_intel.sh

# 설치 진행
bash install_intel.sh
```

#### 3. 설치 확인
설치가 완료되면 `console-llm --help` 명령어를 실행하여 프로그램이 정상적으로 인식되는지 확인합니다.

```bash
console-llm --help
```

### 설치 스크립트 내부 동작

#### `install_apple.sh` 스크립트 예시
Apple Silicon용 설치 스크립트는 내부적으로 다음과 같은 작업을 수행하여 설치 과정을 자동화합니다:

```bash
#!/bin/bash
# Apple Silicon용 ConsoleLLM 설치 스크립트

echo "🚀 Apple Silicon용 ConsoleLLM 설치를 시작합니다."

# 1. 패키지에 포함된 오프라인 의존성 설치
echo "📦 오프라인 의존성을 설치합니다: llama-cpp-python"
pip install dependencies/llama_cpp_python-*-macosx_11_0_arm64.whl

# 2. ConsoleLLM 패키지 설치 (개발 모드)
echo "🔧 ConsoleLLM을 설치합니다."
pip install -e .

# 3. AST 분석기에 실행 권한 부여
echo "🔑 AST 분석기에 실행 권한을 부여합니다."
chmod +x console_llm/ast_analyzers/*/SwiftASTAnalyzer

echo "✅ 설치가 완료되었습니다. 'console-llm --help' 명령어로 사용법을 확인하세요."
```

#### `install_intel.sh` 스크립트 예시
Intel Mac용 설치 스크립트도 유사한 구조로 동작합니다:

```bash
#!/bin/bash
# Intel Mac용 ConsoleLLM 설치 스크립트

echo "🚀 Intel Mac용 ConsoleLLM 설치를 시작합니다."

# 1. 패키지에 포함된 오프라인 의존성 설치
echo "📦 오프라인 의존성을 설치합니다: llama-cpp-python"
pip install dependencies/llama_cpp_python-*-macosx_10_16_x86_64.whl

# 2. ConsoleLLM 패키지 설치 (개발 모드)
echo "🔧 ConsoleLLM을 설치합니다."
pip install -e .

# 3. AST 분석기에 실행 권한 부여
echo "🔑 AST 분석기에 실행 권한을 부여합니다."
chmod +x console_llm/ast_analyzers/*/SwiftASTAnalyzer

echo "✅ 설치가 완료되었습니다. 'console-llm --help' 명령어로 사용법을 확인하세요."
```

### 내부망 배포 시 주의사항

1. **Python 환경**: 대상 시스템에 Python 3.8 이상이 설치되어 있어야 합니다.
2. **아키텍처 확인**: Intel Mac과 Apple Silicon Mac용 패키지가 다르므로 올바른 패키지를 사용해야 합니다.
3. **권한 설정**: 설치 스크립트와 AST 분석기 실행파일에 적절한 권한이 필요합니다.
4. **모델 파일 경로**: 설치 후 모델 파일들이 올바른 경로에 위치하는지 확인해야 합니다.

## 문제 해결

### 일반적인 오류

#### 1. Segmentation Fault
**원인**: 메모리 부족
**해결**: 
```bash
--max_workers 1
--gpu_layers 8
--ctx 8192
```

#### 2. Context Window Exceeded
**원인**: 컨텍스트 크기 부족
**해결**:
```bash
--ctx 32768  # 더 큰 컨텍스트
```

#### 3. AST Analysis Failed
**원인**: AST 분석기 권한 문제
**해결**:
```bash
chmod +x console_llm/ast_analyzers/*/SwiftASTAnalyzer
```

#### 4. Model Loading Failed
**원인**: 모델 파일 문제 또는 아키텍처 불일치
**해결**:
- 파일 존재 및 권한 확인
- Intel/Apple Silicon 환경에 맞는 llama-cpp-python 설치

### 성능 문제

#### 느린 처리 속도
1. GPU 레이어 수 증가: `--gpu_layers 24`
2. 4비트 KV 캐시 활성화: `--enable_4bit_kv_cache`
3. 적절한 컨텍스트 크기 설정
4. Apple Silicon 환경 사용

#### 메모리 부족
1. 워커 수 감소: `--max_workers 1`
2. 컨텍스트 크기 감소: `--ctx 8192`
3. GPU 레이어 수 감소: `--gpu_layers 8`

## 개발 가이드

### 모듈 구조

- **core**: 핵심 기능 (모델 로더, 베이스 분석기)
- **analyzers**: 모드별 분석기 (Exclude, Sensitive)
- **api**: 외부 인터페이스 (CLI, 프로그래밍 API)

### 새로운 분석 모드 추가

1. `console_llm/analyzers/`에 새로운 분석기 클래스 생성
2. `BaseAnalyzer`를 상속하여 구현
3. `api.py`에 해당 모드 추가
4. CLI에 옵션 추가

## 라이선스

MIT License

## 지원 및 문의

프로젝트 관련 문의사항이나 이슈는 GitHub Issues를 통해 제보해 주세요.

---

**ConsoleLLM** - Swift 코드 보안 분석의 새로운 표준