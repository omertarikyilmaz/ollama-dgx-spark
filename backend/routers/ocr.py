"""OCR endpoints for newspaper text extraction"""
import io
import time
from fastapi import APIRouter, HTTPException, UploadFile, File
from PIL import Image
import pytesseract
from models import NewspaperOCRResponse, OCRLine, OCRWord

router = APIRouter(tags=["OCR"])


@router.post("/ocr-newspaper", response_model=NewspaperOCRResponse)
async def ocr_newspaper(file: UploadFile = File(...)):
    """
    Extract text from newspaper image using Tesseract OCR.
    Returns full text and word-level bounding boxes.
    """
    start_time = time.time()

    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Sadece görsel dosyaları destekleniyor (PNG, JPG, JPEG)")

    try:
        content = await file.read()
        image = Image.open(io.BytesIO(content))

        if image.mode != 'RGB':
            image = image.convert('RGB')

        img_width, img_height = image.size

        ocr_data = pytesseract.image_to_data(
            image,
            lang='tur+eng',
            output_type=pytesseract.Output.DICT,
            config='--psm 3 --oem 3'
        )

        lines_dict = {}
        total_words = 0

        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            if not text:
                continue

            level = ocr_data['level'][i]
            if level != 5:
                continue

            line_num = ocr_data['line_num'][i]
            left = float(ocr_data['left'][i])
            top = float(ocr_data['top'][i])
            width = float(ocr_data['width'][i])
            height = float(ocr_data['height'][i])
            conf = float(ocr_data['conf'][i]) / 100.0

            word_bbox = [
                [left, top],
                [left + width, top],
                [left + width, top + height],
                [left, top + height]
            ]

            word_obj = OCRWord(
                text=text,
                bbox=word_bbox,
                confidence=max(0.0, min(1.0, conf))
            )

            if line_num not in lines_dict:
                lines_dict[line_num] = []

            lines_dict[line_num].append({
                'word': word_obj,
                'left': left,
                'top': top,
                'right': left + width,
                'bottom': top + height
            })

            total_words += 1

        lines = []
        all_text_parts = []

        for line_num in sorted(lines_dict.keys()):
            words_data = lines_dict[line_num]
            if not words_data:
                continue

            min_left = min(w['left'] for w in words_data)
            min_top = min(w['top'] for w in words_data)
            max_right = max(w['right'] for w in words_data)
            max_bottom = max(w['bottom'] for w in words_data)

            line_bbox = [
                [min_left, min_top],
                [max_right, min_top],
                [max_right, max_bottom],
                [min_left, max_bottom]
            ]

            words = [w['word'] for w in words_data]
            line_text = ' '.join(w.text for w in words)
            avg_conf = sum(w.confidence for w in words) / len(words)

            lines.append(OCRLine(
                text=line_text,
                bbox=line_bbox,
                confidence=avg_conf,
                words=words
            ))

            all_text_parts.append(line_text)

        lines.sort(key=lambda l: l.bbox[0][1])

        full_text = "\n".join(all_text_parts)
        processing_time = (time.time() - start_time) * 1000

        return NewspaperOCRResponse(
            success=True,
            full_text=full_text,
            lines=lines,
            word_count=total_words,
            processing_time_ms=processing_time,
            image_width=img_width,
            image_height=img_height
        )

    except Exception as e:
        import traceback
        return NewspaperOCRResponse(
            success=False,
            error=str(e) + "\n" + traceback.format_exc(),
            processing_time_ms=(time.time() - start_time) * 1000
        )


@router.get("/ocr-health")
async def ocr_health():
    """Check if OCR service is ready"""
    try:
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages()
        has_turkish = 'tur' in langs

        return {
            "status": "ready",
            "engine": "Tesseract OCR",
            "version": str(version),
            "languages": langs,
            "turkish_available": has_turkish
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
