# Streamlit app (for dev demo)

import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import pillow_heif
import io
import rembg
import mediapipe as mp
from datetime import datetime

# Import cv2 with error handling for cloud deployment
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError as e:
    st.warning("⚠️ OpenCV not available. Some advanced features may be limited.")
    CV2_AVAILABLE = False
    cv2 = None

# Import streamlit-cropper with error handling
try:
    from streamlit_cropper import st_cropper
    CROPPER_AVAILABLE = True
except ImportError as e:
    st.warning("⚠️ streamlit-cropper not available. Manual crop feature will be limited.")
    CROPPER_AVAILABLE = False

# Register HEIF support with Pillow
pillow_heif.register_heif_opener()

def format_passport_option(key, spec):
    """Format passport option with country flag"""
    country_flags = {
        "US": "🇺🇸",
        "EU": "🇪🇺",
        "VN": "🇻🇳"
    }
    flag = country_flags.get(key, "🌍")
    
    name = spec['name']
    
    return f"{flag} {name}"

def format_color_option(color_key, color_value):
    """Format color option with inline color box"""
    color_map = {
        "white": "#FFFFFF",
        "light_gray": "#B8B3B2", 
        "light_blue": "#E6F3FF",
        "light_red": "#F5E6E8"
    }
    
    if color_key == "custom":
        return "🎨 Custom"
    
    # Get the color hex value and name
    color_name = color_key.replace('_', ' ').title()
    
    # Use color block emoji that closely matches the actual color
    if color_key == "white":
        return "⬜ White"
    elif color_key == "light_gray":
        return "⬜ Light Gray"  # Using light square for light gray
    elif color_key == "light_blue":
        return "🟦 Light Blue"
    elif color_key == "light_red":
        return "🟥 Light Red"
    
    return f"🎨 {color_name}"

def is_cv2_available():
    """Check if OpenCV is available for advanced features"""
    return CV2_AVAILABLE and cv2 is not None

def cv2_feature_example(image):
    """Example function showing how to use cv2 when available"""
    if not is_cv2_available():
        st.warning("⚠️ This feature requires OpenCV which is not available in this environment.")
        return image
    
    # Example: Convert PIL to OpenCV format for cv2 operations
    try:
        # Convert PIL Image to OpenCV format (BGR)
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Example cv2 operation (blur)
        blurred = cv2.GaussianBlur(cv_image, (15, 15), 0)
        
        # Convert back to PIL format (RGB)
        result = cv2.cvtColor(blurred, cv2.COLOR_BGR2RGB)
        return Image.fromarray(result)
        
    except Exception as e:
        st.error(f"OpenCV operation failed: {e}")
        return image

# Configure Streamlit page
st.set_page_config(
    page_title="ID Photo Maker",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize MediaPipe Face Detection
@st.cache_resource
def initialize_mediapipe():
    return mp.solutions.face_detection.FaceDetection(
        model_selection=0, min_detection_confidence=0.5
    )

mp_face_detection = initialize_mediapipe()
mp_drawing = mp.solutions.drawing_utils

# Passport photo specifications
PASSPORT_SPECS = {
    "US": {
        "width_px": 600,   # 2 inches × 300 DPI = 600px
        "height_px": 600,  # 2 inches × 300 DPI = 600px
        "width_inch": 2.0,
        "height_inch": 2.0,
        "dpi": 300,
        "head_min_px": 300,
        "head_max_px": 412,
        "eye_line_from_bottom_px": 375,
        "upper_body_ratio": 0.3,
        "head_top_padding": 0.15,
        "name": "US Passport (2×2 inch @ 300 DPI)",
        "sheet_layout": {"cols": 1, "rows": 2, "count": 2}
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
        "sheet_layout": {"cols": 2, "rows": 4, "count": 8}
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
        "sheet_layout": {"cols": 2, "rows": 2, "count": 4}
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

def save_image_with_dpi(image, format='JPEG', dpi=300, quality=95):
    """Save image with proper DPI metadata for correct physical dimensions"""
    img_byte_arr = io.BytesIO()
    
    # Set DPI metadata
    if format.upper() == 'PNG':
        image.save(img_byte_arr, format='PNG', dpi=(dpi, dpi))
    else:
        image.save(img_byte_arr, format='JPEG', dpi=(dpi, dpi), quality=quality)
    
    return img_byte_arr.getvalue()

def detect_faces(image):
    """Detect faces in image using MediaPipe"""
    try:
        # Convert PIL to RGB array
        image_rgb = np.array(image.convert('RGB'))
        
        # Detect faces
        results = mp_face_detection.process(image_rgb)
        
        faces = []
        if results.detections:
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                faces.append({
                    'x': int(bbox.xmin * image.width),
                    'y': int(bbox.ymin * image.height),
                    'width': int(bbox.width * image.width),
                    'height': int(bbox.height * image.height),
                    'confidence': detection.score[0]
                })
        
        return faces
    except Exception as e:
        st.error(f"Face detection error: {str(e)}")
        return []

def apply_manual_crop(image, crop_data):
    """Apply manual crop based on crop coordinates"""
    try:
        x = crop_data['x']
        y = crop_data['y']
        width = crop_data['width']
        height = crop_data['height']
        
        # Ensure crop coordinates are within image bounds
        x = max(0, min(x, image.width - 1))
        y = max(0, min(y, image.height - 1))
        width = min(width, image.width - x)
        height = min(height, image.height - y)
        
        # Crop the image
        cropped_image = image.crop((x, y, x + width, y + height))
        return cropped_image
    except Exception as e:
        st.error(f"Error applying manual crop: {str(e)}")
        return image

def resize_to_target_dimensions(image, target_width_px, target_height_px, method="fit"):
    """
    Resize image to target dimensions with different methods
    
    Args:
        image: PIL Image
        target_width_px: Target width in pixels
        target_height_px: Target height in pixels
        method: Resize method - "fit" (preserve aspect, may have padding), "fill" (stretch), "crop" (preserve aspect, crop excess)
    """
    try:
        if method == "fit":
            # Preserve aspect ratio, fit within target dimensions (may add padding)
            image.thumbnail((target_width_px, target_height_px), Image.Resampling.LANCZOS)
            
            # Create white background with target dimensions
            result = Image.new('RGB', (target_width_px, target_height_px), 'white')
            
            # Center the resized image on the background
            x = (target_width_px - image.width) // 2
            y = (target_height_px - image.height) // 2
            
            if image.mode == 'RGBA':
                result.paste(image, (x, y), image)
            else:
                result.paste(image, (x, y))
            
            return result
            
        elif method == "fill":
            # Stretch to exact dimensions (may distort aspect ratio)
            return image.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
            
        elif method == "crop":
            # Preserve aspect ratio, crop excess to fit exactly
            img_ratio = image.width / image.height
            target_ratio = target_width_px / target_height_px
            
            if img_ratio > target_ratio:
                # Image is wider than target, crop width
                new_width = int(image.height * target_ratio)
                x = (image.width - new_width) // 2
                cropped = image.crop((x, 0, x + new_width, image.height))
            else:
                # Image is taller than target, crop height
                new_height = int(image.width / target_ratio)
                y = (image.height - new_height) // 2
                cropped = image.crop((0, y, image.width, y + new_height))
            
            return cropped.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
        
        else:
            # Default to fill method
            return image.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
            
    except Exception as e:
        st.error(f"Error resizing image: {str(e)}")
        return image

def remove_background(image, tight_crop=True):
    """Remove background from image with sharp cut option"""
    try:
        # Convert PIL to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Remove background
        output = rembg.remove(img_byte_arr)
        
        # Convert back to PIL
        result = Image.open(io.BytesIO(output))
        
        # Apply sharp cut post-processing if CV2 is available
        if tight_crop and is_cv2_available():
            try:
                # Convert to numpy array for processing
                output_array = np.array(result)
                if len(output_array.shape) == 3 and output_array.shape[2] == 4:
                    # Extract alpha channel
                    alpha = output_array[:, :, 3]
                    
                    # Apply morphological operations to create sharp cuts
                    # Create a small kernel for precise operations
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
                    
                    # Apply threshold to create sharp binary mask (remove soft edges)
                    _, alpha_binary = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
                    
                    # Use closing to fill small gaps in the mask
                    alpha_closed = cv2.morphologyEx(alpha_binary, cv2.MORPH_CLOSE, kernel, iterations=1)
                    
                    # Apply slight erosion to tighten the mask and remove fuzzy edges
                    alpha_tight = cv2.erode(alpha_closed, kernel, iterations=1)
                    
                    # Apply opening to remove small noise
                    alpha_clean = cv2.morphologyEx(alpha_tight, cv2.MORPH_OPEN, kernel, iterations=1)
                    
                    # Final threshold to ensure completely sharp edges (no anti-aliasing)
                    _, alpha_sharp = cv2.threshold(alpha_clean, 200, 255, cv2.THRESH_BINARY)
                    
                    # Update the alpha channel with sharp cut
                    output_array[:, :, 3] = alpha_sharp
                    result = Image.fromarray(output_array, 'RGBA')
                    
            except Exception as cv_error:
                st.warning(f"⚠️ Could not apply sharp cutting: {cv_error}")
                # Continue with original result if sharp cut processing fails
        
        return result
    except Exception as e:
        st.error(f"Background removal error: {str(e)}")
        return image

def refill_background(image, bg_color="white"):
    """Add solid color background to transparent image"""
    try:
        # Create background
        if isinstance(bg_color, str):
            background = Image.new('RGB', image.size, bg_color)
        else:
            background = Image.new('RGB', image.size, tuple(bg_color))
        
        # Paste image on background
        if image.mode == 'RGBA':
            background.paste(image, mask=image.split()[-1])
        else:
            background.paste(image)
        
        return background
    except Exception as e:
        st.error(f"Background refill error: {str(e)}")
        return image

def crop_to_passport_size(image, passport_type, faces=None):
    """Crop image to passport photo size based on face detection"""
    try:
        spec = PASSPORT_SPECS[passport_type]
        target_width = spec["width_px"]
        target_height = spec["height_px"]
        
        # Convert PIL to numpy array for processing
        image_array = np.array(image)
        h, w = image_array.shape[:2]
        
        # Convert face detection format
        face_bbox = None
        if faces and len(faces) > 0:
            face = faces[0]
            face_bbox = {
                'x': face['x'],
                'y': face['y'],
                'width': face['width'],
                'height': face['height'],
                'center_x': face['x'] + face['width'] // 2,
                'center_y': face['y'] + face['height'] // 2
            }
        
        if not face_bbox:
            # Fallback: center crop with aspect ratio preservation
            aspect_ratio = target_width / target_height
            
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
            
            cropped = image.crop(crop_box)
            resized = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
            return resized
        
        # Advanced face-based cropping
        face_center_x = face_bbox['center_x']
        face_center_y = face_bbox['center_y']
        face_height = face_bbox['height']
        face_top = face_bbox['y']
        face_bottom = face_bbox['y'] + face_bbox['height']
        
        # Use specification parameters
        upper_body_ratio = spec.get('upper_body_ratio', 0.3)
        head_top_padding_ratio = spec.get('head_top_padding', 0.15)
        target_face_height = spec['head_min_px'] * 0.85  # Use 85% of min for good padding
        
        # Calculate scale factor
        scale_factor = target_face_height / face_height
        
        # Calculate crop dimensions in original image
        crop_width = int(target_width / scale_factor)
        crop_height = int(target_height / scale_factor)
        
        # Ensure crop dimensions don't exceed image size
        if crop_width > w or crop_height > h:
            scale_factor_w = target_width / w
            scale_factor_h = target_height / h
            scale_factor = max(scale_factor_w, scale_factor_h)
            crop_width = int(target_width / scale_factor)
            crop_height = int(target_height / scale_factor)
        
        # Ensure minimum crop size (at least 50% of target)
        min_crop_width = int(target_width * 0.5)
        min_crop_height = int(target_height * 0.5)
        
        if crop_width < min_crop_width or crop_height < min_crop_height:
            crop_width = min(w, max(crop_width, min_crop_width))
            crop_height = min(h, max(crop_height, min_crop_height))
        
        # Estimate upper body area and head padding
        upper_body_height = int(face_height * upper_body_ratio)
        head_padding = int(face_height * 0.4)  # 40% for head padding
        estimated_head_top = face_top - head_padding
        
        # Calculate crop position
        crop_y = estimated_head_top - int(crop_height * head_top_padding_ratio)
        
        # Ensure upper body is included
        required_bottom = face_bottom + upper_body_height
        min_crop_y = required_bottom - crop_height
        crop_y = max(crop_y, min_crop_y)
        
        # Center horizontally on face
        crop_x = face_center_x - crop_width // 2
        
        # Handle different aspect ratios
        if h > w * 1.2:  # Tall image
            min_side_margin = int(w * 0.1)
            crop_x = max(min_side_margin, min(crop_x, w - crop_width - min_side_margin))
        
        if w > h * 1.2:  # Wide image
            min_top_margin = int(h * 0.1)
            crop_y = max(min_top_margin, min(crop_y, h - crop_height - min_top_margin))
        
        # Final boundary adjustments
        if crop_x < 0:
            crop_x = 0
        elif crop_x + crop_width > w:
            crop_x = w - crop_width
            
        if crop_y < 0:
            crop_y = 0
        elif crop_y + crop_height > h:
            crop_y = h - crop_height
        
        # Final safety check
        crop_x = max(0, min(crop_x, w - crop_width))
        crop_y = max(0, min(crop_y, h - crop_height))
        
        # Perform crop
        crop_box = (crop_x, crop_y, crop_x + crop_width, crop_y + crop_height)
        cropped = image.crop(crop_box)
        
        # Resize to exact target dimensions
        resized = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        return resized
        
    except Exception as e:
        st.error(f"Cropping error: {str(e)}")
        return image

def create_photo_sheet(passport_image_pil, passport_type, manual_crop_data=None):
    """Create a sheet of passport photos on 10cm × 15cm format"""
    try:
        # Use custom dimensions if manual crop data is provided
        if manual_crop_data and 'target_width_px' in manual_crop_data:
            # Custom photo dimensions
            photo_width = manual_crop_data['target_width_px']
            photo_height = manual_crop_data['target_height_px']
            custom_info = manual_crop_data.get('custom_size', {})
            
            # Calculate how many photos can fit on standard 10×15cm sheet
            sheet_spec = PHOTO_SHEET_SPECS
            available_width = sheet_spec["width_px"] - 2 * sheet_spec["margin_px"]
            available_height = sheet_spec["height_px"] - 2 * sheet_spec["margin_px"]
            
            # Calculate layout automatically based on photo size
            cols = max(1, available_width // (photo_width + 10))  # 10px minimum spacing
            rows = max(1, available_height // (photo_height + 10))
            
            layout = {"cols": cols, "rows": rows, "count": cols * rows}
            
            st.info(f"📋 **Custom Layout:** {cols}×{rows} grid = {layout['count']} photos per sheet")
            st.info(f"🎯 **Photo Size:** {custom_info.get('width', '?')}×{custom_info.get('height', '?')} {custom_info.get('unit', 'px')}")
            
        else:
            # Standard passport specifications
            if passport_type not in PASSPORT_SPECS:
                raise ValueError(f"Unknown passport type: {passport_type}")
            
            spec = PASSPORT_SPECS[passport_type]
            layout = spec["sheet_layout"]
            
            # Handle EU photo rotation (35×45mm rotated to fit better in 2×4 layout)
            if passport_type.startswith("EU"):
                # Rotate EU photos 90 degrees clockwise to fit better in 2×4 layout
                passport_image_pil = passport_image_pil.rotate(-90, expand=True)
                photo_width = spec["height_px"]  # 531px (was height, now width)
                photo_height = spec["width_px"]  # 413px (was width, now height)
            else:
                photo_width = spec["width_px"]
                photo_height = spec["height_px"]
        
        # Create white background sheet
        sheet_spec = PHOTO_SHEET_SPECS
        sheet = Image.new("RGB", (sheet_spec["width_px"], sheet_spec["height_px"]), "white")
        
        # Prepare photo to paste
        photo_to_paste = passport_image_pil.copy()
        
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
        
        # Place photos on the sheet with light gray borders for cutting guides
        border_width = 1  # 1 pixel light gray border
        border_color = (200, 200, 200)  # Light gray RGB
        
        for row in range(rows):
            for col in range(cols):
                if row * cols + col >= layout["count"]:
                    break
                    
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
        
    except Exception as e:
        st.error(f"Photo sheet creation error: {str(e)}")
        return passport_image_pil

def process_image(image, processing_type, **kwargs):
    """Main image processing function"""
    try:
        st.write(f"🔄 Starting {processing_type} processing...")
        result_image = image.copy()
        
        # Get manual crop data if provided
        manual_crop_data = kwargs.get('manual_crop_data', None)
        
        st.write("🔍 Detecting faces...")
        faces = detect_faces(result_image)
        st.write(f"✅ Found {len(faces)} face(s)")
        
        sheet_image = None
        
        if processing_type == "remove_bg":
            st.write("🎭 Removing background...")
            result_image = remove_background(result_image)
            
        elif processing_type == "refill_bg":
            st.write("🎭 Removing background...")
            result_image = remove_background(result_image)
            st.write("🎨 Refilling background...")
            bg_color = kwargs.get('background_color', 'white')
            result_image = refill_background(result_image, bg_color)
            
        elif processing_type == "crop_face":
            st.write("✂️ Cropping to passport size...")
            passport_type = kwargs.get('passport_type', 'US')
            
            # Step 1: Cropping
            if manual_crop_data:
                st.write("📐 Using manual crop coordinates...")
                result_image = apply_manual_crop(result_image, manual_crop_data)
                
                # Step 2: Resizing - use custom dimensions if provided
                if 'target_width_px' in manual_crop_data and 'target_height_px' in manual_crop_data:
                    st.write("📏 Resizing to custom dimensions...")
                    target_width = manual_crop_data['target_width_px']
                    target_height = manual_crop_data['target_height_px']
                    resize_method = manual_crop_data.get('resize_method', 'crop')
                    result_image = resize_to_target_dimensions(result_image, target_width, target_height, method=resize_method)
                else:
                    st.warning("⚠️ Manual crop enabled but no custom dimensions specified. Using cropped image as-is.")
            else:
                # Use automatic face detection cropping and standard passport size
                result_image = crop_to_passport_size(result_image, passport_type, faces)
            
        elif processing_type == "passport_photo":
            st.write("📋 Creating complete passport photo...")
            # Complete passport photo processing
            st.write("🎭 Removing background...")
            result_image = remove_background(result_image)
            st.write("🎨 Refilling background...")
            bg_color = kwargs.get('background_color', 'white')
            result_image = refill_background(result_image, bg_color)
            
            st.write("✂️ Cropping to passport size...")
            passport_type = kwargs.get('passport_type', 'US')
            
            # Step 1: Cropping
            if manual_crop_data:
                st.write("📐 Using manual crop coordinates...")
                result_image = apply_manual_crop(result_image, manual_crop_data)
                
                # Step 2: Resizing - use custom dimensions if provided
                if 'target_width_px' in manual_crop_data and 'target_height_px' in manual_crop_data:
                    st.write("📏 Resizing to custom dimensions...")
                    target_width = manual_crop_data['target_width_px']
                    target_height = manual_crop_data['target_height_px']
                    resize_method = manual_crop_data.get('resize_method', 'crop')
                    result_image = resize_to_target_dimensions(result_image, target_width, target_height, method=resize_method)
                    
                    # Use custom DPI for photo sheet if available
                    if 'target_dpi' in manual_crop_data:
                        custom_dpi = manual_crop_data['target_dpi']
                        # Store custom DPI in kwargs for photo sheet creation
                        kwargs['custom_dpi'] = custom_dpi
                else:
                    st.warning("⚠️ Manual crop enabled but no custom dimensions specified. Using cropped image as-is.")
            else:
                # Use automatic face detection cropping and standard passport size
                result_image = crop_to_passport_size(result_image, passport_type, faces)
            
            # Always create photo sheet for passport photos
            st.write("📄 Creating photo sheet...")
            # Pass manual crop data to photo sheet creation for custom layouts
            sheet_image = create_photo_sheet(result_image, passport_type, manual_crop_data)
        
        st.write("✅ Processing completed!")
        return result_image, faces, sheet_image
        
    except Exception as e:
        st.error(f"Image processing error: {str(e)}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}")
        return image, [], None

# Streamlit UI
def main():
    st.title("📸 ID Photo Maker")
    st.markdown("Complete ID photo processing with background removal and face detection")
    
    # Instructions - moved to top for better guidance
    with st.expander("📖 How to Use", expanded=False):
        st.markdown("""
        ### 🎯 Processing Options:
        
        1. **🎭 Remove Background**: Creates a transparent PNG background for your image
        2. **🎨 Remove & Refill Background**: Removes background and adds solid color (white, light blue, light red, light gray, or custom)
        3. **✂️ Crop to Passport Size**: Crops image to passport dimensions using AI face detection
        4. **📋 Complete Passport Photo**: Full processing + creates printable photo sheet (recommended)
        
        ### ✂️ Manual Crop Zone:
        **🎯 Define Your Own Passport Size** - When using "Crop to Passport Size" or "Complete Passport Photo":
        - ✅ **Enable Manual Crop Zone** checkbox to unlock custom dimensions
        - 📏 **Set any size**: Width × Height in inches, cm, or pixels
        - 🎚️ **Choose DPI**: 72-1200 DPI (300 DPI recommended for printing)
        - 🔄 **Resize method**: Crop (recommended), Fill, or Fit
        - 🎪 **Interactive cropping**: Drag and resize the crop frame on your image
        - 📋 **Auto layout**: Automatically calculates how many photos fit per sheet
        
        ### 📸 Standard Passport Types (when manual crop disabled):
        - **US**: 2×2 inch (600×600px @ 300 DPI) - 2 photos per sheet
        - **EU**: 35×45 mm (413×531px @ 300 DPI) - 8 photos per sheet  
        - **Vietnam**: 40×60 mm (472×709px @ 300 DPI) - 4 photos per sheet
        
        ### 📁 Supported File Formats:
        - **Standard**: JPG, JPEG, PNG
        - **Mobile**: HEIC, HEIF (iPhone photos)
        
        ### 💡 Tips for Best Results:
        - Use high-resolution images (recommended: 1200px+ width)
        - Ensure good lighting and clear face visibility
        - Face should be centered and looking straight at camera
        - Background removal works best with contrasting backgrounds
        - **Manual crop gives you full control** - perfect for specific requirements
        - Use "Crop" resize method to maintain compliance and avoid distortion
        - Photo sheets are optimized for 10×15cm professional printing
        - For passport photos, always use "Complete Passport Photo" option
        
        ### 🚀 Quick Start with Custom Size:
        1. Upload your image
        2. Select "Complete Passport Photo" 
        3. ✅ Check "Enable Manual Crop Zone"
        4. 📏 Enter your desired dimensions (e.g., 3×4 cm)
        5. 🎪 Adjust the crop frame on your image
        6. 🚀 Click "Process Image"
        """)
    
    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Processing type selection
        processing_type = st.selectbox(
            "Processing Type",
            options=[
                ("remove_bg", "🎭 Remove Background"),
                ("refill_bg", "🎨 Remove & Refill Background"),
                ("crop_face", "✂️ Crop to Passport Size"),
                ("passport_photo", "📋 Complete Passport Photo")
            ],
            format_func=lambda x: x[1]
        )[0]
        
        # Background color selection
        if processing_type in ["refill_bg", "passport_photo"]:
            # Create color options with visual indicators
            color_options = ["white", "light_gray", "light_blue", "light_red", "custom"]
            formatted_colors = [format_color_option(color, None) for color in color_options]
            
            bg_color_selection = st.selectbox(
                "Background Color",
                options=range(len(color_options)),
                format_func=lambda x: formatted_colors[x],
                help="Choose background color for your passport photo"
            )
            bg_color_option = color_options[bg_color_selection]
            
            # Show color preview below dropdown
            color_map = {
                "white": "#FFFFFF",
                "light_gray": "#B8B3B2",
                "light_blue": "#E6F3FF",
                "light_red": "#F5E6E8"
            }
            
            if bg_color_option != "custom":
                preview_color = color_map[bg_color_option]
                st.markdown(
                    f'<div style="background-color: {preview_color}; border: 1px solid #ccc; height: 30px; width: 100%; border-radius: 5px; margin-top: 5px;"></div>',
                    unsafe_allow_html=True
                )
            
            if bg_color_option == "custom":
                bg_color = st.color_picker("Pick a color", "#FFFFFF")
            else:
                color_map = {
                    "white": "#FFFFFF",         # US, VN regulation white
                    "light_gray": "#B8B3B2",    # EU regulation gray
                    "light_blue": "#E6F3FF",
                    "light_red": "#F5E6E8"
                }
                bg_color = color_map[bg_color_option]
        else:
            bg_color = "white"
        
        # Passport type selection
        if processing_type in ["crop_face", "passport_photo"]:
            passport_type = st.selectbox(
                "Passport Type",
                options=list(PASSPORT_SPECS.keys()),
                format_func=lambda x: format_passport_option(x, PASSPORT_SPECS[x])
            )
        else:
            passport_type = "US"
        
        # Photo sheet option
        # if processing_type == "passport_photo":
        #     create_sheet = st.checkbox("Create Photo Sheet for Printing", value=True)
        # else:
        #     create_sheet = False
        create_sheet = True  # Always create photo sheet for passport photos
    
    # Main content area
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("📁 Upload Image")
        uploaded_file = st.file_uploader(
            "Choose an image file",
            type=['jpg', 'jpeg', 'png', 'heic', 'heif'],
            help="Supported formats: JPG, PNG, HEIC/HEIF"
        )
        
        if uploaded_file is not None:
            # Display original image
            try:
                # Load image with HEIC support
                original_image = Image.open(uploaded_file)
                
                # Debug info
                # st.write(f"🔍 **Debug:** File type: {uploaded_file.type}, Original mode: {original_image.mode}")
                
                # Fix image orientation using EXIF data (handles mobile photos)
                original_image = ImageOps.exif_transpose(original_image)
                
                # Convert to RGB if needed (important for HEIC files)
                if original_image.mode != 'RGB':
                    st.write(f"🔄 Converting from {original_image.mode} to RGB")
                    original_image = original_image.convert('RGB')
                
                st.image(original_image, caption="Original Image", use_container_width=True)
                
                # Image info
                st.info(f"📊 **Image Info:** {original_image.width}×{original_image.height}px, {original_image.mode}")
                
                # Store image in session state for cropper
                st.session_state.current_image = original_image
                st.session_state.uploaded_image_info = {
                    'width': original_image.width,
                    'height': original_image.height
                }
                
                # Manual crop option for crop_face and passport_photo
                manual_crop_enabled = False
                manual_crop_data = None
                
                if processing_type in ["crop_face", "passport_photo"]:
                    st.markdown("---")
                    manual_crop_enabled = st.checkbox(
                        "✂️ Enable Manual Crop Zone", 
                        value=False,
                        help="Enable interactive crop zone to manually select the area before processing"
                    )
                    
                    if manual_crop_enabled and CROPPER_AVAILABLE:
                        st.markdown("**🎯 Interactive Crop Zone**")
                        st.markdown("*Drag to move, resize corners/edges to adjust crop area*")
                        
                        # Custom passport size options for manual crop
                        st.markdown("**📏 Custom Photo Size**")
                        col_size1, col_size2, col_size3 = st.columns([1, 1, 1])
                        
                        with col_size1:
                            custom_width = st.number_input(
                                "Width", 
                                min_value=0.1, 
                                max_value=50.0, 
                                value=2.0, 
                                step=0.1,
                                help="Photo width"
                            )
                        
                        with col_size2:
                            custom_height = st.number_input(
                                "Height", 
                                min_value=0.1, 
                                max_value=50.0, 
                                value=2.0, 
                                step=0.1,
                                help="Photo height"
                            )
                        
                        with col_size3:
                            custom_unit = st.selectbox(
                                "Unit",
                                options=["inch", "cm", "pixel"],
                                index=0,
                                help="Measurement unit"
                            )
                        
                        # Custom DPI for physical units
                        if custom_unit != "pixel":
                            custom_dpi = st.number_input(
                                "DPI (Dots Per Inch)", 
                                min_value=72, 
                                max_value=1200, 
                                value=300, 
                                step=25,
                                help="Resolution for print quality (300 DPI recommended for professional printing)"
                            )
                        else:
                            custom_dpi = 300  # Default DPI for pixel-based sizes
                        
                        # Resize method selection
                        resize_method = st.selectbox(
                            "Resize Method",
                            options=["crop", "fill", "fit"],
                            index=0,
                            help="Crop: preserve aspect ratio (may crop excess) - RECOMMENDED for compliance • Fill: stretch to exact size (may distort) • Fit: preserve aspect ratio (may add padding)"
                        )
                        
                        # Calculate target pixel dimensions for aspect ratio
                        if custom_unit == "inch":
                            target_width_px = int(custom_width * custom_dpi)
                            target_height_px = int(custom_height * custom_dpi)
                        elif custom_unit == "cm":
                            # Convert cm to inches then to pixels
                            target_width_px = int(custom_width / 2.54 * custom_dpi)
                            target_height_px = int(custom_height / 2.54 * custom_dpi)
                        else:  # pixel
                            target_width_px = int(custom_width)
                            target_height_px = int(custom_height)
                        
                        # Show calculated dimensions
                        st.info(f"📊 **Target Size:** {target_width_px}×{target_height_px}px @ {custom_dpi} DPI")
                        
                        # Calculate aspect ratio for cropper (width, height)
                        aspect_ratio = (target_width_px, target_height_px)
                        
                        # Pre-resize image to fit container width (streamlit-cropper default is 700px max)
                        # We want it to fit in the column, so use approximately 400px max width
                        display_image = original_image.copy()
                        max_display_width = 400  # Approximate column width
                        
                        if display_image.width > max_display_width:
                            ratio = max_display_width / display_image.width
                            new_height = int(display_image.height * ratio)
                            display_image = display_image.resize((max_display_width, new_height), Image.Resampling.LANCZOS)
                        
                        # Calculate scale factors for coordinate conversion
                        scale_x = original_image.width / display_image.width
                        scale_y = original_image.height / display_image.height
                        
                        # Create the interactive cropper with the pre-resized image
                        cropped_img = st_cropper(
                            display_image,  # Use pre-resized image
                            realtime_update=True,
                            box_color='#3b82f6',
                            aspect_ratio=aspect_ratio,  # Lock to custom aspect ratio
                            return_type='box',
                            should_resize_image=False,  # Don't resize again since we already did it
                            key='manual_cropper'
                        )
                        
                        if cropped_img:
                            # Scale coordinates back to original image size
                            manual_crop_data = {
                                'x': int(cropped_img['left'] * scale_x),
                                'y': int(cropped_img['top'] * scale_y),
                                'width': int(cropped_img['width'] * scale_x),
                                'height': int(cropped_img['height'] * scale_y),
                                # Store custom size info for processing
                                'target_width_px': target_width_px,
                                'target_height_px': target_height_px,
                                'target_dpi': custom_dpi,
                                'resize_method': resize_method,
                                'custom_size': {
                                    'width': custom_width,
                                    'height': custom_height,
                                    'unit': custom_unit,
                                    'dpi': custom_dpi
                                }
                            }
                            
                            # Show crop info
                            crop_area_percentage = (manual_crop_data['width'] * manual_crop_data['height']) / (original_image.width * original_image.height) * 100
                            st.success(f"✂️ **Crop Area:** {manual_crop_data['width']}×{manual_crop_data['height']}px at ({manual_crop_data['x']}, {manual_crop_data['y']})")
                            st.info(f"📏 **Coverage:** {crop_area_percentage:.1f}% of original image")
                            st.info(f"🎯 **Will resize to:** {target_width_px}×{target_height_px}px ({custom_width}×{custom_height} {custom_unit})")
                    
                    elif manual_crop_enabled and not CROPPER_AVAILABLE:
                        st.warning("⚠️ Interactive cropping not available. Install streamlit-cropper for this feature.")
                        manual_crop_enabled = False
                
                # Process button
                if st.button("🚀 Process Image", type="primary"):
                    # Generate timestamp at processing time for consistent naming
                    processing_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.session_state.download_timestamp = processing_timestamp
                    
                    with st.spinner("Processing image..."):
                        try:
                            processed_image, faces, sheet_image = process_image(
                                original_image,
                                processing_type,
                                background_color=bg_color,
                                passport_type=passport_type,
                                create_sheet=create_sheet,
                                manual_crop_data=manual_crop_data if manual_crop_enabled else None
                            )
                            
                            # Store results in session state
                            st.session_state.processed_image = processed_image
                            st.session_state.faces = faces
                            st.session_state.processing_type = processing_type
                            st.session_state.passport_type = passport_type  # Store passport type for DPI
                            st.session_state.sheet_image = sheet_image
                            st.session_state.manual_crop_data = manual_crop_data if manual_crop_enabled else None  # Store manual crop info
                            st.success("✅ Image processed successfully!")
                            
                        except Exception as proc_error:
                            st.error(f"❌ Error processing image: {str(proc_error)}")
                            st.error("Please try with a different image or check the file format.")
                    
            except Exception as e:
                st.error(f"Error loading image: {str(e)}")
    
    with col2:
        st.header("✨ Processed Result")
        
        if hasattr(st.session_state, 'processed_image'):
            processed_image = st.session_state.processed_image
            faces = st.session_state.faces
            sheet_image = getattr(st.session_state, 'sheet_image', None)
            stored_passport_type = getattr(st.session_state, 'passport_type', 'US')
            
            # Display processed image
            st.image(processed_image, caption="Single Passport Photo", use_container_width=True)
            
            # Face detection info
            if faces:
                st.success(f"✅ {len(faces)} face(s) detected")
            else:
                st.warning("⚠️ No faces detected")
            
            # Download button for single image
            if processed_image.mode == 'RGBA':
                img_byte_arr = save_image_with_dpi(processed_image, format='PNG', dpi=300)
                file_ext = "png"
            else:
                # Get DPI from passport specifications
                spec_dpi = PASSPORT_SPECS.get(stored_passport_type, {}).get('dpi', 300)
                img_byte_arr = save_image_with_dpi(processed_image, format='JPEG', dpi=spec_dpi, quality=95)
                file_ext = "jpg"
            
            # Use the stored timestamp for consistent naming
            timestamp = getattr(st.session_state, 'download_timestamp', datetime.now().strftime("%Y%m%d_%H%M%S"))
            filename = f"id_photo-{timestamp}-single.{file_ext}"
            
            st.download_button(
                label="📥 Download Single Photo",
                data=img_byte_arr,
                file_name=filename,
                mime=f"image/{file_ext}",
                type="secondary"
            )
            
            # Display photo sheet if available
            if sheet_image is not None:
                st.markdown("---")
                st.subheader("📋 Photo Sheet for Printing")
                st.image(sheet_image, caption="Photo Sheet (10×15cm)", use_container_width=True)
                
                # Download button for photo sheet
                sheet_dpi = PHOTO_SHEET_SPECS['dpi']
                sheet_byte_arr = save_image_with_dpi(sheet_image, format='JPEG', dpi=sheet_dpi, quality=95)
                
                # Use the same timestamp for consistent naming
                timestamp = getattr(st.session_state, 'download_timestamp', datetime.now().strftime("%Y%m%d_%H%M%S"))
                sheet_filename = f"id_photo-{timestamp}-sheet.jpg"
                
                st.download_button(
                    label="📥 Download Photo Sheet",
                    data=sheet_byte_arr,
                    file_name=sheet_filename,
                    mime="image/jpeg",
                    type="primary"
                )
            
            # Image specifications
            if st.session_state.processing_type in ["crop_face", "passport_photo"]:
                # Check if manual crop was used
                stored_manual_crop = getattr(st.session_state, 'manual_crop_data', None)
                
                if stored_manual_crop and 'custom_size' in stored_manual_crop:
                    # Display user-defined dimensions from manual crop
                    custom_size = stored_manual_crop['custom_size']
                    custom_width = custom_size['width']
                    custom_height = custom_size['height']
                    custom_unit = custom_size['unit']
                    custom_dpi = custom_size['dpi']
                    target_width_px = stored_manual_crop['target_width_px']
                    target_height_px = stored_manual_crop['target_height_px']
                    
                    # Calculate photos per sheet for custom size
                    sheet_spec = PHOTO_SHEET_SPECS
                    available_width = sheet_spec["width_px"] - 2 * sheet_spec["margin_px"]
                    available_height = sheet_spec["height_px"] - 2 * sheet_spec["margin_px"]
                    cols = max(1, available_width // (target_width_px + 10))
                    rows = max(1, available_height // (target_height_px + 10))
                    photos_per_sheet = cols * rows
                    
                    st.info(f"""
                    **📏 Passport Specifications:**
                    - Size: {custom_width}×{custom_height} {custom_unit}
                    - Resolution: {target_width_px}×{target_height_px}px @ {custom_dpi} DPI
                    - Photos per sheet: {photos_per_sheet}
                    """)
                else:
                    # Display standard passport specifications
                    spec = PASSPORT_SPECS[stored_passport_type]
                    # Determine size display format
                    if 'width_mm' in spec:
                        size_display = f"{spec['width_mm']}×{spec['height_mm']} mm"
                    else:
                        size_display = f"{spec['width_inch']}×{spec['height_inch']} inch"
                    
                    st.info(f"""
                    **📏 Passport Specifications:**
                    - Size: {size_display}
                    - Resolution: {spec['width_px']}×{spec['height_px']}px @ {spec['dpi']} DPI
                    - Photos per sheet: {spec['sheet_layout']['count']}
                    """)
        else:
            st.info("👆 Upload an image and click 'Process Image' to see results here")

if __name__ == "__main__":
    main()
