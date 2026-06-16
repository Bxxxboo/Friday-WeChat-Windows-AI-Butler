from __future__ import annotations

from pathlib import Path

from friday.tools._decorators import register_tool


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


@register_tool(
    name="create_docx",
    description="创建 Word 文档",
    parameters={
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
            "title": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "body": {"type": "string"},
                    },
                },
            },
        },
        "required": ["output_path", "title", "sections"],
    },
)
def create_docx(output_path: str, title: str, sections: list[dict]) -> str:
    from docx import Document

    target = _resolve(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    doc.add_heading(title, level=0)
    for section in sections:
        heading = section.get("heading")
        body = section.get("body", "")
        if heading:
            doc.add_heading(str(heading), level=1)
        if body:
            doc.add_paragraph(str(body))
    doc.save(target)
    return f"已创建 Word 文档: {target}"


@register_tool(
    name="create_pptx",
    description="创建极简 PowerPoint 草稿（无设计、仅标题+要点）。正式汇报/演示请走内置 ppt-master 工作流，不要用本工具。",
    parameters={
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
            "title": {"type": "string"},
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "bullets": {"type": "string", "description": "每行一条要点"},
                    },
                },
            },
        },
        "required": ["output_path", "title", "slides"],
    },
)
def create_pptx(output_path: str, title: str, slides: list[dict]) -> str:
    from pptx import Presentation
    from pptx.util import Pt

    target = _resolve(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation()
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = title
    if len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = "由星期五生成"

    for slide in slides:
        layout = prs.slide_layouts[1]
        page = prs.slides.add_slide(layout)
        page.shapes.title.text = str(slide.get("title", "未命名"))
        body = page.placeholders[1].text_frame
        body.clear()
        for line in str(slide.get("bullets", "")).splitlines():
            if not line.strip():
                continue
            p = body.add_paragraph() if body.text else body.paragraphs[0]
            p.text = line.strip()
            p.font.size = Pt(18)
            p.level = 0

    prs.save(target)
    return f"已创建 PPT 文档: {target}"
