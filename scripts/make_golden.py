"""Sinh bộ đề đánh giá tất định từ artifact đã build (SPEC §11).

Không dùng LLM: câu hỏi sinh theo mẫu từ node/chunk thật, nên chạy lại cho ra cùng bộ đề
(`generator: template_v1`). Người dùng kiểm duyệt tay trước khi đóng băng ở CP3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from src.common.paths import EVAL_DIR, PROCESSED_DIR, REPO_ROOT

DEFAULT_DOC = "18-VBHN-VPQH-2026"
FALLBACK_DOC = "45-2019-QH14"
TOTAL_QA = 200
OOS_QUESTIONS = (
    "Thuế thu nhập doanh nghiệp của công ty có vốn Hàn Quốc là bao nhiêu?",
    "Thủ tục ly hôn đơn phương cần những giấy tờ gì?",
    "Mức phạt vi phạm giao thông khi vượt đèn đỏ là bao nhiêu?",
    "Điều kiện thành lập công ty cổ phần theo Luật Doanh nghiệp là gì?",
    "Thời hạn nộp thuế giá trị gia tăng của hộ kinh doanh là khi nào?",
    "Quy định về bảo hiểm y tế tự nguyện cho người nước ngoài?",
    "Độ tuổi nghỉ hưu của công chức theo Luật Cán bộ, công chức?",
    "Mức lương tối thiểu vùng của Lào năm 2026 là bao nhiêu?",
    "Hợp đồng mua bán nhà ở cần công chứng không?",
    "Thủ tục cấp giấy phép xây dựng nhà ở riêng lẻ?",
    "Chế tài khi chậm thanh toán theo Luật Thương mại?",
    "Điều kiện hưởng trợ cấp thất nghiệp theo Luật Việc làm 2013?",
    "Quy định về quyền tác giả đối với phần mềm?",
    "Thuế tiêu thụ đặc biệt với rượu nhập khẩu là bao nhiêu phần trăm?",
    "Thời gian thử việc theo luật của Nhật Bản là bao lâu?",
    "Chính sách visa lao động của Đức cho kỹ sư phần mềm?",
    "Mức đóng bảo hiểm xã hội bắt buộc theo luật Lào?",
    "Quy định về chuyển nhượng cổ phần của công ty đại chúng?",
    "Tiêu chuẩn chức danh nghề nghiệp viên chức ngành y tế?",
    "Hạn mức tín dụng của ngân hàng thương mại với một khách hàng?",
)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def split_of(index: int) -> str:
    return "dev" if index % 5 < 3 else "test"


def article_leaf_ids(chunks: list[dict], doc_id: str) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for chunk in chunks:
        if chunk["doc_id"] == doc_id and chunk["article"]:
            mapping.setdefault(chunk["article"], []).append(chunk["node_id"])
    return {key: sorted(value) for key, value in mapping.items()}


def make_qa(chunks: list[dict]) -> list[dict]:
    """200 câu: 120 tra Điều, 40 tra Khoản, 20 Điều thiếu (fallback), 20 ngoài phạm vi."""
    leaves = article_leaf_ids(chunks, DEFAULT_DOC)
    articles = sorted(leaves, key=lambda value: int(value.rstrip("abcdefgh")))
    clause_chunks = [
        chunk
        for chunk in chunks
        if chunk["doc_id"] == DEFAULT_DOC
        and chunk["clause"] is not None
        and chunk["point"] is None
    ]

    items: list[dict] = []
    step = max(1, len(articles) // 120)
    for number in articles[::step][:120]:
        items.append(
            {
                "type": "article_lookup",
                "question": f"Điều {number} quy định những nội dung gì?",
                "gold_node_ids": leaves[number],
                "gold_doc": DEFAULT_DOC,
            }
        )

    for chunk in clause_chunks[:: max(1, len(clause_chunks) // 40)][:40]:
        items.append(
            {
                "type": "clause_lookup",
                "question": f"Khoản {chunk['clause']} Điều {chunk['article']} quy định gì?",
                "gold_node_ids": leaves.get(chunk["article"], []),
                "gold_doc": DEFAULT_DOC,
            }
        )

    fallback_leaves = article_leaf_ids(chunks, FALLBACK_DOC)
    templates = (
        "Điều {a} quy định gì?",
        "Cho tôi biết nội dung Điều {a} Bộ luật Lao động.",
        "Điều {a} của bộ luật nói về vấn đề nào?",
        "Tóm tắt Điều {a} giúp tôi.",
        "Căn cứ pháp lý tại Điều {a} là gì?",
    )
    for article in ("76", "77", "78", "79"):
        for template in templates:
            items.append(
                {
                    "type": "fallback_article",
                    "question": template.format(a=article),
                    "gold_node_ids": fallback_leaves.get(article, []),
                    "gold_doc": FALLBACK_DOC,
                    "expect_warning": True,
                }
            )

    for question in OOS_QUESTIONS:
        items.append(
            {
                "type": "oos",
                "question": question,
                "gold_node_ids": [],
                "gold_doc": None,
                "expect_refusal": True,
            }
        )

    for index, item in enumerate(items):
        item["qid"] = f"qa-{index + 1:03d}"
        item["split"] = split_of(index)
    return items[:TOTAL_QA]


def make_calc() -> list[dict]:
    """30 case tính: 12 làm thêm giờ + 18 nghỉ hằng năm, kỳ vọng tính độc lập bằng số nguyên."""
    cases: list[dict] = []
    wages = (50_000, 60_000, 80_000)
    plans = (
        ("weekday", "ngày thường", 150),
        ("weekend", "ngày nghỉ hằng tuần", 200),
        ("holiday", "ngày lễ", 300),
        ("night", "ban đêm", 30),
    )
    for plan, phrase, rate in plans:
        for index, wage in enumerate(wages):
            hour = (2, 4, 8)[index]
            cases.append(
                {
                    "type": f"calc_{plan}",
                    "question": (
                        f"Làm thêm {hour} giờ vào {phrase} với lương giờ {wage} đồng "
                        "thì được bao nhiêu?"
                    ),
                    "hourly_wage": wage,
                    "hours": hour,
                    "expected_amount": wage * rate * hour // 100,
                }
            )
    for years in range(1, 19):
        cases.append(
            {
                "type": "calc_leave",
                "question": f"Làm việc {years} năm thì được nghỉ hằng năm bao nhiêu ngày?",
                "years": years,
                "expected_days": 12 + years // 5,
            }
        )
    for index, case in enumerate(cases):
        case["qid"] = f"calc-{index + 1:03d}"
        case["split"] = split_of(index)
    return cases


def write_jsonl(path: Path, records: list[dict]) -> str:
    payload = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa", type=int, default=TOTAL_QA)
    args = parser.parse_args(argv)

    chunks = load_jsonl(PROCESSED_DIR / "chunks_leaf.jsonl")
    qa = make_qa(chunks)[: args.qa]
    calc = make_calc()
    qa_sha = write_jsonl(EVAL_DIR / "qa_eval.jsonl", qa)
    calc_sha = write_jsonl(EVAL_DIR / "calc_eval.jsonl", calc)

    counts: dict[str, int] = {}
    for item in qa:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    print(f"qa: {len(qa)} items {counts} sha256={qa_sha}")
    print(f"calc: {len(calc)} items sha256={calc_sha}")
    print(f"out: {EVAL_DIR.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())