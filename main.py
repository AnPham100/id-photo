from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from typing import Optional
from enum import Enum
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import pillow_heif
import io
import rembg
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import base64
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import cv2
import mediapipe as mp
import json

# Register HEIF support with Pillow
pillow_heif.register_heif_opener()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define processing types enum
class ProcessingType(str, Enum):
    """Available image processing types"""
    REMOVE_BG = "remove_bg"           # Remove background (transparent)
    REFILL_BG = "refill_bg"           # Remove background and refill with solid color
    CROP_FACE = "crop_face"           # Crop image based on face detection or manual selection
    PASSPORT_PHOTO = "passport_photo" # Complete passport photo processing (remove bg + refill + crop + photo sheet)

app = FastAPI(title="ID Photo Maker", description="Complete ID photo processing with background removal and face detection")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

# Passport photo specifications (300 DPI (Dots Per Inch) for professional printing)
PASSPORT_SPECS = {
    "US": {
        "width_px": 600,   # 2 inches × 300 DPI = 600px
        "height_px": 600,  # 2 inches × 300 DPI = 600px
        "width_inch": 2.0,
        "height_inch": 2.0,
        "dpi": 300,
        "head_min_px": 300,    # 1 inch (Chin to Top of Hair)
        "head_max_px": 412,    # 1.375 inches
        "eye_line_from_bottom_px": 375,  # ~1.25 inches from bottom
        "upper_body_ratio": 0.3,  # Include 30% upper body
        "head_top_padding": 0.15,  # 15% padding from top
        "name": "US Passport (2×2 inch @ 300 DPI)",
        "sheet_layout": {"cols": 1, "rows": 2, "count": 2}  # 2 photos on 10×15cm (vertical)
    },
    "US_Baby": {
        "width_px": 600,   # 2 inches × 300 DPI = 600px
        "height_px": 600,  # 2 inches × 300 DPI = 600px
        "width_inch": 2.0,
        "height_inch": 2.0,
        "dpi": 300,
        "head_min_px": 300,
        "head_max_px": 400,
        "eye_line_from_bottom_px": 360,
        "upper_body_ratio": 0.3,
        "head_top_padding": 0.15,
        "name": "US Baby Passport (2×2 inch @ 300 DPI)",
        "sheet_layout": {"cols": 1, "rows": 2, "count": 2}  # 2 photos on 10×15cm (vertical)
    },
    "EU": {
        "width_px": 413,   # 35mm ÷ 25.4 × 300 DPI = 413px
        "height_px": 531,  # 45mm ÷ 25.4 × 300 DPI = 531px
        "width_mm": 35,
        "height_mm": 45,
        "dpi": 300,
        "head_min_px": 300,
        "head_max_px": 370,
        "eye_line_from_bottom_px": 295,
        "upper_body_ratio": 0.30,
        "head_top_padding": 0.17,
        "name": "EU Passport (35×45 mm @ 300 DPI)",
        "sheet_layout": {"cols": 2, "rows": 4, "count": 8}  # 8 photos on 10×15cm
    },
    "EU_Baby": {
        "width_px": 413,   # 35mm ÷ 25.4 × 300 DPI = 413px
        "height_px": 531,  # 45mm ÷ 25.4 × 300 DPI = 531px
        "width_mm": 35,
        "height_mm": 45,
        "dpi": 300,
        "head_min_px": 280,
        "head_max_px": 340,  
        "eye_line_from_bottom_px": 275,  
        "upper_body_ratio": 0.40,
        "head_top_padding": 0.20,
        "name": "EU Baby Passport (35×45 mm @ 300 DPI)",
        "sheet_layout": {"cols": 2, "rows": 4, "count": 8}  # 8 photos on 10×15cm
    },
    "VN": {
        "width_px": 472,   # 4cm ÷ 2.54 × 300 DPI = 472px
        "height_px": 709,  # 6cm ÷ 2.54 × 300 DPI = 709px
        "width_mm": 40,    # 4cm = 40mm
        "height_mm": 60,   # 6cm = 60mm
        "dpi": 300,
        "head_min_px": 320,
        "head_max_px": 400,
        "eye_line_from_bottom_px": 354,
        "upper_body_ratio": 0.5,
        "head_top_padding": 0.15,
        "name": "Vietnam Passport (40×60 mm @ 300 DPI)",
        "sheet_layout": {"cols": 2, "rows": 2, "count": 4}  # 4 photos on 10×15cm
    },
    "VN_Baby": {
        "width_px": 472,   # 4cm ÷ 2.54 × 300 DPI = 472px
        "height_px": 709,  # 6cm ÷ 2.54 × 300 DPI = 709px
        "width_mm": 40,    # 4cm = 40mm
        "height_mm": 60,   # 6cm = 60mm
        "dpi": 300,
        "head_min_px": 320,
        "head_max_px": 420,
        "eye_line_from_bottom_px": 340,  
        "upper_body_ratio": 0.50,
        "head_top_padding": 0.15,
        "name": "Vietnam Baby Passport (40×60 mm @ 300 DPI)",
        "sheet_layout": {"cols": 2, "rows": 2, "count": 4}  # 4 photos on 10×15cm
    }
}

# Standard photo sheet specifications (10cm × 15cm)
PHOTO_SHEET_SPECS = {
    "width_mm": 100,   # 10cm
    "height_mm": 150,  # 15cm  
    "width_px": 1181,  # 10cm ÷ 25.4 × 300 DPI = 1181px
    "height_px": 1772, # 15cm ÷ 25.4 × 300 DPI = 1772px
    "dpi": 300,
    "margin_mm": 3,    # 3mm margin on all sides
    "margin_px": 35    # 3mm ÷ 25.4 × 300 DPI = 35px
}

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/script.js")
async def read_script():
    return FileResponse("./static/script.js")

@app.get("/styles.css")
async def read_styles():
    return FileResponse("./static/styles.css")

def detect_face_mediapipe(image_array):
    """Detect face using MediaPipe"""
    # MediaPipe expects RGB images, so pass RGB array directly
    with mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5) as face_detection:
        # Assume image_array is already in RGB format
        results = face_detection.process(image_array)
        
        if results.detections:
            detection = results.detections[0]  # Use the first (most confident) detection
            bbox = detection.location_data.relative_bounding_box
            h, w, _ = image_array.shape
            
            # Convert relative coordinates to absolute
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            width = int(bbox.width * w)
            height = int(bbox.height * h)
            
            return {
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'center_x': x + width // 2,
                'center_y': y + height // 2
            }
    return None

def crop_passport_photo(image_array, face_bbox, target_spec):
    """Crop image to passport photo specifications with face detection"""
    # Convert numpy array to PIL Image for consistent processing
    pil_image = Image.fromarray(image_array.astype(np.uint8))
    w, h = pil_image.size
    
    if not face_bbox:
        # Fallback: center crop
        aspect_ratio = target_spec['width_px'] / target_spec['height_px']
        
        if w / h > aspect_ratio:
            # Image is too wide
            new_width = int(h * aspect_ratio)
            x_offset = (w - new_width) // 2
            crop_box = (x_offset, 0, x_offset + new_width, h)
        else:
            # Image is too tall
            new_height = int(w / aspect_ratio)
            y_offset = (h - new_height) // 2
            crop_box = (0, y_offset, w, y_offset + new_height)
        
        cropped = pil_image.crop(crop_box)
        resized = cropped.resize((target_spec['width_px'], target_spec['height_px']), Image.Resampling.LANCZOS)
        return np.array(resized)
    
    # Calculate crop dimensions based on face position
    face_center_x = face_bbox['center_x']
    face_center_y = face_bbox['center_y']
    face_height = face_bbox['height']
    face_top = face_bbox['y']
    face_bottom = face_bbox['y'] + face_bbox['height']
    
    # Calculate target dimensions
    target_width = target_spec['width_px']
    target_height = target_spec['height_px']
    
    # Use specification parameters
    upper_body_ratio = target_spec.get('upper_body_ratio', 0.3)
    head_top_padding_ratio = target_spec.get('head_top_padding', 0.15)
    target_face_height = target_spec['head_min_px'] * 0.85  # Use 85% of min for good padding
    
    # Calculate scale factor
    scale_factor = target_face_height / face_height
    
    # Calculate crop dimensions in original image
    crop_width = int(target_width / scale_factor)
    crop_height = int(target_height / scale_factor)
    
    # Ensure crop dimensions don't exceed image size - if they do, adjust scale factor
    if crop_width > w or crop_height > h:
        # Calculate scale factors for both dimensions
        scale_factor_w = target_width / w
        scale_factor_h = target_height / h
        # Use the larger scale factor to ensure we fit within bounds
        scale_factor = max(scale_factor_w, scale_factor_h)
        crop_width = int(target_width / scale_factor)
        crop_height = int(target_height / scale_factor)
        logger.info(f"Adjusted scale factor to {scale_factor:.2f} to fit image bounds")
    
    # Ensure minimum crop size (at least 50% of target to maintain quality)
    min_crop_width = int(target_width * 0.5)
    min_crop_height = int(target_height * 0.5)
    
    if crop_width < min_crop_width or crop_height < min_crop_height:
        # Image is too small, use maximum possible crop
        crop_width = min(w, max(crop_width, min_crop_width))
        crop_height = min(h, max(crop_height, min_crop_height))
        logger.warning(f"Image resolution may be too low for optimal passport photo quality")
    
    # Estimate upper body area (below chin)
    upper_body_height = int(face_height * upper_body_ratio)
    
    # Estimate head top (add padding above detected face for hair/forehead)
    head_padding = int(face_height * 0.4)  # 40% of face height for head padding
    estimated_head_top = face_top - head_padding
    
    # Calculate crop position with better handling for different aspect ratios
    # Head top should be at the specified padding ratio from top
    crop_y = estimated_head_top - int(crop_height * head_top_padding_ratio)
    
    # Ensure we include upper body by checking bottom boundary
    required_bottom = face_bottom + upper_body_height
    min_crop_y = required_bottom - crop_height
    crop_y = max(crop_y, min_crop_y)
    
    # Center horizontally on face, but adjust for image aspect ratio
    crop_x = face_center_x - crop_width // 2
    
    # For tall images (height > width), ensure we don't crop too much from sides
    if h > w * 1.2:  # Image is significantly taller than wide
        # Keep more margin on sides for tall images
        min_side_margin = int(w * 0.1)  # 10% margin on each side
        crop_x = max(min_side_margin, min(crop_x, w - crop_width - min_side_margin))
    
    # For wide images (width > height), ensure we don't crop too much from top/bottom  
    if w > h * 1.2:  # Image is significantly wider than tall
        # Keep more margin on top/bottom for wide images
        min_top_margin = int(h * 0.1)  # 10% margin on top/bottom
        crop_y = max(min_top_margin, min(crop_y, h - crop_height - min_top_margin))
    
    # Ensure crop doesn't exceed image boundaries    
    # Adjust if crop exceeds boundaries
    if crop_x < 0:
        crop_x = 0
    elif crop_x + crop_width > w:
        crop_x = w - crop_width
        
    if crop_y < 0:
        crop_y = 0
    elif crop_y + crop_height > h:
        crop_y = h - crop_height
    
    # Final boundary check - ensure crop box is within image
    crop_x = max(0, min(crop_x, w - crop_width))
    crop_y = max(0, min(crop_y, h - crop_height))
    
    # Perform crop using PIL (left, top, right, bottom)
    crop_box = (crop_x, crop_y, crop_x + crop_width, crop_y + crop_height)
    cropped = pil_image.crop(crop_box)
    
    # Resize to target dimensions using PIL's high-quality LANCZOS resampling
    resized = cropped.resize((target_spec['width_px'], target_spec['height_px']), Image.Resampling.LANCZOS)
    
    # Convert back to numpy array
    return np.array(resized)

def remove_background(image_array, tight_crop=True):
    """Remove background using rembg"""
    # Assume image_array is already RGB, convert to PIL and process
    pil_image = Image.fromarray(image_array.astype(np.uint8))
    
    # Try u2net model for tighter human segmentation
    from rembg import session_factory
    try:
        # - Default model: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
        # session = session_factory.new_session('u2net')
        # - Use u2net model which is better for people/portraits
        # - Human segmentation model: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx
        session = session_factory.new_session('u2net_human_seg')
        output = rembg.remove(pil_image, session=session)
    except:
        # Fallback to default model if u2net_human_seg is not available
        output = rembg.remove(pil_image)

    if tight_crop:
        # Post-process the alpha channel to make it tighter
        output_array = np.array(output)
        if len(output_array.shape) == 3 and output_array.shape[2] == 4:
            # Extract alpha channel
            alpha = output_array[:, :, 3]
            
            # Apply morphological operations to tighten the mask
            try:
                # Create a smaller kernel for tighter erosion
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                
                # Erode to tighten the mask (remove loose edges)
                alpha_eroded = cv2.erode(alpha, kernel, iterations=1)
                
                # Apply Gaussian blur to smooth edges
                alpha_smooth = cv2.GaussianBlur(alpha_eroded, (3, 3), 0.5)
                
                # Increase contrast to make edges sharper
                alpha_sharp = np.clip(alpha_smooth * 1.2, 0, 255).astype(np.uint8)
                
                # Update the alpha channel
                output_array[:, :, 3] = alpha_sharp
                output = Image.fromarray(output_array, 'RGBA')
            except Exception as e:
                logger.warning(f"Could not apply tight cropping: {e}")
                # Continue with original output if post-processing fails
    
    return np.array(output)

def add_background_color(image_with_alpha, color):
    """Add solid color background to transparent image"""
    if color.lower() == "transparent":
        return image_with_alpha
    
    # Convert numpy array to PIL Image if needed
    if isinstance(image_with_alpha, np.ndarray):
        if len(image_with_alpha.shape) == 3 and image_with_alpha.shape[2] == 4:
            # RGBA numpy array
            output = Image.fromarray(image_with_alpha, 'RGBA')
        else:
            # RGB numpy array - shouldn't happen in background removal context
            output = Image.fromarray(image_with_alpha, 'RGB')
    else:
        output = image_with_alpha

    # Handle background color
    if color == "white":
        bg_color = "#FFFFFF"
    elif color == "red":
        bg_color = "#D9001B"
    elif color == "blue":
        bg_color = "#02A7F0"
    elif color == "gray":
        bg_color = "#B8B3B2"
    elif color == "black":
        bg_color = "#000000"
    else:
        bg_color = color  # Custom hex color
        
    # Convert hex to RGB tuple 
    if isinstance(bg_color, str) and bg_color.startswith("#"):
        bg_color = bg_color.lstrip("#")
        bg_color = tuple(int(bg_color[i:i+2], 16) for i in (0, 2, 4))
    
    # Create new RGB background and paste the RGBA image onto it
    bg = Image.new("RGB", output.size, bg_color)
    bg.paste(output, (0, 0), output)  # output is used as both image and mask
    
    # Convert back to numpy array
    return np.array(bg)

def create_photo_sheet(passport_image_pil, passport_type):
    """Create a sheet of passport photos on 10cm × 15cm format"""
    if passport_type not in PASSPORT_SPECS:
        raise ValueError(f"Unknown passport type: {passport_type}")
    
    spec = PASSPORT_SPECS[passport_type]
    sheet_spec = PHOTO_SHEET_SPECS
    layout = spec["sheet_layout"]
    
    # Create white background sheet
    sheet = Image.new("RGB", (sheet_spec["width_px"], sheet_spec["height_px"]), "white")
    
    # Handle EU photo rotation (35×45mm rotated to fit better in 2×4 layout)
    photo_to_paste = passport_image_pil.copy()
    if passport_type.startswith("EU"):
        # Rotate EU photos 90 degrees clockwise to fit better in 2×4 layout
        photo_to_paste = photo_to_paste.rotate(-90, expand=True)
        # After rotation: width becomes height, height becomes width
        photo_width = spec["height_px"]  # 531px (was height, now width)
        photo_height = spec["width_px"]  # 413px (was width, now height)
    else:
        photo_width = spec["width_px"]
        photo_height = spec["height_px"]
    
    # Calculate available space for photos (excluding margins)
    available_width = sheet_spec["width_px"] - 2 * sheet_spec["margin_px"]
    available_height = sheet_spec["height_px"] - 2 * sheet_spec["margin_px"]
    
    cols = layout["cols"]
    rows = layout["rows"]
    
    # Calculate total space needed for photos
    total_photos_width = cols * photo_width
    total_photos_height = rows * photo_height
    
    # Calculate spacing between photos
    if cols > 1:
        spacing_x = (available_width - total_photos_width) // (cols + 1)
        spacing_x = max(spacing_x, 5)  # Minimum 5px spacing
    else:
        spacing_x = (available_width - photo_width) // 2
    
    if rows > 1:
        spacing_y = (available_height - total_photos_height) // (rows + 1)
        spacing_y = max(spacing_y, 5)  # Minimum 5px spacing
    else:
        spacing_y = (available_height - photo_height) // 2
    
    # Log warning if photos don't fit (but don't scale - let them get cut off)
    if total_photos_width + (cols + 1) * spacing_x > available_width:
        logger.warning(f"Photos too wide for sheet: need {total_photos_width + (cols + 1) * spacing_x}px, have {available_width}px")
    if total_photos_height + (rows + 1) * spacing_y > available_height:
        logger.warning(f"Photos too tall for sheet: need {total_photos_height + (rows + 1) * spacing_y}px, have {available_height}px")
    
    # Place photos on the sheet with light gray borders for cutting guides
    border_width = 1  # 1 pixel light gray border
    border_color = (200, 200, 200)  # Light gray RGB
    
    for row in range(rows):
        for col in range(cols):
            # Calculate position
            x = sheet_spec["margin_px"] + spacing_x + col * (photo_width + spacing_x)
            y = sheet_spec["margin_px"] + spacing_y + row * (photo_height + spacing_y)
            
            # Draw light gray border rectangle around photo area
            draw = ImageDraw.Draw(sheet)
            # Draw border slightly larger than photo for cutting guide
            border_x1 = x - border_width
            border_y1 = y - border_width  
            border_x2 = x + photo_width + border_width
            border_y2 = y + photo_height + border_width
            
            # Draw the border
            draw.rectangle([border_x1, border_y1, border_x2, border_y2], 
                         outline=border_color, width=border_width)
            
            # Paste the photo
            sheet.paste(photo_to_paste, (x, y))
    
    return sheet

def create_flexible_photo_sheet(passport_image_pil):
    """Create a flexible photo sheet that fits photos automatically without scaling
    
    This function calculates how many photos can fit in a 10cm × 15cm sheet
    without scaling the input photo, so you can see if dimensions are correct
    """
    sheet_spec = PHOTO_SHEET_SPECS
    
    # Create white background sheet
    sheet = Image.new("RGB", (sheet_spec["width_px"], sheet_spec["height_px"]), "white")
    
    # Get photo dimensions (use as-is, no scaling)
    photo_width, photo_height = passport_image_pil.size
    
    # Calculate available space for photos (excluding margins)
    available_width = sheet_spec["width_px"] - 2 * sheet_spec["margin_px"]
    available_height = sheet_spec["height_px"] - 2 * sheet_spec["margin_px"]
    
    # Calculate minimum spacing
    min_spacing = 10  # 10px minimum spacing between photos
    
    # Calculate how many photos can fit horizontally and vertically
    cols = max(1, (available_width + min_spacing) // (photo_width + min_spacing))
    rows = max(1, (available_height + min_spacing) // (photo_height + min_spacing))
    
    # Ensure at least one photo fits
    if photo_width > available_width or photo_height > available_height:
        logger.warning(f"Photo ({photo_width}×{photo_height}px) is larger than available sheet space ({available_width}×{available_height}px)")
        # Still place one photo, but it will be clipped
        cols = 1
        rows = 1
    
    total_count = cols * rows
    
    # Calculate actual spacing to center the grid
    if cols > 1:
        spacing_x = (available_width - cols * photo_width) // (cols + 1)
        spacing_x = max(spacing_x, min_spacing)
    else:
        spacing_x = (available_width - photo_width) // 2
    
    if rows > 1:
        spacing_y = (available_height - rows * photo_height) // (rows + 1)
        spacing_y = max(spacing_y, min_spacing)
    else:
        spacing_y = (available_height - photo_height) // 2
    
    logger.info(f"Flexible sheet layout: {cols}×{rows} = {total_count} photos, photo size: {photo_width}×{photo_height}px, spacing: {spacing_x}×{spacing_y}px")
    
    # Place photos on the sheet with cutting guides
    border_width = 1
    border_color = (200, 200, 200)  # Light gray
    
    for row in range(rows):
        for col in range(cols):
            # Calculate position
            x = sheet_spec["margin_px"] + spacing_x + col * (photo_width + spacing_x)
            y = sheet_spec["margin_px"] + spacing_y + row * (photo_height + spacing_y)
            
            # Draw cutting guide border
            draw = ImageDraw.Draw(sheet)
            border_x1 = x - border_width
            border_y1 = y - border_width
            border_x2 = x + photo_width + border_width
            border_y2 = y + photo_height + border_width
            
            draw.rectangle([border_x1, border_y1, border_x2, border_y2],
                         outline=border_color, width=border_width)
            
            # Paste the photo (will be clipped if too large)
            try:
                sheet.paste(passport_image_pil, (x, y))
            except Exception as e:
                logger.warning(f"Could not paste photo at ({x}, {y}): {e}")
    
    return sheet

def convert_dimensions_to_pixels(width: float, height: float, unit: str, dpi: int = 300) -> tuple:
    """Convert dimensions from specified unit to pixels at given DPI"""
    if unit == 'px':
        return int(width), int(height)
    elif unit == 'cm':
        # 1 cm = 300/2.54 pixels at 300 DPI (approximately 118.11 pixels)
        pixels_per_cm = dpi / 2.54
        return int(width * pixels_per_cm), int(height * pixels_per_cm)
    elif unit == 'inch':
        # 1 inch = DPI pixels
        return int(width * dpi), int(height * dpi)
    else:
        raise ValueError(f"Unsupported unit: {unit}")

def apply_manual_crop(image_array: np.ndarray, crop_data: dict) -> np.ndarray:
    """Apply manual crop based on crop coordinates"""
    h, w = image_array.shape[:2]
    
    # Extract crop coordinates from manual crop data
    x = max(0, min(crop_data.get('x', 0), w))
    y = max(0, min(crop_data.get('y', 0), h))
    crop_width = max(1, min(crop_data.get('width', w), w - x))
    crop_height = max(1, min(crop_data.get('height', h), h - y))
    
    logger.info(f"Manual crop: ({x}, {y}, {crop_width}, {crop_height}) from {w}x{h} image")
    
    # Crop the image
    if len(image_array.shape) == 3:
        cropped = image_array[y:y+crop_height, x:x+crop_width]
    else:
        cropped = image_array[y:y+crop_height, x:x+crop_width]
    
    return cropped

def apply_automatic_crop(image_array: np.ndarray, face_bbox: Optional[dict], target_aspect_ratio: float) -> np.ndarray:
    """Apply automatic crop centering on face with target aspect ratio"""
    h, w = image_array.shape[:2]
    
    if not face_bbox:
        # No face detected - center crop
        logger.warning("No face detected, using center crop")
        
        if w / h > target_aspect_ratio:
            # Image is wider - crop width
            new_width = int(h * target_aspect_ratio)
            x_offset = (w - new_width) // 2
            cropped = image_array[:, x_offset:x_offset + new_width]
        else:
            # Image is taller - crop height
            new_height = int(w / target_aspect_ratio)
            y_offset = (h - new_height) // 2
            cropped = image_array[y_offset:y_offset + new_height, :]
        
        return cropped
    
    # Use face-centered cropping
    face_center_x = face_bbox['center_x']
    face_center_y = face_bbox['center_y']
    face_height = face_bbox['height']
    
    # Calculate crop size maintaining target aspect ratio
    # Start with a reasonable crop size (aim for face to be about 1/3 of image height)
    crop_height = max(face_height * 3, min(h, w // target_aspect_ratio) // 2)  # Minimum reasonable size
    crop_width = int(crop_height * target_aspect_ratio)
    
    # Ensure crop fits within image bounds
    crop_width = min(crop_width, w)
    crop_height = min(crop_height, h)
    
    # Recalculate to maintain aspect ratio if we hit bounds
    if crop_width == w:
        crop_height = int(crop_width / target_aspect_ratio)
    elif crop_height == h:
        crop_width = int(crop_height * target_aspect_ratio)
    
    # Center crop on face
    left = max(0, int(face_center_x - crop_width // 2))
    top = max(0, int(face_center_y - crop_height // 2))
    
    # Adjust if crop goes beyond image bounds
    if left + crop_width > w:
        left = w - crop_width
    if top + crop_height > h:
        top = h - crop_height
    
    # Apply crop
    cropped = image_array[top:top + crop_height, left:left + crop_width]
    
    logger.info(f"Automatic face-centered crop: ({left}, {top}, {crop_width}, {crop_height}) from {w}x{h} image")
    
    return cropped

def resize_to_target_dimensions(image_array: np.ndarray, target_width_px: int, target_height_px: int) -> np.ndarray:
    """Resize image to exact target dimensions"""
    pil_image = Image.fromarray(image_array.astype(np.uint8))
    resized = pil_image.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
    
    logger.info(f"Resized image to {target_width_px} x {target_height_px} pixels")
    
    return np.array(resized)

async def process_image_data(
    file_content: bytes,
    processing_type: ProcessingType,
    background_color: str = "white",
    passport_type: Optional[str] = None,
    manual_crop_data: Optional[dict] = None,
    target_width: Optional[str] = None,
    target_height: Optional[str] = None,
    target_unit: Optional[str] = None,
    crop_only: bool = False
):
    """Process image based on the selected options"""
    try:
        # Load image with HEIC support
        image = Image.open(io.BytesIO(file_content))
        
        # Fix image orientation using EXIF data (handles mobile photos)
        image = ImageOps.exif_transpose(image)
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to numpy array - keep in RGB format throughout processing
        image_array = np.array(image)
        
        original_h, original_w = image_array.shape[:2]
        logger.info(f"Original image size: {original_w} × {original_h} pixels (after orientation fix)")
        
        # Detect face (MediaPipe expects RGB)
        face_bbox = detect_face_mediapipe(image_array)
        if face_bbox:
            logger.info(f"Face detected at: {face_bbox}")
        else:
            logger.warning("No face detected, using center crop")
        
        processed_image = image_array.copy()
        
        if processing_type == ProcessingType.REMOVE_BG:
            # Option 1: Remove background (transparent)
            processed_image = remove_background(processed_image)
            
        elif processing_type == ProcessingType.REFILL_BG:
            # Option 2: Remove background and refill with solid color
            processed_image = remove_background(processed_image)
            processed_image = add_background_color(processed_image, background_color)
            # No color conversion needed - stay in RGB
            
        elif processing_type == ProcessingType.CROP_FACE:
            # Option 3: Crop image based on manual selection or target dimensions
            if manual_crop_data and target_width and target_height and target_unit:
                # Manual cropping workflow
                target_width_px, target_height_px = convert_dimensions_to_pixels(
                    float(target_width), float(target_height), target_unit
                )
                # Step 1: Apply manual crop
                cropped_image = apply_manual_crop(processed_image, manual_crop_data)
                # Step 2: Resize to target dimensions
                processed_image = resize_to_target_dimensions(cropped_image, target_width_px, target_height_px)
            elif target_width and target_height and target_unit:
                # Automatic cropping workflow
                target_width_px, target_height_px = convert_dimensions_to_pixels(
                    float(target_width), float(target_height), target_unit
                )
                target_aspect_ratio = target_width_px / target_height_px
                # Step 1: Apply automatic crop with face detection
                cropped_image = apply_automatic_crop(processed_image, face_bbox, target_aspect_ratio)
                # Step 2: Resize to target dimensions
                processed_image = resize_to_target_dimensions(cropped_image, target_width_px, target_height_px)
            elif passport_type and passport_type in PASSPORT_SPECS:
                # Fallback to passport specs if no target dimensions
                spec = PASSPORT_SPECS[passport_type]
                processed_image = crop_passport_photo(processed_image, face_bbox, spec)
            
        elif processing_type == ProcessingType.PASSPORT_PHOTO:
            # Option 4: Complete passport photo (remove bg + refill + crop)
            # First remove background
            processed_image = remove_background(processed_image)
            # Then add solid background
            processed_image = add_background_color(processed_image, background_color)
            # Finally crop to target dimensions or passport specifications
            if manual_crop_data and target_width and target_height and target_unit:
                # Manual cropping workflow
                target_width_px, target_height_px = convert_dimensions_to_pixels(
                    float(target_width), float(target_height), target_unit
                )
                # Step 1: Apply manual crop
                cropped_image = apply_manual_crop(processed_image, manual_crop_data)
                # Step 2: Resize to target dimensions
                processed_image = resize_to_target_dimensions(cropped_image, target_width_px, target_height_px)
            elif target_width and target_height and target_unit:
                # Automatic cropping workflow
                target_width_px, target_height_px = convert_dimensions_to_pixels(
                    float(target_width), float(target_height), target_unit
                )
                target_aspect_ratio = target_width_px / target_height_px
                # Detect face in processed image (still RGB)
                face_bbox_processed = detect_face_mediapipe(processed_image)
                if not face_bbox_processed:
                    face_bbox_processed = face_bbox  # Use original detection
                # Step 1: Apply automatic crop with face detection
                cropped_image = apply_automatic_crop(processed_image, face_bbox_processed, target_aspect_ratio)
                # Step 2: Resize to target dimensions
                processed_image = resize_to_target_dimensions(cropped_image, target_width_px, target_height_px)
            elif passport_type and passport_type in PASSPORT_SPECS:
                # Fallback to passport specs
                spec = PASSPORT_SPECS[passport_type]
                # Detect face in processed image (still RGB)
                face_bbox_processed = detect_face_mediapipe(processed_image)
                if not face_bbox_processed:
                    face_bbox_processed = face_bbox  # Use original detection
                processed_image = crop_passport_photo(processed_image, face_bbox_processed, spec)
        
        # Convert back to PIL Image
        if len(processed_image.shape) == 3:
            if processed_image.shape[2] == 4:
                # RGBA
                pil_result = Image.fromarray(processed_image.astype(np.uint8), 'RGBA')
            else:
                # RGB - no conversion needed since we stayed in RGB
                pil_result = Image.fromarray(processed_image.astype(np.uint8), 'RGB')
        else:
            # Grayscale
            pil_result = Image.fromarray(processed_image.astype(np.uint8), 'L')
        
        # Set DPI metadata for professional printing
        dpi = 300  # Standard for high-quality printing
        if processing_type in [ProcessingType.CROP_FACE, ProcessingType.PASSPORT_PHOTO] and passport_type and passport_type in PASSPORT_SPECS:
            dpi = PASSPORT_SPECS[passport_type].get("dpi", 300)
        
        # Convert to base64 with proper DPI metadata
        buffered = io.BytesIO()
        if processing_type == ProcessingType.REMOVE_BG:
            pil_result.save(buffered, format="PNG", dpi=(dpi, dpi))
        else:
            pil_result.save(buffered, format="JPEG", quality=95, dpi=(dpi, dpi))
        
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        result_w, result_h = pil_result.size
        logger.info(f"Result image size: {result_w} × {result_h} pixels @ {dpi} DPI")
        
        # Calculate physical dimensions for logging
        width_inch = result_w / dpi
        height_inch = result_h / dpi
        logger.info(f"Physical print size: {width_inch:.2f} × {height_inch:.2f} inches")
        
        # Generate photo sheet only for passport photos
        sheet_data = None
        if processing_type == ProcessingType.PASSPORT_PHOTO:
            try:
                logger.info(f"Creating photo sheet - passport_type: {passport_type}, manual_crop_data: {manual_crop_data is not None}, target_dims: {target_width}x{target_height} {target_unit}")
                
                # Check if manual cropping was used (indicates custom dimensions)
                if manual_crop_data and target_width and target_height and target_unit:
                    # Manual cropping with custom dimensions - create flexible sheet
                    logger.info("Using flexible sheet for manual cropping")
                    sheet = create_flexible_photo_sheet(pil_result)
                    sheet_info = "Flexible layout"
                    photo_count = "Auto-fit"
                elif passport_type and passport_type in PASSPORT_SPECS:
                    # Predefined passport specifications - use fixed layout
                    logger.info(f"Using predefined passport specs for {passport_type}")
                    sheet = create_photo_sheet(pil_result, passport_type)
                    layout = PASSPORT_SPECS[passport_type]["sheet_layout"]
                    sheet_info = f"{layout['cols']}×{layout['rows']}"
                    photo_count = layout["count"]
                    logger.info(f"Created sheet with layout: {sheet_info}, count: {photo_count}")
                else:
                    # Fallback to flexible sheet
                    logger.info("Using fallback flexible sheet")
                    sheet = create_flexible_photo_sheet(pil_result)
                    sheet_info = "Flexible layout"
                    photo_count = "Auto-fit"
                
                sheet_buffered = io.BytesIO()
                sheet.save(sheet_buffered, format="JPEG", quality=95, dpi=(dpi, dpi))
                sheet_base64 = base64.b64encode(sheet_buffered.getvalue()).decode()
                
                sheet_data = {
                    "image": sheet_base64,
                    "width": sheet.size[0],
                    "height": sheet.size[1],
                    "count": photo_count,
                    "layout": sheet_info,
                    "dpi": dpi
                }
                logger.info(f"Photo sheet created: {photo_count} photos in {sheet_info} layout")
            except Exception as e:
                logger.warning(f"Could not create photo sheet: {e}")
        
        # Prepare result data
        result_data = {
            "image": img_base64,
            "width": result_w,
            "height": result_h,
            "dpi": dpi,
            "physical_size_inches": f"{width_inch:.2f} × {height_inch:.2f}",
            "face_detected": face_bbox is not None,
            "original_size": f"{original_w} × {original_h}",
            "processing_type": processing_type,
            "sheet": sheet_data
        }
        
        # Add target dimensions if provided (for verification)
        if target_width and target_height and target_unit:
            result_data["target_dimensions"] = {
                "width": float(target_width),
                "height": float(target_height),
                "unit": target_unit
            }
        
        return result_data
        
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@app.post("/process")
async def process_image(
    file: UploadFile = File(...),
    processing_type: ProcessingType = Form(...),  # Enum: remove_bg, refill_bg, crop_face, passport_photo. FastAPI automatically converts string to enum.
    background_color: str = Form("white"),
    passport_type: Optional[str] = Form(None),
    manual_crop: Optional[str] = Form(None),  # JSON string with manual crop data
    target_width: Optional[str] = Form(None),  # Target width in specified unit
    target_height: Optional[str] = Form(None),  # Target height in specified unit
    target_unit: Optional[str] = Form(None)  # Unit: cm, inch, px
):
    """Process image with selected options
    
    Args:
        file: Input image file
        processing_type: Type of processing (ProcessingType enum)
        background_color: Background color for refill_bg and passport_photo
        passport_type: Passport specification (for passport_photo)
        manual_crop: JSON string with manual crop coordinates
        target_width/height/unit: Custom target dimensions
    """
    
    # Enhanced file validation - support common image formats + HEIC
    allowed_types = [
        'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
        'image/heic', 'image/heif'  # Apple HEIC/HEIF formats
    ]
    
    if not (file.content_type and 
            (file.content_type.startswith('image/') or file.content_type in allowed_types)):
        raise HTTPException(
            status_code=400, 
            detail=f"File must be an image. Supported formats: JPG, PNG, WEBP, HEIC. Received: {file.content_type}"
        )
    
    logger.info(f"Processing file: {file.filename}, content_type: {file.content_type}")
    
    # Read file content
    file_content = await file.read()
    
    # Parse manual crop data if provided
    manual_crop_data = None
    if manual_crop:
        try:
            manual_crop_data = json.loads(manual_crop)
        except json.JSONDecodeError:
            logger.warning("Invalid manual crop JSON data, ignoring")
    
    # Process in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            lambda: asyncio.run(process_image_data(
                file_content,
                processing_type,
                background_color,
                passport_type,
                manual_crop_data,
                target_width,
                target_height,
                target_unit
            ))
        )
    
    return JSONResponse(content=result)

@app.post("/convert-img")
async def convert_image(
    file: UploadFile = File(...),
    output_format: str = "jpeg",
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: int = 90,
    keep_original_size: bool = True
):
    """Convert image between formats and optionally resize
    
    Args:
        file: Input image file (supports JPG, PNG, WEBP, HEIC, HEIF)
        output_format: Target format (jpeg, png, webp)
        max_width: Maximum width for resizing (optional)
        max_height: Maximum height for resizing (optional) 
        quality: JPEG quality (1-100, default 85)
        keep_original_size: If True, preserve original dimensions
    """
    
    # Enhanced file validation - support common image formats + HEIC
    allowed_types = [
        'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
        'image/heic', 'image/heif'  # Apple HEIC/HEIF formats
    ]
    
    if not (file.content_type and 
            (file.content_type.startswith('image/') or file.content_type in allowed_types)):
        raise HTTPException(
            status_code=400, 
            detail=f"File must be an image. Supported formats: JPG, PNG, WEBP, HEIC. Received: {file.content_type}"
        )
    
    # Validate output format
    output_format = output_format.lower()
    if output_format not in ['jpeg', 'jpg', 'png', 'webp']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported output format: {output_format}. Supported: jpeg, png, webp"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Load image with HEIC support
        image = Image.open(io.BytesIO(file_content))
        
        # Store original dimensions
        original_width, original_height = image.size
        
        # Fix image orientation using EXIF data (handles mobile photos)
        image = ImageOps.exif_transpose(image)
        
        # Convert to RGB for JPEG output, or RGBA for PNG if needed
        if output_format in ['jpeg', 'jpg']:
            if image.mode != 'RGB':
                image = image.convert('RGB')
        elif output_format == 'png':
            if image.mode not in ['RGB', 'RGBA']:
                image = image.convert('RGBA')
        elif output_format == 'webp':
            if image.mode not in ['RGB', 'RGBA']:
                image = image.convert('RGB')
        
        # Handle resizing
        if not keep_original_size and (max_width or max_height):
            w, h = image.size
            
            # Calculate new size based on constraints
            if max_width and max_height:
                # Resize to fit within both constraints
                ratio = min(max_width / w, max_height / h)
                new_w = int(w * ratio)
                new_h = int(h * ratio)
            elif max_width:
                # Resize based on width constraint
                ratio = max_width / w
                new_w = max_width
                new_h = int(h * ratio)
            elif max_height:
                # Resize based on height constraint
                ratio = max_height / h
                new_w = int(w * ratio)
                new_h = max_height
            
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Convert to output format
        buffered = io.BytesIO()
        
        if output_format in ['jpeg', 'jpg']:
            image.save(buffered, format="JPEG", quality=quality, optimize=True)
            output_mime = "image/jpeg"
        elif output_format == 'png':
            image.save(buffered, format="PNG", optimize=True)
            output_mime = "image/png"
        elif output_format == 'webp':
            image.save(buffered, format="WEBP", quality=quality, optimize=True)
            output_mime = "image/webp"
        
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        return JSONResponse(content={
            "success": True,
            "image": img_base64,
            "width": image.size[0],
            "height": image.size[1],
            "original_width": original_width,
            "original_height": original_height,
            "original_format": file.content_type,
            "output_format": output_mime,
            "file_size_bytes": len(buffered.getvalue())
        })
        
    except Exception as e:
        logger.error(f"Error converting image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error converting image: {str(e)}")

@app.get("/passport-specs")
async def get_passport_specs():
    """Get available passport photo specifications"""
    return JSONResponse(content=PASSPORT_SPECS)

@app.get("/processing-types")
async def get_processing_types():
    """Get available processing types"""
    return JSONResponse(content={
        "processing_types": [
            {
                "value": ptype.value,
                "description": {
                    ProcessingType.REMOVE_BG: "Remove background (transparent)",
                    ProcessingType.REFILL_BG: "Remove background and refill with solid color", 
                    ProcessingType.CROP_FACE: "Crop image based on face detection or manual selection",
                    ProcessingType.PASSPORT_PHOTO: "Complete passport photo processing (remove bg + refill + crop + photo sheet)"
                }[ptype]
            }
            for ptype in ProcessingType
        ]
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Export app for Vercel
app = app
