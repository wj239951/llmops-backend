# 文件解析器，支持 txt/md/pdf 格式提取纯文本
from fastapi import UploadFile
import fitz  # PyMuPDF


async def parse_file(file: UploadFile) -> str:
    """根据文件扩展名分发到对应的解析器"""
    if not file.filename:
        raise ValueError("文件名不能为空")

    ext = file.filename.split(".")[-1].lower()

    match ext:
        case "txt" | "md" | "py" | "json":
            content = await file.read()
            return content.decode("utf-8")
        case "pdf":
            return await parse_pdf(file)
        case _:
            raise ValueError(f"不支持的文件类型: {ext}")


async def parse_pdf(file: UploadFile) -> str:
    """解析 PDF 文件，提取所有页面的文本"""
    content = await file.read()

    # fitz (PyMuPDF) 需要从字节流打开
    doc = fitz.open(stream=content, filetype="pdf")

    texts = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            texts.append(text)

    doc.close()
    return "\n\n".join(texts)
