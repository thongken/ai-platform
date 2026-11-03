import argparse
import json
from pathlib import Path

from app.schemas.content import (
    ContentDocument,
    ContentSection,
    SourceLocation,
)


def time_to_seconds(value: str) -> int:
    """Chuyển HH:MM:SS thành số giây."""
    parts = value.split(":")

    if len(parts) != 3:
        raise ValueError(f"Invalid timestamp: {value}")

    hours, minutes, seconds = map(int, parts)

    if min(hours, minutes, seconds) < 0 or minutes >= 60 or seconds >= 60:
        raise ValueError(f"Invalid timestamp: {value}")

    return hours * 3600 + minutes * 60 + seconds


def convert_record_output(
    raw: dict,
    material_id: str,
    source_type: str = "audio",
) -> dict:
    """Chuyển output Record-to-Quiz sang định dạng AI Platform."""

    results = raw.get("results")

    if not isinstance(results, list) or len(results) != 1:
        raise ValueError(
            "Adapter hiện yêu cầu output của đúng một recording."
        )

    record = results[0]

    if "error" in record:
        raise ValueError(f"Record-to-Quiz failed: {record['error']}")

    quiz_data = record["quiz"]
    segments = quiz_data["segments"]

    sections = []
    questions = []

    for index, segment in enumerate(segments, start=1):
        section_id = f"{material_id}_section_{index}"

        start = time_to_seconds(segment["start_time"])
        end = time_to_seconds(segment["end_time"])

        if end < start:
            raise ValueError("End time must not precede start time")

        # Nội dung section hiện lấy từ segment_summary.
        # Đây là bản tóm tắt, KHÔNG phải transcript gốc.
        section = ContentSection(
            section_id=section_id,
            title=f"Phần {index}",
            content=segment["segment_summary"],
            source=SourceLocation(
                start_seconds=start,
                end_seconds=end,
            ),
        )
        sections.append(section)

        for question_index, question in enumerate(
            segment["quiz"], start=1
        ):
            options = question["options"]
            correct_text = question["correct_answer"]

            if correct_text not in options:
                raise ValueError(
                    f"Correct answer not in options: {section_id}"
                )

            questions.append({
                "question_id": f"{section_id}_q{question_index}",
                "section_id": section_id,
                "question": question["question"],
                "options": options,
                "correct_answer": correct_text,
                "correct_option_index": options.index(correct_text),
                "explanation": question["explanation"],
            })

    document = ContentDocument(
        schema_version="1.0",
        material_id=material_id,
        source_type=source_type,
        title=Path(record["file"]).name,
        sections=sections,
    )

    return {
        "schema_version": "1.0",
        "material_id": material_id,
        "source_type": source_type,
        "transcript": record["transcript"],
        "document": document.model_dump(mode="json"),
        "generated": {
            "summary": quiz_data["summary"],
            "questions": questions,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--material-id", default="mat_audio_001"
    )
    parser.add_argument(
        "--source-type",
        choices=["audio", "video"],
        default="audio",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/record_normalized.json"),
    )

    args = parser.parse_args()

    raw = json.loads(
        args.input.read_text(encoding="utf-8-sig")
    )

    converted = convert_record_output(
        raw,
        material_id=args.material_id,
        source_type=args.source_type,
    )

    args.output.parent.mkdir(
        parents=True, exist_ok=True
    )

    args.output.write_text(
        json.dumps(
            converted,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Record-to-Quiz adapter completed")
    print(f"Material: {converted['material_id']}")
    print(
        "Sections:",
        len(converted["document"]["sections"])
    )
    print(
        "Questions:",
        len(converted["generated"]["questions"])
    )
    print(f"Output: {args.output.resolve()}")


if __name__ == "__main__":
    main()
