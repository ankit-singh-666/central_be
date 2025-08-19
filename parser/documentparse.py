import os
from huggingface_hub import snapshot_download
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import (
    ConversionResult,
    DocumentConverter,
    InputFormat,
    PdfFormatOption,
)
import fitz  # PyMuPDF
from pix2tex.cli import LatexOCR


def extract_images_from_pdf(pdf_path):
    """Extract images from each page of a PDF."""
    pdf = fitz.open(pdf_path)
    images = []
    for i, page in enumerate(pdf, start=1):
        for img in page.get_images(full=True):
            xref = img[0]
            base_image = pdf.extract_image(xref)
            images.append({
                "page": i,
                "bytes": base_image["image"],
                "ext": base_image["ext"],
            })
    return images


def convert_pdf_to_markdown(pdf_path: str, output_dir: str = "output") -> str:
    """
    Converts PDF file at pdf_path to Markdown with embedded mathematical formulas extracted via OCR.
    Saves the result in output_dir folder, returns path to the generated Markdown file.
    """
    print("Downloading RapidOCR models")
    download_path = snapshot_download(repo_id="SWHL/RapidOCR")

    det_model_path = os.path.join(download_path, "PP-OCRv4", "en_PP-OCRv3_det_infer.onnx")
    rec_model_path = os.path.join(download_path, "PP-OCRv4", "ch_PP-OCRv4_rec_server_infer.onnx")
    cls_model_path = os.path.join(download_path, "PP-OCRv3", "ch_ppocr_mobile_v2.0_cls_train.onnx")

    ocr_options = RapidOcrOptions(
        det_model_path=det_model_path,
        rec_model_path=rec_model_path,
        cls_model_path=cls_model_path,
    )

    pipeline_options = PdfPipelineOptions(
        ocr_options=ocr_options,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            ),
        },
    )

    print(f"Converting PDF document: {pdf_path}")
    conversion_result: ConversionResult = converter.convert(source=pdf_path)
    doc = conversion_result.document
    md = doc.export_to_markdown()

    print("Extracting images from PDF pages for formula detection...")
    images = extract_images_from_pdf(pdf_path)
    pix2tex_model = LatexOCR()
    math_md_blocks = []
    for img in images:
        try:
            latex_code = pix2tex_model(img["bytes"])
            # Heuristic: consider as math if contains math chars and sufficient length
            if latex_code and (any(c in latex_code for c in "=\\frac{}\\sum\\sqrt") and len(latex_code.strip()) > 3):
                math_md_blocks.append(
                    f"\n\n**Math Formula from Page {img['page']}**:\n\n$$\n{latex_code}\n$$\n"
                )
        except Exception as e:
            print(f"[WARN] Math OCR failed on page {img['page']}: {e}")

    if math_md_blocks:
        md += "\n".join(math_md_blocks)

    input_filename = os.path.basename(pdf_path)
    filename_wo_ext = os.path.splitext(input_filename)[0]
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"new{filename_wo_ext}.md")

    with open(output_path, "w", encoding="utf-8") as outfile:
        outfile.write(md)

    print(f"Markdown output written to: {output_path}")
    return output_path


# Example usage:
# output_md = convert_pdf_to_markdown("../Downloads/abctest.pdf")
# print(f"Markdown file saved at: {output_md}")
