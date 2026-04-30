# 💸💸네이버증권 종목토론 데이터 파이프라인

## 프로젝트 소개

회사명을 입력하면 네이버증권에서 국내 상장 종목을 검색하고, 종목토론 게시판의 게시글 제목을 수집해 전처리, 필터링, 데이터 증강, 통합 저장까지 수행하는 Django 기반 데이터 파이프라인 프로젝트입니다.

브라우저 자동화와 HTML 파싱을 함께 사용해 동적 페이지에서 필요한 데이터를 안정적으로 가져오고, 수집 결과를 웹 화면과 JSON 응답으로 확인할 수 있도록 구성했습니다.

## 개발기간

2026.04.30

## 팀원소개

| 이름 | 역할 |
| --- | --- |
| 전희창 | 데이터 수집 및 크롤링 로직 구현 |
| 성하빈 | Django 웹 화면 및 결과 저장 기능 구현 |
| 정준오 | 데이터 전처리, 필터링, 테스트 및 문서화 |

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| Backend | Python, Django |
| Crawling | Selenium, BeautifulSoup4 |
| Data Processing | re, JSONField, IQR 기반 필터링 |
| LLM | LangChain, OpenAI API |
| Database | SQLite |
| Browser Driver | ChromeDriver |
| Test | Django TestCase, unittest.mock |

## 주요기능

- 회사명 기반 네이버증권 종목 검색
- 검색 결과에서 국내 상장 종목 코드 추출
- 종목토론 게시판 제목 수집
- 중복 제목 제거 및 댓글 수 표기 제거
- 부적절하거나 분석 목적에 맞지 않는 제목 필터링
- IQR 기준을 활용한 길이 기반 이상치 필터링
- LLM 기반 의미 보존 텍스트 증강
- 원본, 전처리, 증강 데이터를 하나의 통합 데이터셋으로 저장
- 웹 화면 결과 출력 및 JSON 응답 지원

## 프로젝트 구조

```text
pjt_6/
+-- chromedriver-win64/
|   +-- chromedriver.exe
|   +-- LICENSE.chromedriver
|   +-- THIRD_PARTY_NOTICES.chromedriver
+-- pjt06/
|   +-- naver/
|   |   +-- migrations/
|   |   +-- templates/
|   |   |   +-- naver/
|   |   |       +-- index.html
|   |   +-- admin.py
|   |   +-- apps.py
|   |   +-- models.py
|   |   +-- tests.py
|   |   +-- urls.py
|   |   +-- views.py
|   +-- naver.py
|   +-- settings.py
|   +-- urls.py
|   +-- wsgi.py
+-- manage.py
+-- requirements.txt
+-- README.md
```

## 실행방법

### 1. 프로젝트 클론

```bash
git clone <repository-url>
cd NFC_Naver_Finance_Crawling
```

### 2. 가상환경 생성 및 활성화

```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. 패키지 설치

```powershell
pip install -r requirements.txt
```

### 4. 환경변수 파일 생성

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
MODEL="gpt-5-nano"
OPENAI_API_KEY="발급받은_API_KEY"
```

`.env` 파일은 개인 API 키를 포함하므로 Git에 커밋하지 않습니다.

### 5. DB 마이그레이션

```powershell
python manage.py migrate
```

### 6. 개발 서버 실행

```powershell
python manage.py runserver 127.0.0.1:8001
```

브라우저에서 아래 주소로 접속합니다.

```text
http://127.0.0.1:8001/naver/
```

JSON 응답은 다음 형식으로 확인할 수 있습니다.

```text
http://127.0.0.1:8001/naver/?company=삼성전자&limit=20&format=json
```

## 트러블 슈팅

### ChromeDriver not found

```text
ChromeDriver not found: C:\...\chromedriver.exe
```

원인:

- 서버를 현재 프로젝트 폴더가 아닌 다른 폴더에서 실행한 경우
- `CHROMEDRIVER_PATH` 환경변수가 예전 경로를 가리키는 경우
- `chromedriver-win64/chromedriver.exe` 파일이 없는 경우

해결:

```powershell
cd <clone받은_프로젝트_경로>\pjt_6
python manage.py runserver 127.0.0.1:8001
```

또는 프로젝트 내부에 아래 파일이 있는지 확인합니다.

```text
chromedriver-win64/chromedriver.exe
```

### no such table 오류

```text
no such table: naver_discussionpipelineresult
```

원인:

- DB 마이그레이션을 실행하지 않은 상태에서 서버를 실행한 경우

해결:

```powershell
python manage.py migrate
```

### ChromeDriver와 Chrome 버전 불일치

원인:

- 설치된 Chrome 브라우저 버전과 ChromeDriver 버전이 맞지 않는 경우

해결:

- 현재 PC의 Chrome 버전에 맞는 ChromeDriver로 `chromedriver-win64/chromedriver.exe`를 교체합니다.

### OpenAI API Key 오류

원인:

- `.env` 파일이 없거나 `OPENAI_API_KEY` 값이 설정되지 않은 경우

해결:

```env
MODEL="gpt-5-nano"
OPENAI_API_KEY="발급받은_API_KEY"
```

## 향후 개선 사항

- ChromeDriver를 직접 포함하지 않고 Selenium Manager 기반으로 자동 관리
- 비동기 작업 큐를 도입해 긴 수집 작업의 응답성 개선
- 수집 결과 검색, 필터링, 다운로드 기능 추가
- 종목별 수집 이력 비교 화면 구현
- 크롤링 실패 시 재시도 및 상세 로그 저장
- LLM 필터링 기준을 관리자가 수정할 수 있는 설정 화면 추가
- 배포 환경용 설정 분리 및 보안 설정 강화
