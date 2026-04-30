import importlib.util
from functools import lru_cache
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import DiscussionPipelineResult


@require_GET
def index(request):
    company = request.GET.get("company", "").strip()
    if not company:
        if _wants_json_response(request):
            return JsonResponse(
                {"error": "company query parameter is required"},
                status=400,
            )
        return render(request, "naver/index.html", {"default_limit": 20})

    try:
        limit = _parse_limit(request.GET.get("limit", 20))
    except ValueError as exc:
        return _error_response(request, str(exc), status=400, company=company)

    crawler = _load_crawler()

    try:
        collected = crawler.fetch_discussion_data(company, limit=limit)
        original_comments = collected["titles"]
        cleaned_comments, iqr_thresholds = crawler.preprocess_comments(
            original_comments
        )
        augmented_comments = crawler.augment_comments(cleaned_comments)
        integrated_data = crawler.build_integrated_dataset(
            original_comments,
            cleaned_comments,
            augmented_comments,
        )
    except crawler.StockNotFoundError as exc:
        return _error_response(request, str(exc), status=404, company=company)
    except crawler.CrawlerError as exc:
        return _error_response(request, str(exc), status=502, company=company)
    except ValueError as exc:
        return _error_response(request, str(exc), status=400, company=company)

    pipeline_result = DiscussionPipelineResult.objects.create(
        requested_company_name=company,
        actual_stock_name=collected["actual_stock_name"],
        stock_code=collected.get("stock_code", ""),
        original_comments=original_comments,
        cleaned_comments=cleaned_comments,
        augmented_comments=augmented_comments,
        integrated_data=integrated_data,
        iqr_thresholds=iqr_thresholds,
    )

    payload = _build_payload(
        pipeline_result,
        company,
        original_comments,
        cleaned_comments,
        augmented_comments,
        integrated_data,
        iqr_thresholds,
    )

    if _wants_json_response(request):
        return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})

    return render(
        request,
        "naver/index.html",
        {
            "default_limit": limit,
            "company": company,
            "result": payload,
        },
    )


def _parse_limit(raw_limit):
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc

    if limit < 1:
        raise ValueError("limit must be greater than 0")

    return min(limit, 100)


def _build_payload(
    pipeline_result,
    company,
    original_comments,
    cleaned_comments,
    augmented_comments,
    integrated_data,
    iqr_thresholds,
):
    return {
        "id": pipeline_result.id,
        "requirement_number": pipeline_result.requirement_number,
        "company": company,
        "actual_stock_name": pipeline_result.actual_stock_name,
        "stock_code": pipeline_result.stock_code,
        "count": len(original_comments),
        "titles": original_comments,
        "original_comments": original_comments,
        "cleaned_comments": cleaned_comments,
        "augmented_comments": augmented_comments,
        "integrated_data": integrated_data,
        "iqr_thresholds": iqr_thresholds,
        "created_at": pipeline_result.created_at.isoformat(),
    }


def _error_response(request, message, status, company=""):
    if _wants_json_response(request):
        return JsonResponse(
            {"error": message},
            status=status,
            json_dumps_params={"ensure_ascii": False},
        )

    return render(
        request,
        "naver/index.html",
        {
            "default_limit": 20,
            "company": company,
            "error": message,
        },
        status=status,
    )


def _wants_json_response(request):
    if request.GET.get("format") == "json":
        return True

    accept = request.headers.get("Accept", "")
    return "application/json" in accept


@lru_cache(maxsize=1)
def _load_crawler():
    crawler_path = Path(__file__).resolve().parents[1] / "naver.py"
    spec = importlib.util.spec_from_file_location("naver_discussion_crawler", crawler_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
