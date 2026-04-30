from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase

from . import views
from .models import DiscussionPipelineResult


class NaverViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch("pjt06.naver.views._load_crawler")
    def test_company_is_required_and_does_not_collect(self, mock_load_crawler):
        response = views.index(self.factory.get("/naver/", {"format": "json"}))

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"company query parameter is required", response.content)
        self.assertFalse(mock_load_crawler.called)
        self.assertEqual(DiscussionPipelineResult.objects.count(), 0)

    @mock.patch("pjt06.naver.views._load_crawler")
    def test_empty_browser_request_shows_form_and_does_not_collect(
        self, mock_load_crawler
    ):
        response = views.index(self.factory.get("/naver/"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="company"', response.content)
        self.assertFalse(mock_load_crawler.called)
        self.assertEqual(DiscussionPipelineResult.objects.count(), 0)

    @mock.patch("pjt06.naver.views._load_crawler")
    def test_collects_processes_and_stores_pipeline_result(self, mock_load_crawler):
        class CrawlerError(Exception):
            pass

        class StockNotFoundError(CrawlerError):
            pass

        mock_load_crawler.return_value = SimpleNamespace(
            CrawlerError=CrawlerError,
            StockNotFoundError=StockNotFoundError,
            fetch_discussion_data=mock.Mock(
                return_value={
                    "stock_code": "005930",
                    "actual_stock_name": "Samsung Electronics",
                    "titles": ["title 1!!!", "title 2"],
                }
            ),
            preprocess_comments=mock.Mock(
                return_value=(["title 1!", "title 2"], {"lower": 3, "upper": None})
            ),
            augment_comments=mock.Mock(return_value=["expanded title 1"]),
            build_integrated_dataset=mock.Mock(
                return_value=[
                    {"stage": "original", "text": "title 1!!!"},
                    {"stage": "cleaned", "text": "title 1!"},
                    {"stage": "augmented", "text": "expanded title 1"},
                ]
            ),
        )

        response = views.index(
            self.factory.get(
                "/naver/",
                {"company": "Samsung", "limit": "2", "format": "json"},
            )
        )

        result = DiscussionPipelineResult.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result.requirement_number, "F102")
        self.assertEqual(result.requested_company_name, "Samsung")
        self.assertEqual(result.actual_stock_name, "Samsung Electronics")
        self.assertEqual(result.stock_code, "005930")
        self.assertEqual(result.original_comments, ["title 1!!!", "title 2"])
        self.assertEqual(result.cleaned_comments, ["title 1!", "title 2"])
        self.assertEqual(result.augmented_comments, ["expanded title 1"])
        self.assertEqual(result.integrated_data[0]["stage"], "original")
        self.assertEqual(result.integrated_data[2]["stage"], "augmented")
        self.assertIn(b'"id":', response.content)
        self.assertIn(b'"integrated_data":', response.content)

    @mock.patch("pjt06.naver.views._load_crawler")
    def test_browser_request_renders_pipeline_result(self, mock_load_crawler):
        class CrawlerError(Exception):
            pass

        class StockNotFoundError(CrawlerError):
            pass

        mock_load_crawler.return_value = SimpleNamespace(
            CrawlerError=CrawlerError,
            StockNotFoundError=StockNotFoundError,
            fetch_discussion_data=mock.Mock(
                return_value={
                    "stock_code": "005930",
                    "actual_stock_name": "Samsung Electronics",
                    "titles": ["title 1!!!", "title 2"],
                }
            ),
            preprocess_comments=mock.Mock(
                return_value=(
                    ["title 1!", "title 2"],
                    {
                        "lower": 3,
                        "upper": None,
                        "inappropriate_filter": {"used_llm": True},
                    },
                )
            ),
            augment_comments=mock.Mock(return_value=["expanded title 1"]),
            build_integrated_dataset=mock.Mock(
                return_value=[
                    {"stage": "original", "stage_label": "원본", "text": "title 1!!!"},
                    {"stage": "cleaned", "stage_label": "전처리", "text": "title 1!"},
                    {
                        "stage": "augmented",
                        "stage_label": "증강",
                        "text": "expanded title 1",
                    },
                ]
            ),
        )

        response = views.index(
            self.factory.get("/naver/", {"company": "Samsung", "limit": "2"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("원본 제목 목록".encode(), response.content)
        self.assertIn(b"title 1!!!", response.content)
        self.assertIn("통합 데이터 결과".encode(), response.content)
        self.assertIn(b"expanded title 1", response.content)

    @mock.patch("pjt06.naver.views._load_crawler")
    def test_unknown_company_returns_message_and_does_not_store(self, mock_load_crawler):
        class CrawlerError(Exception):
            pass

        class StockNotFoundError(CrawlerError):
            pass

        message = "존재하지 않는 회사 명 이거나 국내에 상장되지 않았습니다"
        mock_load_crawler.return_value = SimpleNamespace(
            CrawlerError=CrawlerError,
            StockNotFoundError=StockNotFoundError,
            fetch_discussion_data=mock.Mock(side_effect=StockNotFoundError(message)),
        )

        response = views.index(
            self.factory.get(
                "/naver/",
                {"company": "없는회사명입니다", "format": "json"},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(message.encode(), response.content)
        self.assertEqual(DiscussionPipelineResult.objects.count(), 0)

    def test_first_domestic_stock_code_uses_top_result(self):
        crawler = views._load_crawler()
        page_source = """
            <a href="/item/main.naver?code=005930">삼성전자</a>
            <a href="/item/main.naver?code=000830">삼성물산</a>
        """

        self.assertEqual(
            crawler._extract_first_domestic_stock_code(page_source),
            "005930",
        )

    def test_first_autocomplete_stock_code_uses_top_suggestion(self):
        crawler = views._load_crawler()
        page_source = """
            <a href="#">005930 삼성 전자 코스피</a>
            <a href="#">006400 삼성 SDI 코스피</a>
        """

        self.assertEqual(
            crawler._extract_first_autocomplete_stock_code(page_source),
            "005930",
        )

    def test_extract_titles_removes_comment_count_suffix(self):
        crawler = views._load_crawler()
        page_source = """
            <table class="type2">
              <a href="/item/board_read.naver?code=005930&nid=1">첫 제목 [12]</a>
              <a href="/item/board_read.naver?code=005930&nid=2">어느날 갑자기... [ 2 ]</a>
            </table>
        """

        self.assertEqual(
            crawler._extract_titles(page_source, limit=20),
            ["첫 제목", "어느날 갑자기..."],
        )

    def test_clean_comment_removes_spaced_comment_count_suffix(self):
        crawler = views._load_crawler()

        self.assertEqual(
            crawler._clean_comment("어느날 갑자기... [ 2 ]"),
            "어느날 갑자기...",
        )

    def test_llm_filter_can_remove_political_and_union_related_titles(self):
        crawler = views._load_crawler()
        comments = ["실적 개선 기대", "정치권 이슈", "노조 파업 관련"]

        with mock.patch.object(
            crawler,
            "_call_inappropriate_filter_llm",
            return_value="[1, 2]",
        ):
            filtered, info = crawler.filter_inappropriate_comments(comments)

        self.assertEqual(filtered, ["실적 개선 기대"])
        self.assertEqual(info["removed_comments"], ["정치권 이슈", "노조 파업 관련"])
        self.assertIn("정치적 내용", info["excluded_categories"])
        self.assertIn("노조 관련 내용", info["excluded_categories"])
