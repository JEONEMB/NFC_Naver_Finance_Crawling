import json
import re
import os
import shutil
import tempfile
from math import floor
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
NAVER_FINANCE_HOME = "https://finance.naver.com/"
STOCK_CODE_RE = re.compile(r"code=(\d{6})")
AUTOCOMPLETE_STOCK_RE = re.compile(r"^\s*(\d{6})\s+")
STOCK_NOT_FOUND_MESSAGE = "존재하지 않는 회사 명 이거나 국내에 상장되지 않았습니다"


class CrawlerError(Exception):
    """Raised when Naver Finance cannot be crawled."""


class StockNotFoundError(CrawlerError):
    """Raised when a matching domestic stock cannot be found."""


def fetch_discussion_titles(company_name, limit=20, timeout=15):
    """Fetch post titles from the Naver Finance stock discussion board."""
    return fetch_discussion_data(company_name, limit=limit, timeout=timeout)["titles"]


def fetch_discussion_data(company_name, limit=20, timeout=15):
    """Fetch stock metadata and post titles from Naver Finance."""
    company_name = (company_name or "").strip()
    if not company_name:
        raise ValueError("company_name is required")

    limit = _normalize_limit(limit)
    driver = _build_driver()

    try:
        stock_code = _search_stock_code(driver, company_name, timeout)
        board_url = f"{NAVER_FINANCE_HOME}item/board.naver?code={stock_code}"
        driver.get(board_url)

        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.type2"))
        )

        page_source = driver.page_source
        return {
            "stock_code": stock_code,
            "actual_stock_name": _extract_stock_name(page_source) or company_name,
            "titles": _extract_titles(page_source, limit),
        }
    except StockNotFoundError:
        raise
    except TimeoutException as exc:
        raise CrawlerError("Timed out while loading Naver Finance") from exc
    except WebDriverException as exc:
        raise CrawlerError(f"Selenium failed: {exc.msg}") from exc
    finally:
        temp_user_data_dir = getattr(driver, "_temp_user_data_dir", None)
        driver.quit()
        if temp_user_data_dir:
            shutil.rmtree(temp_user_data_dir, ignore_errors=True)


def _normalize_limit(limit):
    try:
        parsed = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc

    if parsed < 1:
        raise ValueError("limit must be greater than 0")

    return min(parsed, 100)


def _build_driver():
    chromedriver_path = _resolve_chromedriver_path()
    if not chromedriver_path:
        searched_paths = ", ".join(str(path) for path in _candidate_chromedriver_paths())
        raise CrawlerError(f"ChromeDriver not found. Searched: {searched_paths}")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--window-size=1280,1200")
    temp_user_data_dir = tempfile.mkdtemp(prefix="naver-finance-chrome-")
    options.add_argument(f"--user-data-dir={temp_user_data_dir}")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    service = Service(str(chromedriver_path))
    try:
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        shutil.rmtree(temp_user_data_dir, ignore_errors=True)
        raise

    driver._temp_user_data_dir = temp_user_data_dir
    return driver


def _resolve_chromedriver_path():
    for candidate in _candidate_chromedriver_paths():
        if candidate.is_file():
            return candidate

    return None


def _candidate_chromedriver_paths():
    candidates = [
        PROJECT_ROOT / "chromedriver-win64" / "chromedriver.exe",
        PROJECT_ROOT.parent / "chromedriver-win64" / "chromedriver.exe",
    ]

    env_path = _normalize_chromedriver_path(os.getenv("CHROMEDRIVER_PATH"))
    if env_path:
        candidates.append(env_path)

    unique_candidates = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)

    return unique_candidates


def _normalize_chromedriver_path(raw_path):
    if not raw_path:
        return None

    path = Path(raw_path.strip().strip('"').strip("'")).expanduser()
    if path.name.lower() == "chromedriver.exe":
        return path

    return path / "chromedriver.exe"


def _search_stock_code(driver, company_name, timeout):
    driver.get(NAVER_FINANCE_HOME)
    home_url = driver.current_url
    search_url = _build_search_url(company_name)

    try:
        search_input = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#stock_items"))
        )
        search_input.clear()
        search_input.send_keys(company_name)

        try:
            return WebDriverWait(driver, min(3, timeout)).until(
                lambda d: _extract_first_autocomplete_stock_code(d.page_source)
            )
        except TimeoutException:
            pass

        search_input.send_keys(Keys.ENTER)
        WebDriverWait(driver, timeout).until(
            lambda d: d.current_url != home_url
            or STOCK_CODE_RE.search(d.current_url)
        )
    except TimeoutException:
        driver.get(search_url)

    code = _extract_stock_code(driver.current_url)
    if code:
        return code

    if "search.naver" not in driver.current_url:
        driver.get(search_url)

    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    code = _extract_first_domestic_stock_code(driver.page_source)
    if not code:
        raise StockNotFoundError(STOCK_NOT_FOUND_MESSAGE)

    return code


def _build_search_url(company_name):
    return f"{NAVER_FINANCE_HOME}search/search.naver?query={quote(company_name)}"


def _extract_stock_code(text):
    match = STOCK_CODE_RE.search(text or "")
    if not match:
        return None
    return match.group(1)


def _extract_first_domestic_stock_code(page_source):
    soup = BeautifulSoup(page_source, "html.parser")

    for link in soup.select("a[href*='item/main.naver?code=']"):
        code = _extract_stock_code(link.get("href", ""))
        if code:
            return code

    return None


def _extract_first_autocomplete_stock_code(page_source):
    soup = BeautifulSoup(page_source, "html.parser")

    for link in soup.find_all("a", href="#"):
        text = " ".join(link.get_text(" ", strip=True).split())
        match = AUTOCOMPLETE_STOCK_RE.match(text)
        if match:
            return match.group(1)

    return None


def _extract_titles(page_source, limit):
    soup = BeautifulSoup(page_source, "html.parser")
    titles = []

    for link in soup.select("table.type2 a[href*='board_read.naver']"):
        title = _normalize_title(link.get_text(" ", strip=True))
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= limit:
            break

    return titles


def _normalize_title(title):
    title = " ".join(str(title or "").split())
    title = re.sub(r"\s*\[\s*\d+\s*\]\s*$", "", title)
    return title.strip()


def _extract_stock_name(page_source):
    soup = BeautifulSoup(page_source, "html.parser")

    for selector in (".wrap_company h2 a", ".wrap_company h2", "#middle h2"):
        element = soup.select_one(selector)
        if element:
            name = " ".join(element.get_text(" ", strip=True).split())
            if name:
                return name

    title = soup.select_one("title")
    if not title:
        return None

    page_title = title.get_text(" ", strip=True)
    if ":" in page_title:
        return page_title.split(":", 1)[0].strip()

    return None


def preprocess_comments(comments):
    """Clean collected titles/comments and calculate IQR threshold metadata."""
    cleaned = []
    for comment in comments:
        text = _clean_comment(comment)
        if text and text not in cleaned:
            cleaned.append(text)

    llm_filtered, moderation_info = filter_inappropriate_comments(cleaned)
    iqr_filtered, iqr_info = _filter_by_iqr(llm_filtered)
    iqr_info["inappropriate_filter"] = moderation_info
    return iqr_filtered, iqr_info


def filter_inappropriate_comments(comments):
    """Remove inappropriate comments using an LLM when API credentials exist."""
    if not comments:
        return [], {
            "used_llm": False,
            "removed_indices": [],
            "removed_comments": [],
            "reason": "empty input",
        }

    try:
        response_text = _call_inappropriate_filter_llm(comments)
        indexes = _parse_llm_indexes(response_text, len(comments))
    except Exception as exc:
        return comments, {
            "used_llm": False,
            "removed_indices": [],
            "removed_comments": [],
            "reason": str(exc),
        }

    removed_index_set = set(indexes)
    filtered = [
        comment for index, comment in enumerate(comments)
        if index not in removed_index_set
    ]

    return filtered, {
        "used_llm": True,
        "removed_indices": indexes,
        "removed_comments": [comments[index] for index in indexes],
        "excluded_categories": [
            "욕설",
            "혐오",
            "비방",
            "선정성",
            "과도한 비난",
            "정치적 내용",
            "노조 관련 내용",
        ],
        "prompt": "다음 댓글 목록에서 부적절하거나 정치적이거나 노조 관련 댓글의 번호(0부터 시작)만 JSON 배열로 알려줘",
    }


def augment_comments(comments):
    """Create meaning-preserving expanded title data."""
    if not comments:
        return []

    try:
        augmented = _call_augmentation_llm(comments)
        if augmented:
            return augmented
    except Exception:
        pass

    return _fallback_augment_comments(comments)


def build_integrated_dataset(original_comments, cleaned_comments, augmented_comments):
    """Combine each pipeline stage into one stage-aware result set."""
    integrated = []

    for index, text in enumerate(original_comments):
        integrated.append(
            {
                "stage": "original",
                "stage_label": "원본",
                "source_index": index,
                "text": text,
            }
        )

    for index, text in enumerate(cleaned_comments):
        integrated.append(
            {
                "stage": "cleaned",
                "stage_label": "전처리",
                "source_index": index,
                "text": text,
            }
        )

    for index, text in enumerate(augmented_comments):
        integrated.append(
            {
                "stage": "augmented",
                "stage_label": "증강",
                "source_index": index,
                "text": text,
            }
        )

    return integrated


def _fallback_augment_comments(comments):
    """Create deterministic variants when LLM augmentation is unavailable."""
    augmented = []
    for comment in comments:
        normalized = re.sub(r"\s+", " ", comment).strip()
        without_repeated_marks = re.sub(r"([!?\.])\1+", r"\1", normalized)
        without_brackets = re.sub(r"\[[^\]]+\]|\([^\)]*\)", "", without_repeated_marks)
        base = without_brackets.strip() or without_repeated_marks
        variants = [
            without_repeated_marks,
            base,
            f"{base} 관련 의견",
        ]

        for variant in variants:
            if variant and variant != comment and variant not in augmented:
                augmented.append(variant)

    return augmented


def _clean_comment(comment):
    text = _normalize_title(comment)
    text = re.sub(r"[^가-힣a-zA-Z0-9\s!?.,%+-]", " ", text)
    text = re.sub(r"(ㅋ|ㅎ|ㅠ|ㅜ){3,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    if len(text) < 3:
        return ""

    if re.fullmatch(r"\d+", text):
        return ""

    if re.fullmatch(r"[ㅋㅎㅠㅜ\s]+", text):
        return ""

    if re.fullmatch(r"[A-Za-z\s]+", text):
        return ""

    if text.lower() == "none":
        return ""

    return text


def _call_inappropriate_filter_llm(comments):
    from dotenv import load_dotenv
    from langchain.chat_models import init_chat_model

    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise CrawlerError("OPENAI_API_KEY is not configured")

    model = os.getenv("MODEL", "gpt-4o-mini")
    numbered = "\n".join(f"{index}. {comment}" for index, comment in enumerate(comments))
    prompt = f"""
다음 댓글 목록에서 제외해야 할 댓글의 번호(0부터 시작)만 JSON 배열로 알려줘.
제외 대상:
- 욕설, 혐오, 비방, 선정성, 과도한 비난
- 정치적 내용, 특정 정당/이념/정치인 관련 내용
- 노조, 파업, 쟁의, 노사갈등 등 노조 관련 내용
응답은 반드시 [0, 2] 또는 [] 같은 JSON 배열만 반환해.

댓글 목록:
{numbered}
"""

    llm = init_chat_model(model, model_provider="openai", api_key=api_key)
    result = llm.invoke([{"role": "user", "content": prompt}])
    return result.content


def _call_augmentation_llm(comments):
    from dotenv import load_dotenv
    from langchain.chat_models import init_chat_model

    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise CrawlerError("OPENAI_API_KEY is not configured")

    model = os.getenv("MODEL", "gpt-4o-mini")
    numbered = "\n".join(f"{index}. {comment}" for index, comment in enumerate(comments))
    prompt = f"""
다음 제목 목록의 의미를 유지하면서, 학습/분석에 활용할 수 있도록 각각을 자연스러운 한국어 문장으로 조금 더 구체화해줘.
- 원래 제목의 핵심 의미와 감정 방향은 바꾸지 마.
- 각 입력 제목마다 증강 문장 1개만 만들어줘.
- 응답은 반드시 JSON 문자열 배열만 반환해. 예: ["문장1", "문장2"]

제목 목록:
{numbered}
"""

    llm = init_chat_model(model, model_provider="openai", api_key=api_key)
    result = llm.invoke([{"role": "user", "content": prompt}])
    augmented = json.loads(str(result.content).strip())
    if not isinstance(augmented, list):
        raise ValueError("LLM augmentation response must be a JSON array")

    cleaned = []
    for item in augmented:
        text = str(item or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)

    return cleaned


def _parse_llm_indexes(response_text, comment_count):
    indexes = json.loads(str(response_text).strip())
    if not isinstance(indexes, list):
        raise ValueError("LLM response must be a JSON array")

    normalized = []
    for index in indexes:
        if isinstance(index, bool):
            continue
        if isinstance(index, (int, float)):
            parsed = int(index)
            if 0 <= parsed < comment_count and parsed not in normalized:
                normalized.append(parsed)

    return normalized


def _filter_by_iqr(comments):
    lengths = [len(comment) for comment in comments]
    if not lengths:
        return [], {
            "q1": None,
            "q3": None,
            "iqr": None,
            "lower": None,
            "upper": None,
            "removed_count": 0,
        }

    if len(comments) < 5:
        filtered = [comment for comment in comments if len(comment) >= 3]
        return filtered, {
            "q1": None,
            "q3": None,
            "iqr": None,
            "lower": 3,
            "upper": None,
            "removed_count": len(comments) - len(filtered),
        }

    q1 = _percentile(lengths, 25)
    q3 = _percentile(lengths, 75)
    iqr = q3 - q1
    lower = max(3, q1 - 1.5 * iqr)
    upper = q3 + 1.5 * iqr
    filtered = [comment for comment in comments if lower <= len(comment) <= upper]

    return filtered, {
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lower": lower,
        "upper": upper,
        "removed_count": len(comments) - len(filtered),
    }


def _percentile(values, percentile):
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    position = (len(sorted_values) - 1) * (percentile / 100)
    lower_index = floor(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    return lower_value + (upper_value - lower_value) * fraction


if __name__ == "__main__":
    for title in fetch_discussion_titles("삼성전자", limit=5):
        print(title)
