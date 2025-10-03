# ConsoleLLM v1.1.0

**Swift/Objective-C 코드 분석 시스템 - LLM 기반 난독화 제외 대상 및 보안 민감 로직 식별자 분석**

ConsoleLLM은 LLM(Large Language Model)을 활용하여 Swift 코드의 보안 민감 로직 식별자와 Objective-C Header/Swift 파일의 난독화 제외 대상을 식별하는 모듈화된 분석 시스템입니다. 메모리 효율성을 위해 4비트 K_M 방식으로 양자화된 모델을 사용합니다.

## 주요 기능 (v1.1.0 업데이트)

- **Header 파일 Exclude 분석**: Objective-C 헤더 파일의 public API 식별자 분석 (AST 분석 없이 소스코드만 사용)
- **Swift 파일 Exclude 분석**: Swift 코드의 난독화 제외 대상 식별자 분석 (AST 기반)
- **Sensitive 모드**: Swift 코드의 보안 민감 로직 식별자 분석
- **스마트 파일 분할**: 25KB 이상의 큰 헤더 파일을 안전하게 분할하여 처리
- **3개 LoRA 어댑터 지원**: Header용, Swift용, Sensitive용으로 구분된 전용 모델
- **Metal GPU 가속**: Apple Silicon에서 Metal GPU 활용 지원
- **병렬 처리**: 멀티 워커를 통한 효율적인 파일 처리
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
│   │   ├── exclude_analyzer.py     # Header + Swift Exclude 분석기
│   │   └── sensitive_analyzer.py   # Swift Sensitive 분석기
│   └── ast_analyzers/              # AST 분석 실행파일
│       ├── exclude/
│       │   └── SwiftASTAnalyzer    # Exclude용 AST 분석기 (Swift 파일용)
│       └── sensitive/
│           └── SwiftASTAnalyzer    # Sensitive용 AST 분석기
├── setup.py                       # 패키지 설정
├── requirements.txt                # 의존성 목록
├── swingft_config.json            # 프로젝트 설정 파일
├── models/                        # 모델 파일들
│   ├── base_model.gguf            # 베이스 모델 파일
│   ├── lora_exclude_header.gguf   # Header 파일 Exclude용 LoRA
│   ├── lora_exclude_swift.gguf    # Swift 파일 Exclude용 LoRA
│   └── lora_sensitive.gguf        # Swift 파일 Sensitive용 LoRA
```

## 모델 파일 설명

ConsoleLLM v1.1.0부터는 3개의 전용 LoRA 어댑터를 사용합니다:

- **base_model.gguf**: 공통 베이스 모델 (4비트 양자화)
- **lora_exclude_header.gguf**: Objective-C 헤더 파일 분석 전용
- **lora_exclude_swift.gguf**: Swift 파일 exclude 분석 전용  
- **lora_sensitive.gguf**: Swift 파일 sensitive 분석 전용

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

**Header 파일만 Exclude 분석**:
```bash
console-llm --mode exclude \
  --file_types header \
  --project ./MyProject \
  --base_model ./models/base_model.gguf \
  --lora_exclude_header ./models/lora_exclude_header.gguf \
  --output_dir ./output_exclude_headers
```

**Swift 파일만 Exclude 분석**:
```bash
console-llm --mode exclude \
  --file_types swift \
  --project ./MyProject \
  --base_model ./models/base_model.gguf \
  --lora_exclude_swift ./models/lora_exclude_swift.gguf \
  --output_dir ./output_exclude_swift
```

**Header + Swift 파일 모두 Exclude 분석**:
```bash
console-llm --mode exclude \
  --file_types both \
  --project ./MyProject \
  --base_model ./models/base_model.gguf \
  --lora_exclude_header ./models/lora_exclude_header.gguf \
  --lora_exclude_swift ./models/lora_exclude_swift.gguf \
  --output_dir ./output_exclude
```

**Sensitive 분석 (Swift만)**:
```bash
console-llm --mode sensitive \
  --project ./MyProject \
  --base_model ./models/base_model.gguf \
  --lora_sensitive ./models/lora_sensitive.gguf \
  --output_dir ./output_sensitive
```

**모든 분석 실행**:
```bash
console-llm --mode all \
  --project ./MyProject \
  --base_model ./models/base_model.gguf \
  --lora_exclude_header ./models/lora_exclude_header.gguf \
  --lora_exclude_swift ./models/lora_exclude_swift.gguf \
  --lora_sensitive ./models/lora_sensitive.gguf \
  --output_dir ./output_all
```

#### 성능 최적화 설정

**Apple Silicon Mac (권장 설정)**:
```bash
console-llm --mode exclude \
  --file_types both \
  --project ./MyProject \
  --base_model ./models/base_model.gguf \
  --lora_exclude_header ./models/lora_exclude_header.gguf \
  --lora_exclude_swift ./models/lora_exclude_swift.gguf \
  --gpu_layers 24 \
  --ctx 16384 \
  --enable_4bit_kv_cache \
  --max_workers 1
```

**Intel Mac (안전 설정)**:
```bash
console-llm --mode exclude \
  --file_types both \
  --project ./MyProject \
  --base_model ./models/base_model.gguf \
  --lora_exclude_header ./models/lora_exclude_header.gguf \
  --lora_exclude_swift ./models/lora_exclude_swift.gguf \
  --gpu_layers 0 \
  --ctx 8192 \
  --threads 4 \
  --max_workers 1
```

#### 디버그 모드
개별 JSON 파일도 함께 저장하려면 `--debug` 옵션 추가:
```bash
console-llm --mode exclude \
  --file_types both \
  --project ./MyProject \
  --base_model ./models/base_model.gguf \
  --lora_exclude_header ./models/lora_exclude_header.gguf \
  --lora_exclude_swift ./models/lora_exclude_swift.gguf \
  --debug
```

### 프로그래밍 API 사용

#### 기본 사용법
```python
from console_llm.api import ConsoleLLM

# ConsoleLLM 초기화 (3개 LoRA 어댑터)
analyzer = ConsoleLLM(
    base_model_path="./models/base_model.gguf",
    lora_exclude_header_path="./models/lora_exclude_header.gguf",
    lora_exclude_swift_path="./models/lora_exclude_swift.gguf", 
    lora_sensitive_path="./models/lora_sensitive.gguf",
    n_ctx=16384,
    n_gpu_layers=24,
    enable_4bit_kv_cache=True
)

# Header + Swift 파일 Exclude 분석
exclude_result = analyzer.analyze_exclude(
    project_path="./MyProject",
    file_types=['both']
)

# Sensitive 분석 (Swift만)
sensitive_result = analyzer.analyze_sensitive(
    project_path="./MyProject"
)

# 모든 분석 실행
all_results = analyzer.analyze_all(
    project_path="./MyProject"
)

print(f"Exclude: {exclude_result['total_files_analyzed']} 파일 분석")
print(f"Sensitive: {sensitive_result['files_analyzed']} 파일 분석")
```

#### 파일 타입별 분석
```python
# Header 파일만 분석
header_results = analyzer.analyze_exclude_headers_only(
    project_path="./MyProject"
)

# Swift 파일만 exclude 분석
swift_exclude_results = analyzer.analyze_exclude_swift_only(
    project_path="./MyProject"
)
```

#### 배치 분석
```python
from console_llm.api import ConsoleLLM

analyzer = ConsoleLLM(
    base_model_path="./models/base_model.gguf",
    lora_exclude_header_path="./models/lora_exclude_header.gguf",
    lora_exclude_swift_path="./models/lora_exclude_swift.gguf",
    lora_sensitive_path="./models/lora_sensitive.gguf"
)

# 여러 프로젝트 배치 분석
project_paths = [
    "./Project1",
    "./Project2", 
    "./Project3"
]

batch_results = analyzer.analyze_batch(
    project_paths=project_paths,
    output_base_dir="./batch_results"
)

for project_name, result in batch_results.items():
    print(f"{project_name}: 완료")
```

#### 빠른 분석 (편의 함수)
```python
from console_llm.api import quick_exclude_analysis, quick_sensitive_analysis

# 빠른 Exclude 분석 (Header + Swift)
result = quick_exclude_analysis(
    base_model_path="./models/base_model.gguf",
    lora_exclude_header_path="./models/lora_exclude_header.gguf",
    lora_exclude_swift_path="./models/lora_exclude_swift.gguf",
    project_path="./MyProject",
    file_types=['both']
)

# 빠른 Sensitive 분석
result = quick_sensitive_analysis(
    base_model_path="./models/base_model.gguf",
    lora_sensitive_path="./models/lora_sensitive.gguf",
    project_path="./MyProject"
)
```

## 설정 파일 (swingft_config.json)

```json
{
  "_comment_path": "프로젝트 절대 경로 설정",
  "project": {
    "input": "/path/to/your/project",
    "output": "/path/to/output/directory",
    "build_target": "YourProject"
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
- `--mode`: 분석 모드 (`sensitive`, `exclude`, `all`)
- `--project`: 프로젝트 디렉토리 경로
- `--base_model`: 베이스 모델 GGUF 파일 경로

### 모델 관련 옵션 (v1.1.0 업데이트)
- `--lora_exclude_header`: Header 파일 Exclude LoRA 어댑터 경로
- `--lora_exclude_swift`: Swift 파일 Exclude LoRA 어댑터 경로  
- `--lora_sensitive`: Swift 파일 Sensitive LoRA 어댑터 경로

### 파일 타입 선택 (exclude 모드 전용)
- `--file_types`: 처리할 파일 타입 (`header`, `swift`, `both`)

### 성능 튜닝 옵션
- `--gpu_layers`: GPU에서 처리할 레이어 수 (0-32)
- `--ctx`: 컨텍스트 크기 (토큰 수)
- `--threads`: CPU 스레드 수
- `--max_workers`: 병렬 처리 워커 수
- `--enable_4bit_kv_cache`: 4비트 KV 캐시 활성화 (기본값)
- `--disable_4bit_kv_cache`: 4비트 KV 캐시 비활성화

### 출력 옵션
- `--output_dir`: 출력 디렉토리 경로
- `--debug`: 개별 JSON 파일도 함께 저장

## Header 파일 스마트 분할 기능

ConsoleLLM v1.1.0부터는 큰 헤더 파일을 안전하게 분할하여 처리합니다:

### 분할 기준
- **기본 임계값**: 25KB
- **최소 파트 크기**: 5KB
- **안전한 분할 지점**: 함수, 구조체, 주석 경계를 고려

### 지원 기능
- **다중 인코딩 감지**: UTF-8, Latin-1, CP1252, Mac-Roman
- **구문 인식 분할**: C/Objective-C 문법을 고려한 안전한 분할
- **메타데이터 보존**: 원본 파일 정보와 분할 정보 추적

### 분할 결과 예시
```
Original: LargeFramework.h (50KB)
├── LargeFramework_part1.h (24KB)
├── LargeFramework_part2.h (23KB)  
└── LargeFramework_part3.h (3KB)
```

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

#### Header 파일 결과
```json
{
  "file_path": "/path/to/Header.h",
  "file_type": "header",
  "reasoning": "단계별 분석 근거",
  "identifiers": [
    "NSString",
    "UIViewController", 
    "performSelector"
  ],
  "raw_output": "모델 원본 출력",
  "part_index": 1,
  "total_parts": 3
}
```

#### Swift 파일 결과
```json
{
  "file_path": "/path/to/SwiftFile.swift",
  "file_type": "swift",
  "reasoning": "단계별 분석 근거",
  "identifiers": [
    "viewDidLoad",
    "IBOutlet",
    "delegate"
  ],
  "raw_output": "모델 원본 출력",
  "ast_json": "AST 분석 결과"
}
```

### 요약 결과 (v1.1.0 업데이트)
```json
{
  "mode": "exclude",
  "file_types_processed": ["both"],
  "total_files_analyzed": 15,
  "total_results": 18,
  "successful": 17,
  "failed": 1,
  "header_files_processed": 5,
  "header_results": 8,
  "swift_files_processed": 10,
  "swift_results": 10,
  "total_exclude_identifiers_found": 45,
  "unique_exclude_identifiers": [
    "NSString", "UIViewController", "viewDidLoad"
  ]
}
```

### 출력 디렉토리 구조

#### Exclude 분석 결과
```
output_exclude/
├── exclude_id.txt              # 제외 대상 식별자 목록
├── summary_exclude.json        # 분석 요약
└── [debug 모드시]
    ├── Header1_exclude.json           # Header 파일 결과
    ├── LargeHeader_part1_exclude.json # 분할된 Header 파일 결과
    ├── LargeHeader_part2_exclude.json
    └── SwiftFile_exclude.json         # Swift 파일 결과
```

#### 전체 분석 결과 (all 모드)
```
output_all/
├── exclude/
│   ├── exclude_id.txt
│   └── summary_exclude.json
└── sensitive/
    ├── sensitive_id.txt
    └── summary_sensitive.json
```

## 내부망 배포 (Offline/Internal Network Deployment)

인터넷 연결이 제한된 내부망 환경을 위해, 모든 의존성과 모델이 포함된 올인원(All-in-one) 패키지를 제공합니다.

### 패키지 구조 (v1.1.0 업데이트)

#### Apple Silicon용 패키지
```
ConsoleLLM_AppleSilicon_v1.1.0.zip
├── console_llm/                    # ConsoleLLM 소스 코드
├── dependencies/                   # 오프라인 의존성
│   └── llama_cpp_python-*.whl     # Apple Silicon용 wheel 파일
├── models/                         # AI 모델 파일 (v1.1.0)
│   ├── base_model.gguf
│   ├── lora_exclude_header.gguf    # Header용 LoRA (신규)
│   ├── lora_exclude_swift.gguf     # Swift용 LoRA (신규)
│   └── lora_sensitive.gguf
├── install_apple.sh               # Apple Silicon 설치 스크립트
├── setup.py                       # 패키지 설정
├── requirements.txt               # 의존성 목록
└── README_AppleSilicon.md          # Apple Silicon 전용 설명서
```

### 배포 절차

#### 1. 패키지 전달 및 압축 해제
```bash
# 패키지 압축 해제
unzip ConsoleLLM_AppleSilicon_v1.1.0.zip
cd ConsoleLLM_AppleSilicon_v1.1.0
```

#### 2. 설치 스크립트 실행 (v1.1.0 업데이트)
```bash
# Apple Silicon Mac
chmod +x install_apple.sh
bash install_apple.sh

# Intel Mac  
chmod +x install_intel.sh
bash install_intel.sh
```

#### 3. 설치 확인
```bash
console-llm --help
```

### 설치 스크립트 내부 동작 (v1.1.0 업데이트)

#### `install_apple.sh` 스크립트 예시
```bash
#!/bin/bash
# Apple Silicon용 ConsoleLLM v1.1.0 설치 스크립트

echo "🚀 Apple Silicon용 ConsoleLLM v1.1.0 설치를 시작합니다."

# 1. 패키지에 포함된 오프라인 의존성 설치
echo "📦 오프라인 의존성을 설치합니다: llama-cpp-python"
pip install dependencies/llama_cpp_python-*-macosx_11_0_arm64.whl

# 2. ConsoleLLM 패키지 설치 (개발 모드)
echo "🔧 ConsoleLLM을 설치합니다."
pip install -e .

# 3. AST 분석기에 실행 권한 부여
echo "🔑 AST 분석기에 실행 권한을 부여합니다."
chmod +x console_llm/ast_analyzers/*/SwiftASTAnalyzer

# 4. 모델 파일 확인
echo "📋 모델 파일을 확인합니다."
ls -la models/

echo "✅ 설치가 완료되었습니다."
echo "📖 사용법: console-llm --help"
echo "📖 예시: console-llm --mode exclude --file_types both --project ./MyProject --base_model ./models/base_model.gguf --lora_exclude_header ./models/lora_exclude_header.gguf --lora_exclude_swift ./models/lora_exclude_swift.gguf"
```

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
**원인**: 컨텍스트 크기 부족 (특히 큰 헤더 파일)
**해결**:
```bash
--ctx 32768  # 더 큰 컨텍스트
```

#### 3. AST Analysis Failed
**원인**: AST 분석기 권한 문제 (Swift 파일 분석시)
**해결**:
```bash
chmod +x console_llm/ast_analyzers/*/SwiftASTAnalyzer
```

#### 4. LoRA Loading Failed
**원인**: 잘못된 LoRA 어댑터 사용
**해결**:
- Header 파일: `--lora_exclude_header` 사용
- Swift 파일: `--lora_exclude_swift` 또는 `--lora_sensitive` 사용
- 파일 타입에 맞는 어댑터 확인

#### 5. Header File Encoding Error
**원인**: 지원되지 않는 인코딩
**해결**: 자동으로 다중 인코딩 시도 (UTF-8, Latin-1, CP1252, Mac-Roman)

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

### 모듈 구조 (v1.1.0 업데이트)

- **core**: 핵심 기능 (모델 로더, 베이스 분석기)
- **analyzers**: 모드별 분석기 
  - `ExcludeAnalyzer`: Header + Swift 파일 exclude 분석
  - `SensitiveAnalyzer`: Swift 파일 sensitive 분석
- **api**: 외부 인터페이스 (CLI, 프로그래밍 API)

### 새로운 분석 모드 추가

1. `console_llm/analyzers/`에 새로운 분석기 클래스 생성
2. `BaseAnalyzer`를 상속하여 구현
3. `api.py`에 해당 모드 추가
4. CLI에 옵션 추가

## 버전 히스토리

### v1.1.0 (현재)
- 3개 LoRA 어댑터 지원 (Header, Swift, Sensitive)
- Header 파일 스마트 분할 기능
- 파일 타입별 선택 처리
- 다중 인코딩 지원

### v1.0.0 (이전)
- 2개 LoRA 어댑터 (Exclude, Sensitive)
- Swift 파일만 지원

## 라이선스

MIT License

## 지원 및 문의

프로젝트 관련 문의사항이나 이슈는 GitHub Issues를 통해 제보해 주세요.

---

**ConsoleLLM v1.1.0** - Swift/Objective-C 코드 보안 분석의 새로운 표준