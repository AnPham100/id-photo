// Global variables
let selectedFile = null;
let currentStep = 1;
let selectedProcessingType = null;
let passportSpecs = {};
let heicConvertedCache = null; // Cache for converted HEIC to JPG (same size as original)

// Manual cropping variables
let isManualCroppingEnabled = false;
let cropCanvas = null;
let cropCtx = null;
let cropImage = null;
let cropFrame = { x: 0, y: 0, width: 413, height: 531 }; // Default US passport size in pixels
let cropZoom = 1;
let cropOffset = { x: 0, y: 0 };
let isDragging = false;
let isResizing = false;
let dragStart = { x: 0, y: 0 };
let resizeHandle = null;
let frameAspectRatio = 413 / 531; // Default aspect ratio

// Touch handling variables
let lastTouchDistance = 0;
let lastTouchCenter = { x: 0, y: 0 };
let isTouchDragging = false;
let isTouchResizing = false;
let touchStartTime = 0;

// DOM elements
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const step1 = document.getElementById('step1');
const step2 = document.getElementById('step2');
const step3 = document.getElementById('step3');
const progressContainer = document.getElementById('progressContainer');
const resultContainer = document.getElementById('resultContainer');
const processBtn = document.getElementById('processBtn');
const downloadBtn = document.getElementById('downloadBtn');
const downloadSheetBtn = document.getElementById('downloadSheetBtn');
const retryBtn = document.getElementById('retryBtn');

// Color options
const colorOptions = [
    { id: "white", value: "white", label: "White", preview: "#FFFFFF" },
    { id: "blue", value: "blue", label: "Blue", preview: "#3B82F6" },
    { id: "red", value: "red", label: "Red", preview: "#EF4444" },
    { id: "gray", value: "gray", label: "Gray", preview: "#B8B3B2" },
    { id: "custom", value: "custom", label: "Custom", preview: null }
];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    populateColorOptions();
    fetchPassportSpecs();
    updatePixelDimensions(); // Initialize pixel dimensions display
});

function initializeEventListeners() {
    // File upload
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);

    // Processing type selection
    document.querySelectorAll('.processing-option').forEach(option => {
        option.addEventListener('click', selectProcessingType);
    });

    // Process button
    processBtn.addEventListener('click', processImage);

    // Download button
    downloadBtn.addEventListener('click', downloadImage);
    
    // Download sheet button
    downloadSheetBtn.addEventListener('click', downloadSheet);

    // Retry button
    retryBtn.addEventListener('click', goToStep2);
    
    // Manual cropping events
    initializeManualCroppingEvents();
}

function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('border-blue-400', 'bg-blue-50');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('border-blue-400', 'bg-blue-50');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('border-blue-400', 'bg-blue-50');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelect({ target: { files: files } });
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Enhanced validation for HEIC files
    const isValidImage = file.type.startsWith('image/') || 
                        file.type === 'image/heic' || 
                        file.type === 'image/heif' ||
                        file.name.toLowerCase().endsWith('.heic') ||
                        file.name.toLowerCase().endsWith('.heif');

    if (!isValidImage) {
        showAlert('Please select a valid image file (JPG, PNG, WEBP, HEIC)', 'error');
        return;
    }

    if (file.size > 20 * 1024 * 1024) { // 20MB limit
        showAlert('File size must be less than 20MB', 'error');
        return;
    }

    selectedFile = file;
    heicConvertedCache = null; // Reset converted cache when new file is selected
    
    // Reset manual cropping
    isManualCroppingEnabled = false;
    document.getElementById('manualCropCheckbox').checked = false;
    document.getElementById('manualCroppingSection').classList.add('hidden');
    
    displaySelectedFile(file);
    goToStep2();
}

function displaySelectedFile(file) {
    const reader = new FileReader();
    reader.onload = function(e) {
        uploadArea.innerHTML = `
            <div class="flex flex-col items-center justify-center space-y-2 text-center">
                <img src="${e.target.result}" class="max-h-32 rounded-lg shadow-md">
                <p class="text-gray-700 font-medium">${file.name}</p>
                <p class="text-sm text-gray-500">File ready for processing</p>
            </div>
        `;
    };
    reader.readAsDataURL(file);
}

function selectProcessingType(e) {
    // Remove selection from all options
    document.querySelectorAll('.processing-option').forEach(option => {
        option.classList.remove('selected');
    });

    // Add selection to clicked option
    e.currentTarget.classList.add('selected');
    selectedProcessingType = e.currentTarget.dataset.type;

    // Show step 3 and configure settings based on selection
    goToStep3();
}

function goToStep2() {
    currentStep = 2;
    updateStepIndicators();
    step1.classList.add('hidden');
    step2.classList.remove('hidden');
    step3.classList.add('hidden');
    resultContainer.classList.add('hidden');
}

function goToStep3() {
    currentStep = 3;
    updateStepIndicators();
    step2.classList.add('hidden');
    step3.classList.remove('hidden');
    
    // Reset manual cropping to unchecked by default
    isManualCroppingEnabled = false;
    document.getElementById('manualCropCheckbox').checked = false;
    document.getElementById('manualCroppingSection').classList.add('hidden');
    
    // Ensure passport options are enabled and restored
    disablePassportOptions(false);
    
    configureSettingsForProcessingType();
}

function configureSettingsForProcessingType() {
    const backgroundColorSection = document.getElementById('backgroundColorSection');
    const passportTypeSection = document.getElementById('passportTypeSection');

    // Hide all sections first
    backgroundColorSection.classList.add('hidden');
    passportTypeSection.classList.add('hidden');

    // Show relevant sections based on processing type
    if (selectedProcessingType === 'refill_bg' || selectedProcessingType === 'passport_photo') {
        backgroundColorSection.classList.remove('hidden');
    }

    if (selectedProcessingType === 'crop_face' || selectedProcessingType === 'passport_photo') {
        passportTypeSection.classList.remove('hidden');
        populatePassportOptions();
    }
}

// Manual Cropping Functions
function initializeManualCroppingEvents() {
    const manualCropCheckbox = document.getElementById('manualCropCheckbox');
    const cropWidthInput = document.getElementById('cropWidth');
    const cropHeightInput = document.getElementById('cropHeight');
    const cropUnitSelect = document.getElementById('cropUnit');
    const applyCustomSizeBtn = document.getElementById('applyCustomSize');
    const zoomInBtn = document.getElementById('zoomIn');
    const zoomOutBtn = document.getElementById('zoomOut');
    const resetZoomBtn = document.getElementById('resetZoom');

    manualCropCheckbox.addEventListener('change', toggleManualCropping);
    cropWidthInput.addEventListener('input', updatePixelDimensions);
    cropHeightInput.addEventListener('input', updatePixelDimensions);
    cropUnitSelect.addEventListener('change', updatePixelDimensions);
    applyCustomSizeBtn.addEventListener('click', applyCropSize);
    zoomInBtn.addEventListener('click', () => adjustZoom(1.2));
    zoomOutBtn.addEventListener('click', () => adjustZoom(0.8));
    resetZoomBtn.addEventListener('click', resetCropZoom);
}

function toggleManualCropping() {
    const checkbox = document.getElementById('manualCropCheckbox');
    const manualCroppingSection = document.getElementById('manualCroppingSection');
    const passportOptions = document.querySelectorAll('.passport-option');
    
    isManualCroppingEnabled = checkbox.checked;
    
    console.log('Manual cropping toggled:', isManualCroppingEnabled);
    
    if (isManualCroppingEnabled) {
        manualCroppingSection.classList.remove('hidden');
        
        // Clear and disable passport type selections
        clearPassportSelection();
        disablePassportOptions(true);
        
        // Wait a bit for the DOM to update, then setup canvas
        setTimeout(() => {
            setupCropCanvas();
        }, 100);
    } else {
        manualCroppingSection.classList.add('hidden');
        
        // Re-enable passport options and restore default selection
        disablePassportOptions(false);
        restoreDefaultPassportSelection();
        
        // Clean up canvas
        if (cropCanvas) {
            cropCanvas.removeEventListener('mousedown', handleCropMouseDown);
            cropCanvas.removeEventListener('mousemove', handleCropMouseMove);
            cropCanvas.removeEventListener('mouseup', handleCropMouseUp);
            cropCanvas.removeEventListener('mouseleave', handleCropMouseUp);
            cropCanvas.removeEventListener('wheel', handleCropWheel);
            
            // Remove touch event listeners
            cropCanvas.removeEventListener('touchstart', handleCropTouchStart);
            cropCanvas.removeEventListener('touchmove', handleCropTouchMove);
            cropCanvas.removeEventListener('touchend', handleCropTouchEnd);
        }
    }
}

function setupCropCanvas() {
    if (!selectedFile) {
        console.error('No file selected for cropping');
        return;
    }
    
    cropCanvas = document.getElementById('cropCanvas');
    const placeholder = document.getElementById('cropCanvasPlaceholder');
    
    if (!cropCanvas) {
        console.error('Crop canvas element not found');
        return;
    }
    
    // Hide placeholder and show canvas
    if (placeholder) placeholder.style.display = 'none';
    cropCanvas.style.display = 'block';
    
    cropCtx = cropCanvas.getContext('2d');
    
    console.log('Setting up crop canvas for file:', selectedFile.name);
    
    // Load image into canvas - handle HEIC files
    const isHEIC = selectedFile.type === 'image/heic' || 
                   selectedFile.type === 'image/heif' || 
                   selectedFile.name.toLowerCase().endsWith('.heic') || 
                   selectedFile.name.toLowerCase().endsWith('.heif');
    
    if (isHEIC && heicConvertedCache) {
        // Use cached HEIC converted image (same size as original)
        console.log('Using cached HEIC converted image for crop canvas');
        cropImage = new Image();
        cropImage.onload = function() {
            console.log('HEIC converted image loaded for cropping:', cropImage.width, 'x', cropImage.height);
            initializeCropCanvas();
        };
        cropImage.onerror = function() {
            console.error('Failed to load HEIC converted image for cropping');
            showCropError();
        };
        cropImage.src = heicConvertedCache.dataUrl;
    } else if (isHEIC) {
        // Need to convert HEIC first
        console.log('Converting HEIC for crop canvas');
        convertHEICForCrop();
    } else {
        // Use file reader for other formats
        const reader = new FileReader();
        reader.onload = function(e) {
            cropImage = new Image();
            cropImage.onload = function() {
                console.log('Image loaded for cropping:', cropImage.width, 'x', cropImage.height);
                initializeCropCanvas();
            };
            cropImage.onerror = function() {
                console.error('Failed to load image for cropping');
                showCropError();
            };
            cropImage.src = e.target.result;
        };
        reader.onerror = function() {
            console.error('Failed to read file for cropping');
            showCropError();
        };
        reader.readAsDataURL(selectedFile);
    }
}

async function convertHEICForCrop() {
    try {
        console.log('Converting HEIC to JPG for cropping...');
        const formData = new FormData();
        formData.append('file', selectedFile);

        const response = await fetch('/convert-img?output_format=jpeg&keep_original_size=true', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                heicConvertedCache = {
                    dataUrl: `data:image/jpeg;base64,${result.image}`,
                    width: result.width,
                    height: result.height,
                    originalWidth: result.original_width,
                    originalHeight: result.original_height
                };
                
                console.log('HEIC converted to JPG:', heicConvertedCache.width, 'x', heicConvertedCache.height);
                
                // Load the converted image into crop canvas
                cropImage = new Image();
                cropImage.onload = function() {
                    console.log('HEIC converted image loaded for cropping:', cropImage.width, 'x', cropImage.height);
                    initializeCropCanvas();
                };
                cropImage.onerror = function() {
                    console.error('Failed to load converted HEIC image');
                    showCropError();
                };
                cropImage.src = heicConvertedCache.dataUrl;
            } else {
                throw new Error('HEIC conversion failed');
            }
        } else {
            throw new Error(`HEIC conversion request failed: ${response.status}`);
        }
    } catch (error) {
        console.error('Error converting HEIC for crop:', error);
        showCropError();
    }
}

function showCropError() {
    const placeholder = document.getElementById('cropCanvasPlaceholder');
    if (placeholder) {
        placeholder.innerHTML = `
            <div class="text-center text-red-500">
                <div class="mb-2">
                    <svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                </div>
                <p>Failed to load image for cropping</p>
                <p class="text-xs text-gray-500 mt-1">Try uploading a different image</p>
            </div>
        `;
        placeholder.style.display = 'block';
    }
    cropCanvas.style.display = 'none';
}

function initializeCropCanvas() {
    if (!cropImage || !cropCanvas) {
        console.error('Missing crop image or canvas');
        return;
    }
    
    const container = document.getElementById('cropCanvasContainer');
    const maxWidth = Math.min(container.clientWidth - 40, 800); // Leave space for zoom controls
    const maxHeight = 500;
    
    console.log('Container size:', container.clientWidth, 'Image size:', cropImage.width, 'x', cropImage.height);
    
    // Calculate canvas size maintaining aspect ratio
    const imageAspect = cropImage.width / cropImage.height;
    let canvasWidth = Math.min(maxWidth, cropImage.width);
    let canvasHeight = canvasWidth / imageAspect;
    
    if (canvasHeight > maxHeight) {
        canvasHeight = maxHeight;
        canvasWidth = canvasHeight * imageAspect;
    }
    
    console.log('Setting canvas size:', canvasWidth, 'x', canvasHeight);
    
    cropCanvas.width = canvasWidth;
    cropCanvas.height = canvasHeight;
    cropCanvas.style.display = 'block';
    
    // Reset zoom and offset
    cropZoom = 1;
    cropOffset.x = 0;
    cropOffset.y = 0;
    
    // Initialize crop frame in center (make it smaller for better visibility)
    const frameWidth = Math.min(cropFrame.width * canvasWidth / cropImage.width, canvasWidth * 0.6);
    const frameHeight = Math.min(cropFrame.height * canvasHeight / cropImage.height, canvasHeight * 0.6);
    
    cropFrame.x = (canvasWidth - frameWidth) / 2;
    cropFrame.y = (canvasHeight - frameHeight) / 2;
    cropFrame.width = frameWidth;
    cropFrame.height = frameHeight;
    
    console.log('Initial crop frame:', cropFrame);
    
    // Remove existing event listeners
    cropCanvas.removeEventListener('mousedown', handleCropMouseDown);
    cropCanvas.removeEventListener('mousemove', handleCropMouseMove);
    cropCanvas.removeEventListener('mouseup', handleCropMouseUp);
    cropCanvas.removeEventListener('wheel', handleCropWheel);
    
    // Add canvas event listeners for mouse
    cropCanvas.addEventListener('mousedown', handleCropMouseDown);
    cropCanvas.addEventListener('mousemove', handleCropMouseMove);
    cropCanvas.addEventListener('mouseup', handleCropMouseUp);
    cropCanvas.addEventListener('mouseleave', handleCropMouseUp); // Stop dragging when leaving canvas
    cropCanvas.addEventListener('wheel', handleCropWheel, { passive: false });
    
    // Add touch event listeners for mobile
    cropCanvas.addEventListener('touchstart', handleCropTouchStart, { passive: false });
    cropCanvas.addEventListener('touchmove', handleCropTouchMove, { passive: false });
    cropCanvas.addEventListener('touchend', handleCropTouchEnd, { passive: false });
    
    // Initial draw
    drawCropCanvas();
}

function updatePixelDimensions() {
    const width = parseFloat(document.getElementById('cropWidth').value) || 0;
    const height = parseFloat(document.getElementById('cropHeight').value) || 0;
    const unit = document.getElementById('cropUnit').value;
    
    let pixelWidth, pixelHeight;
    
    // Convert to pixels (assuming 300 DPI for print)
    switch (unit) {
        case 'cm':
            pixelWidth = Math.round(width * 118.11); // 300 DPI conversion
            pixelHeight = Math.round(height * 118.11);
            break;
        case 'inch':
            pixelWidth = Math.round(width * 300); // 300 DPI
            pixelHeight = Math.round(height * 300);
            break;
        case 'px':
            pixelWidth = Math.round(width);
            pixelHeight = Math.round(height);
            break;
    }
    
    document.getElementById('pixelDimensions').textContent = `≈ ${pixelWidth} × ${pixelHeight} pixels`;
}

function applyCropSize() {
    const width = parseFloat(document.getElementById('cropWidth').value) || 0;
    const height = parseFloat(document.getElementById('cropHeight').value) || 0;
    const unit = document.getElementById('cropUnit').value;
    
    if (width <= 0 || height <= 0) {
        showAlert('Please enter valid width and height values', 'error');
        return;
    }
    
    // Calculate aspect ratio from user input
    frameAspectRatio = width / height;
    
    // Convert to pixels
    let pixelWidth, pixelHeight;
    switch (unit) {
        case 'cm':
            pixelWidth = Math.round(width * 118.11);
            pixelHeight = Math.round(height * 118.11);
            break;
        case 'inch':
            pixelWidth = Math.round(width * 300);
            pixelHeight = Math.round(height * 300);
            break;
        case 'px':
            pixelWidth = Math.round(width);
            pixelHeight = Math.round(height);
            break;
    }
    
    // Scale to canvas coordinates if image is loaded
    if (cropCanvas && cropImage) {
        // Calculate how the image fits in the canvas
        const canvasAspect = cropCanvas.width / cropCanvas.height;
        const imageAspect = cropImage.width / cropImage.height;
        
        let displayWidth, displayHeight;
        
        if (imageAspect > canvasAspect) {
            displayWidth = cropCanvas.width;
            displayHeight = cropCanvas.width / imageAspect;
        } else {
            displayHeight = cropCanvas.height;
            displayWidth = cropCanvas.height * imageAspect;
        }
        
        // Scale the frame to canvas coordinates
        const scaleToCanvas = Math.min(displayWidth / cropImage.width, displayHeight / cropImage.height);
        cropFrame.width = pixelWidth * scaleToCanvas;
        cropFrame.height = pixelHeight * scaleToCanvas;
        
        // Ensure frame fits in canvas
        const maxWidth = cropCanvas.width * 0.9;
        const maxHeight = cropCanvas.height * 0.9;
        
        if (cropFrame.width > maxWidth) {
            cropFrame.width = maxWidth;
            cropFrame.height = cropFrame.width / frameAspectRatio;
        }
        
        if (cropFrame.height > maxHeight) {
            cropFrame.height = maxHeight;
            cropFrame.width = cropFrame.height * frameAspectRatio;
        }
        
        // Center the frame
        cropFrame.x = (cropCanvas.width - cropFrame.width) / 2;
        cropFrame.y = (cropCanvas.height - cropFrame.height) / 2;
        
        drawCropCanvas();
        console.log('Applied crop size:', {
            input: { width, height, unit },
            pixels: { width: pixelWidth, height: pixelHeight },
            frame: cropFrame,
            aspectRatio: frameAspectRatio
        });
    } else {
        // Just store the values for when canvas is ready
        cropFrame.width = pixelWidth;
        cropFrame.height = pixelHeight;
    }
}

function adjustZoom(factor) {
    cropZoom *= factor;
    cropZoom = Math.max(0.1, Math.min(5, cropZoom)); // Limit zoom range
    drawCropCanvas();
}

function resetCropZoom() {
    cropZoom = 1;
    cropOffset.x = 0;
    cropOffset.y = 0;
    drawCropCanvas();
}

function handleCropMouseDown(e) {
    e.preventDefault();
    const rect = cropCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    console.log('Mouse down at:', x, y, 'Crop frame:', cropFrame);
    
    // Check if clicking on resize handles first
    const handleSize = 10;
    const handles = [
        { x: cropFrame.x - handleSize/2, y: cropFrame.y - handleSize/2, type: 'nw' },
        { x: cropFrame.x + cropFrame.width - handleSize/2, y: cropFrame.y - handleSize/2, type: 'ne' },
        { x: cropFrame.x - handleSize/2, y: cropFrame.y + cropFrame.height - handleSize/2, type: 'sw' },
        { x: cropFrame.x + cropFrame.width - handleSize/2, y: cropFrame.y + cropFrame.height - handleSize/2, type: 'se' }
    ];
    
    for (let handle of handles) {
        if (x >= handle.x && x <= handle.x + handleSize &&
            y >= handle.y && y <= handle.y + handleSize) {
            isResizing = true;
            resizeHandle = handle.type;
            dragStart.x = x;
            dragStart.y = y;
            cropCanvas.style.cursor = handle.type + '-resize';
            console.log('Started resizing from handle:', handle.type);
            return;
        }
    }
    
    // Check if clicking inside crop frame for dragging
    if (x >= cropFrame.x && x <= cropFrame.x + cropFrame.width &&
        y >= cropFrame.y && y <= cropFrame.y + cropFrame.height) {
        isDragging = true;
        dragStart.x = x - cropFrame.x;
        dragStart.y = y - cropFrame.y;
        cropCanvas.style.cursor = 'move';
        console.log('Started dragging crop frame');
    }
}

function handleCropMouseMove(e) {
    e.preventDefault();
    const rect = cropCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    if (isResizing && resizeHandle) {
        const deltaX = x - dragStart.x;
        const deltaY = y - dragStart.y;
        
        resizeCropFrame(resizeHandle, deltaX, deltaY);
        dragStart.x = x;
        dragStart.y = y;
        drawCropCanvas();
    } else if (isDragging) {
        const newX = x - dragStart.x;
        const newY = y - dragStart.y;
        
        // Keep frame within canvas bounds
        cropFrame.x = Math.max(0, Math.min(cropCanvas.width - cropFrame.width, newX));
        cropFrame.y = Math.max(0, Math.min(cropCanvas.height - cropFrame.height, newY));
        
        drawCropCanvas();
    } else {
        // Update cursor based on position
        updateCursor(x, y);
    }
}

function updateCursor(x, y) {
    // Use larger handles for touch devices
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const handleSize = isTouchDevice ? 15 : 10;
    
    const handles = [
        { x: cropFrame.x - handleSize/2, y: cropFrame.y - handleSize/2, cursor: 'nw-resize' },
        { x: cropFrame.x + cropFrame.width - handleSize/2, y: cropFrame.y - handleSize/2, cursor: 'ne-resize' },
        { x: cropFrame.x - handleSize/2, y: cropFrame.y + cropFrame.height - handleSize/2, cursor: 'sw-resize' },
        { x: cropFrame.x + cropFrame.width - handleSize/2, y: cropFrame.y + cropFrame.height - handleSize/2, cursor: 'se-resize' }
    ];
    
    for (let handle of handles) {
        if (x >= handle.x && x <= handle.x + handleSize &&
            y >= handle.y && y <= handle.y + handleSize) {
            cropCanvas.style.cursor = handle.cursor;
            return;
        }
    }
    
    if (x >= cropFrame.x && x <= cropFrame.x + cropFrame.width &&
        y >= cropFrame.y && y <= cropFrame.y + cropFrame.height) {
        cropCanvas.style.cursor = 'move';
    } else {
        cropCanvas.style.cursor = 'crosshair';
    }
}

function resizeCropFrame(handle, deltaX, deltaY) {
    const originalFrame = { ...cropFrame };
    
    // Calculate the desired size change based on the handle
    let newWidth = cropFrame.width;
    let newHeight = cropFrame.height;
    let newX = cropFrame.x;
    let newY = cropFrame.y;
    
    switch (handle) {
        case 'se': // Bottom-right corner
            newWidth = cropFrame.width + deltaX;
            newHeight = newWidth / frameAspectRatio; // Maintain aspect ratio
            break;
        case 'sw': // Bottom-left corner
            newWidth = cropFrame.width - deltaX;
            newHeight = newWidth / frameAspectRatio;
            newX = cropFrame.x + deltaX;
            break;
        case 'ne': // Top-right corner
            newWidth = cropFrame.width + deltaX;
            newHeight = newWidth / frameAspectRatio;
            newY = cropFrame.y + cropFrame.height - newHeight;
            break;
        case 'nw': // Top-left corner
            newWidth = cropFrame.width - deltaX;
            newHeight = newWidth / frameAspectRatio;
            newX = cropFrame.x + deltaX;
            newY = cropFrame.y + cropFrame.height - newHeight;
            break;
    }
    
    // Enforce minimum size
    const minSize = 50;
    if (newWidth < minSize) {
        newWidth = minSize;
        newHeight = newWidth / frameAspectRatio;
    }
    
    // Keep frame within canvas bounds
    if (newX < 0) {
        newX = 0;
        newWidth = originalFrame.x + originalFrame.width;
        newHeight = newWidth / frameAspectRatio;
    }
    if (newY < 0) {
        newY = 0;
        newHeight = originalFrame.y + originalFrame.height;
        newWidth = newHeight * frameAspectRatio;
    }
    if (newX + newWidth > cropCanvas.width) {
        newWidth = cropCanvas.width - newX;
        newHeight = newWidth / frameAspectRatio;
    }
    if (newY + newHeight > cropCanvas.height) {
        newHeight = cropCanvas.height - newY;
        newWidth = newHeight * frameAspectRatio;
    }
    
    // Apply the changes
    cropFrame.x = newX;
    cropFrame.y = newY;
    cropFrame.width = newWidth;
    cropFrame.height = newHeight;
}

function handleCropMouseUp(e) {
    e.preventDefault();
    isDragging = false;
    isResizing = false;
    resizeHandle = null;
    cropCanvas.style.cursor = 'crosshair';
    console.log('Mouse up - stopped dragging/resizing');
}

function handleCropWheel(e) {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    adjustZoom(factor);
}

// Touch Event Handlers for Mobile
function handleCropTouchStart(e) {
    e.preventDefault();
    const touches = e.touches;
    touchStartTime = Date.now();
    
    if (touches.length === 1) {
        // Single touch - handle dragging or resizing
        const touch = touches[0];
        const rect = cropCanvas.getBoundingClientRect();
        const x = touch.clientX - rect.left;
        const y = touch.clientY - rect.top;
        
        console.log('Touch start at:', x, y);
        
        // Check if touching resize handles first
        const handleSize = 15; // Larger handles for touch
        const handles = [
            { x: cropFrame.x - handleSize/2, y: cropFrame.y - handleSize/2, type: 'nw' },
            { x: cropFrame.x + cropFrame.width - handleSize/2, y: cropFrame.y - handleSize/2, type: 'ne' },
            { x: cropFrame.x - handleSize/2, y: cropFrame.y + cropFrame.height - handleSize/2, type: 'sw' },
            { x: cropFrame.x + cropFrame.width - handleSize/2, y: cropFrame.y + cropFrame.height - handleSize/2, type: 'se' }
        ];
        
        for (let handle of handles) {
            if (x >= handle.x && x <= handle.x + handleSize &&
                y >= handle.y && y <= handle.y + handleSize) {
                isTouchResizing = true;
                resizeHandle = handle.type;
                dragStart.x = x;
                dragStart.y = y;
                console.log('Started touch resizing from handle:', handle.type);
                return;
            }
        }
        
        // Check if touching inside crop frame for dragging
        if (x >= cropFrame.x && x <= cropFrame.x + cropFrame.width &&
            y >= cropFrame.y && y <= cropFrame.y + cropFrame.height) {
            isTouchDragging = true;
            dragStart.x = x - cropFrame.x;
            dragStart.y = y - cropFrame.y;
            console.log('Started touch dragging crop frame');
        }
    } else if (touches.length === 2) {
        // Two touches - handle pinch to zoom
        const touch1 = touches[0];
        const touch2 = touches[1];
        const rect = cropCanvas.getBoundingClientRect();
        
        const x1 = touch1.clientX - rect.left;
        const y1 = touch1.clientY - rect.top;
        const x2 = touch2.clientX - rect.left;
        const y2 = touch2.clientY - rect.top;
        
        lastTouchDistance = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
        lastTouchCenter.x = (x1 + x2) / 2;
        lastTouchCenter.y = (y1 + y2) / 2;
        
        console.log('Started pinch gesture, distance:', lastTouchDistance);
    }
}

function handleCropTouchMove(e) {
    e.preventDefault();
    const touches = e.touches;
    
    if (touches.length === 1 && (isTouchDragging || isTouchResizing)) {
        // Single touch - handle dragging or resizing
        const touch = touches[0];
        const rect = cropCanvas.getBoundingClientRect();
        const x = touch.clientX - rect.left;
        const y = touch.clientY - rect.top;
        
        if (isTouchResizing && resizeHandle) {
            const deltaX = x - dragStart.x;
            const deltaY = y - dragStart.y;
            
            resizeCropFrame(resizeHandle, deltaX, deltaY);
            dragStart.x = x;
            dragStart.y = y;
            drawCropCanvas();
        } else if (isTouchDragging) {
            const newX = x - dragStart.x;
            const newY = y - dragStart.y;
            
            // Keep frame within canvas bounds
            cropFrame.x = Math.max(0, Math.min(cropCanvas.width - cropFrame.width, newX));
            cropFrame.y = Math.max(0, Math.min(cropCanvas.height - cropFrame.height, newY));
            
            drawCropCanvas();
        }
    } else if (touches.length === 2) {
        // Two touches - handle pinch to zoom
        const touch1 = touches[0];
        const touch2 = touches[1];
        const rect = cropCanvas.getBoundingClientRect();
        
        const x1 = touch1.clientX - rect.left;
        const y1 = touch1.clientY - rect.top;
        const x2 = touch2.clientX - rect.left;
        const y2 = touch2.clientY - rect.top;
        
        const currentDistance = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
        const currentCenter = { x: (x1 + x2) / 2, y: (y1 + y2) / 2 };
        
        if (lastTouchDistance > 0) {
            // Calculate zoom factor based on distance change
            const zoomFactor = currentDistance / lastTouchDistance;
            const newZoom = cropZoom * zoomFactor;
            
            // Apply zoom with bounds
            cropZoom = Math.max(0.1, Math.min(5, newZoom));
            
            // Adjust offset to zoom towards the center of pinch
            const centerDeltaX = currentCenter.x - lastTouchCenter.x;
            const centerDeltaY = currentCenter.y - lastTouchCenter.y;
            
            cropOffset.x += centerDeltaX * 0.5;
            cropOffset.y += centerDeltaY * 0.5;
            
            drawCropCanvas();
        }
        
        lastTouchDistance = currentDistance;
        lastTouchCenter = currentCenter;
    }
}

function handleCropTouchEnd(e) {
    e.preventDefault();
    const touchEndTime = Date.now();
    const touchDuration = touchEndTime - touchStartTime;
    
    console.log('Touch end - duration:', touchDuration, 'ms');
    
    // Reset touch states
    isTouchDragging = false;
    isTouchResizing = false;
    resizeHandle = null;
    lastTouchDistance = 0;
    
    // If it was a very quick touch (tap), don't interfere with other interactions
    if (touchDuration < 200 && e.touches.length === 0) {
        console.log('Quick tap detected');
    }
}

function updateCropPosition() {
    const imageX = Math.round((cropFrame.x / cropCanvas.width) * cropImage.width);
    const imageY = Math.round((cropFrame.y / cropCanvas.height) * cropImage.height);
    document.getElementById('cropPosition').textContent = `Position: (${imageX}, ${imageY})`;
}

function drawCropCanvas() {
    if (!cropCanvas || !cropImage || !cropCtx) {
        console.error('Missing crop canvas, image, or context');
        return;
    }
    
    // Clear canvas
    cropCtx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
    
    // Calculate proper image scaling to fit canvas while maintaining aspect ratio
    const canvasAspect = cropCanvas.width / cropCanvas.height;
    const imageAspect = cropImage.width / cropImage.height;
    
    let displayWidth, displayHeight, offsetX, offsetY;
    
    if (imageAspect > canvasAspect) {
        // Image is wider - fit to canvas width
        displayWidth = cropCanvas.width;
        displayHeight = cropCanvas.width / imageAspect;
        offsetX = 0;
        offsetY = (cropCanvas.height - displayHeight) / 2;
    } else {
        // Image is taller - fit to canvas height
        displayHeight = cropCanvas.height;
        displayWidth = cropCanvas.height * imageAspect;
        offsetX = (cropCanvas.width - displayWidth) / 2;
        offsetY = 0;
    }
    
    // Apply zoom
    const zoomedWidth = displayWidth * cropZoom;
    const zoomedHeight = displayHeight * cropZoom;
    const zoomedOffsetX = (cropCanvas.width - zoomedWidth) / 2 + cropOffset.x;
    const zoomedOffsetY = (cropCanvas.height - zoomedHeight) / 2 + cropOffset.y;
    
    console.log('Drawing image:', {
        original: { width: cropImage.width, height: cropImage.height },
        canvas: { width: cropCanvas.width, height: cropCanvas.height },
        display: { width: displayWidth, height: displayHeight },
        zoomed: { width: zoomedWidth, height: zoomedHeight, x: zoomedOffsetX, y: zoomedOffsetY }
    });
    
    // Draw the full image
    cropCtx.drawImage(cropImage, zoomedOffsetX, zoomedOffsetY, zoomedWidth, zoomedHeight);
    
    // Draw semi-transparent overlay over entire canvas
    cropCtx.fillStyle = 'rgba(0, 0, 0, 0.4)';
    cropCtx.fillRect(0, 0, cropCanvas.width, cropCanvas.height);
    
    // Clear the crop frame area (make it fully visible)
    cropCtx.globalCompositeOperation = 'destination-out';
    cropCtx.fillRect(cropFrame.x, cropFrame.y, cropFrame.width, cropFrame.height);
    
    // Reset composite operation and redraw image in crop area only
    cropCtx.globalCompositeOperation = 'source-over';
    cropCtx.save();
    cropCtx.beginPath();
    cropCtx.rect(cropFrame.x, cropFrame.y, cropFrame.width, cropFrame.height);
    cropCtx.clip();
    cropCtx.drawImage(cropImage, zoomedOffsetX, zoomedOffsetY, zoomedWidth, zoomedHeight);
    cropCtx.restore();
    
    // Draw crop frame border
    cropCtx.strokeStyle = '#3b82f6';
    cropCtx.lineWidth = 2;
    cropCtx.strokeRect(cropFrame.x, cropFrame.y, cropFrame.width, cropFrame.height);
    
    // Draw dashed inner border
    cropCtx.strokeStyle = '#1d4ed8';
    cropCtx.lineWidth = 1;
    cropCtx.setLineDash([5, 5]);
    cropCtx.strokeRect(cropFrame.x + 1, cropFrame.y + 1, cropFrame.width - 2, cropFrame.height - 2);
    cropCtx.setLineDash([]);
    
    // Draw corner handles for resizing
    drawResizeHandles();
    
    updateCropPosition();
}

function drawResizeHandles() {
    // Use larger handles for touch devices
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const handleSize = isTouchDevice ? 15 : 10;
    
    cropCtx.fillStyle = '#3b82f6';
    cropCtx.strokeStyle = '#ffffff';
    cropCtx.lineWidth = 2;
    
    // Corner handles
    const handles = [
        { x: cropFrame.x - handleSize/2, y: cropFrame.y - handleSize/2, cursor: 'nw-resize', type: 'nw' },
        { x: cropFrame.x + cropFrame.width - handleSize/2, y: cropFrame.y - handleSize/2, cursor: 'ne-resize', type: 'ne' },
        { x: cropFrame.x - handleSize/2, y: cropFrame.y + cropFrame.height - handleSize/2, cursor: 'sw-resize', type: 'sw' },
        { x: cropFrame.x + cropFrame.width - handleSize/2, y: cropFrame.y + cropFrame.height - handleSize/2, cursor: 'se-resize', type: 'se' }
    ];
    
    handles.forEach(handle => {
        cropCtx.fillRect(handle.x, handle.y, handleSize, handleSize);
        cropCtx.strokeRect(handle.x, handle.y, handleSize, handleSize);
    });
}

function getCropData() {
    if (!cropCanvas || !cropImage || !cropFrame) return null;
    
    // For both HEIC and non-HEIC files, cropImage now contains the actual image to process
    // No need for special dimension handling since HEIC is already converted to same size
    const actualImageWidth = cropImage.width;
    const actualImageHeight = cropImage.height;
    
    console.log('Using image dimensions for crop data:', actualImageWidth, 'x', actualImageHeight);
    
    // Calculate the actual display scale of the image on canvas
    const canvasAspect = cropCanvas.width / cropCanvas.height;
    const imageAspect = cropImage.width / cropImage.height;
    
    let displayWidth, displayHeight, offsetX, offsetY;
    
    if (imageAspect > canvasAspect) {
        // Image is wider - fit to canvas width
        displayWidth = cropCanvas.width;
        displayHeight = cropCanvas.width / imageAspect;
        offsetX = 0;
        offsetY = (cropCanvas.height - displayHeight) / 2;
    } else {
        // Image is taller - fit to canvas height
        displayHeight = cropCanvas.height;
        displayWidth = cropCanvas.height * imageAspect;
        offsetX = (cropCanvas.width - displayWidth) / 2;
        offsetY = 0;
    }
    
    // Apply zoom
    displayWidth *= cropZoom;
    displayHeight *= cropZoom;
    offsetX = (cropCanvas.width - displayWidth) / 2 + cropOffset.x;
    offsetY = (cropCanvas.height - displayHeight) / 2 + cropOffset.y;
    
    // Convert crop frame coordinates to actual image coordinates
    const scaleX = actualImageWidth / displayWidth;
    const scaleY = actualImageHeight / displayHeight;
    
    const imageX = Math.max(0, Math.round((cropFrame.x - offsetX) * scaleX));
    const imageY = Math.max(0, Math.round((cropFrame.y - offsetY) * scaleY));
    const imageWidth = Math.min(actualImageWidth - imageX, Math.round(cropFrame.width * scaleX));
    const imageHeight = Math.min(actualImageHeight - imageY, Math.round(cropFrame.height * scaleY));
    
    // Get target dimensions from form inputs
    const targetWidth = parseFloat(document.getElementById('cropWidth').value) || 0;
    const targetHeight = parseFloat(document.getElementById('cropHeight').value) || 0;
    const unit = document.getElementById('cropUnit').value;
    
    console.log('Crop data conversion:', {
        canvas: { width: cropCanvas.width, height: cropCanvas.height },
        image: { width: actualImageWidth, height: actualImageHeight },
        display: { width: displayWidth, height: displayHeight, offsetX, offsetY },
        frame: cropFrame,
        result: { x: imageX, y: imageY, width: imageWidth, height: imageHeight },
        target: { width: targetWidth, height: targetHeight, unit: unit }
    });
    
    return {
        x: imageX,
        y: imageY,
        width: imageWidth,
        height: imageHeight,
        originalWidth: actualImageWidth,
        originalHeight: actualImageHeight,
        targetWidth: targetWidth,
        targetHeight: targetHeight,
        targetUnit: unit
    };
}

function populateColorOptions() {
    const colorContainer = document.getElementById('colorOptions');
    
    colorOptions.forEach(option => {
        const colorDiv = document.createElement('div');
        colorDiv.className = 'color-option flex items-center p-3 rounded-lg border-2 border-gray-200 cursor-pointer hover:border-blue-300 transition-colors';
        colorDiv.dataset.color = option.value;
        
        colorDiv.innerHTML = `
            <input type="radio" name="bgColor" value="${option.value}" id="${option.id}" class="hidden">
            <div class="flex items-center space-x-2">
                ${option.preview ? 
                    `<div class="w-6 h-6 rounded-full border-2 border-gray-300" style="background-color: ${option.preview}"></div>` :
                    `<div class="w-6 h-6 rounded-full border-2 border-gray-300 bg-gradient-to-r from-red-500 via-yellow-500 to-blue-500"></div>`
                }
                <span class="text-sm font-medium text-gray-700">${option.label}</span>
            </div>
        `;
        
        colorDiv.addEventListener('click', () => selectColor(option.value, colorDiv));
        colorContainer.appendChild(colorDiv);
    });

    // Handle custom color picker
    const customColorPicker = document.getElementById('customColorPicker');
    customColorPicker.addEventListener('change', () => {
        if (document.querySelector('input[name="bgColor"]:checked')?.value === 'custom') {
            // Update custom color selection
        }
    });
}

function selectColor(colorValue, element) {
    // Remove selection from all color options
    document.querySelectorAll('.color-option').forEach(option => {
        option.classList.remove('border-blue-500', 'bg-blue-50');
    });

    // Add selection to clicked option
    element.classList.add('border-blue-500', 'bg-blue-50');
    
    // Set radio button
    const radio = element.querySelector('input[type="radio"]');
    radio.checked = true;

    // Show/hide custom color picker
    const customColorSection = document.getElementById('customColorSection');
    if (colorValue === 'custom') {
        customColorSection.classList.remove('hidden');
    } else {
        customColorSection.classList.add('hidden');
    }
}

async function fetchPassportSpecs() {
    try {
        const response = await fetch('/passport-specs');
        passportSpecs = await response.json();
    } catch (error) {
        console.error('Error fetching passport specs:', error);
    }
}

function populatePassportOptions() {
    const passportContainer = document.getElementById('passportOptions');
    passportContainer.innerHTML = '';

    Object.entries(passportSpecs).forEach(([key, spec]) => {
        const optionDiv = document.createElement('div');
        optionDiv.className = 'passport-option flex items-center p-3 rounded-lg border-2 border-gray-200 cursor-pointer hover:border-blue-300 transition-colors';
        optionDiv.dataset.passport = key;
        
        optionDiv.innerHTML = `
            <input type="radio" name="passportType" value="${key}" id="passport_${key}" class="hidden">
            <div class="flex items-center space-x-3">
                <div class="w-4 h-4 border-2 border-gray-400 rounded-full flex-shrink-0"></div>
                <div>
                    <div class="font-medium text-gray-800">${spec.name}</div>
                    <div class="text-sm text-gray-600">${spec.width_px} × ${spec.height_px} pixels</div>
                </div>
            </div>
        `;
        
        // Set click handler that can be removed/restored
        optionDiv.onclick = () => selectPassportType(key, optionDiv);
        passportContainer.appendChild(optionDiv);
    });

    // Select US by default if manual cropping is not enabled
    if (!isManualCroppingEnabled) {
        const usOption = passportContainer.querySelector('[data-passport="US"]');
        if (usOption) {
            selectPassportType('US', usOption);
        }
    }
}

function selectPassportType(passportType, element) {
    // Remove selection from all passport options
    document.querySelectorAll('.passport-option').forEach(option => {
        option.classList.remove('border-blue-500', 'bg-blue-50');
        // Reset radio button visual indicator
        const radioIndicator = option.querySelector('.w-4.h-4');
        if (radioIndicator) {
            radioIndicator.classList.remove('bg-blue-500', 'border-blue-500');
            radioIndicator.classList.add('border-gray-400');
        }
    });

    // Add selection to clicked option
    element.classList.add('border-blue-500', 'bg-blue-50');
    
    // Update radio button visual indicator
    const radioIndicator = element.querySelector('.w-4.h-4');
    if (radioIndicator) {
        radioIndicator.classList.remove('border-gray-400');
        radioIndicator.classList.add('bg-blue-500', 'border-blue-500');
    }
    
    // Set radio button
    const radio = element.querySelector('input[type="radio"]');
    radio.checked = true;
}

function clearPassportSelection() {
    // Clear all passport selections
    document.querySelectorAll('.passport-option').forEach(option => {
        option.classList.remove('border-blue-500', 'bg-blue-50');
        // Reset radio button visual indicator
        const radioIndicator = option.querySelector('.w-4.h-4');
        if (radioIndicator) {
            radioIndicator.classList.remove('bg-blue-500', 'border-blue-500');
            radioIndicator.classList.add('border-gray-400');
        }
        // Uncheck radio button
        const radio = option.querySelector('input[type="radio"]');
        if (radio) {
            radio.checked = false;
        }
    });
}

function disablePassportOptions(disabled) {
    const passportContainer = document.getElementById('passportOptions');
    
    document.querySelectorAll('.passport-option').forEach(option => {
        if (disabled) {
            option.classList.add('opacity-50', 'cursor-not-allowed');
            option.classList.remove('cursor-pointer', 'hover:border-blue-300');
            // Remove click event listener
            option.onclick = null;
        } else {
            option.classList.remove('opacity-50', 'cursor-not-allowed');
            option.classList.add('cursor-pointer', 'hover:border-blue-300');
            // Restore click event listener
            const passportType = option.dataset.passport;
            option.onclick = () => selectPassportType(passportType, option);
        }
    });
    
    // Add/remove disabled message
    let disabledMessage = passportContainer.querySelector('.manual-crop-disabled-message');
    
    if (disabled && !disabledMessage) {
        disabledMessage = document.createElement('div');
        disabledMessage.className = 'manual-crop-disabled-message text-sm text-gray-500 italic text-center py-2 px-3 bg-gray-50 rounded-lg mb-3';
        disabledMessage.textContent = 'Manual cropping enabled - passport sizes disabled';
        passportContainer.insertBefore(disabledMessage, passportContainer.firstChild);
    } else if (!disabled && disabledMessage) {
        disabledMessage.remove();
    }
}

function restoreDefaultPassportSelection() {
    // Select US by default when re-enabling passport options
    const usOption = document.querySelector('.passport-option[data-passport="US"]');
    if (usOption) {
        selectPassportType('US', usOption);
    }
}

async function processImage() {
    if (!selectedFile || !selectedProcessingType) {
        showAlert('Please select a file and processing type', 'error');
        return;
    }

    // Show progress
    step3.classList.add('hidden');
    progressContainer.classList.remove('hidden');
    
    // Check if file is HEIC
    const isHEIC = selectedFile.type === 'image/heic' || 
                   selectedFile.type === 'image/heif' || 
                   selectedFile.name.toLowerCase().endsWith('.heic') || 
                   selectedFile.name.toLowerCase().endsWith('.heif');
    
    try {
        // For HEIC files, ensure conversion is done before processing
        if (isHEIC && !heicConvertedCache) {
            updateProgressText('Converting HEIC to JPG...');
            // Convert HEIC first
            const formData = new FormData();
            formData.append('file', selectedFile);

            const convertResponse = await fetch('/convert-img?output_format=jpeg&keep_original_size=true', {
                method: 'POST',
                body: formData
            });

            if (convertResponse.ok) {
                const convertResult = await convertResponse.json();
                if (convertResult.success) {
                    heicConvertedCache = {
                        dataUrl: `data:image/jpeg;base64,${convertResult.image}`,
                        width: convertResult.width,
                        height: convertResult.height,
                        originalWidth: convertResult.original_width,
                        originalHeight: convertResult.original_height
                    };
                    console.log('HEIC converted for processing:', heicConvertedCache.width, 'x', heicConvertedCache.height);
                } else {
                    throw new Error('HEIC conversion failed');
                }
            } else {
                throw new Error(`HEIC conversion request failed: ${convertResponse.status}`);
            }
        }
        
        updateProgressText('Preparing image data...');
        
        // Prepare form data
        const formData = new FormData();
    
    // For HEIC files, use the converted JPG version if available
    if (isHEIC && heicConvertedCache) {
        console.log('Using converted HEIC-to-JPG for processing');
        // Convert base64 to blob for form data
        const base64Data = heicConvertedCache.dataUrl.split(',')[1];
        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const convertedBlob = new Blob([byteArray], { type: 'image/jpeg' });
        
        // Create a new file from the converted blob
        const convertedFile = new File([convertedBlob], selectedFile.name.replace(/\.(heic|heif)$/i, '.jpg'), {
            type: 'image/jpeg'
        });
        
        formData.append('file', convertedFile);
    } else {
        // Use original file for non-HEIC files or if conversion not available
        formData.append('file', selectedFile);
    }
    
    formData.append('processing_type', selectedProcessingType);

    // Add background color if needed
    if (selectedProcessingType === 'refill_bg' || selectedProcessingType === 'passport_photo') {
        const selectedColor = document.querySelector('input[name="bgColor"]:checked');
        if (selectedColor) {
            let colorValue = selectedColor.value;
            if (colorValue === 'custom') {
                colorValue = document.getElementById('customColorPicker').value;
            }
            formData.append('background_color', colorValue);
        }
    }

    // Add target dimensions for crop_face or passport_photo
    if (selectedProcessingType === 'crop_face' || selectedProcessingType === 'passport_photo') {
        let targetWidth, targetHeight, targetUnit;
        
        if (isManualCroppingEnabled && cropFrame) {
            // Manual cropping: use user-defined dimensions
            targetWidth = parseFloat(document.getElementById('cropWidth').value) || 0;
            targetHeight = parseFloat(document.getElementById('cropHeight').value) || 0;
            targetUnit = document.getElementById('cropUnit').value;
            
            // Add manual cropping data
            const cropData = getCropData();
            formData.append('manual_crop', JSON.stringify(cropData));
        } else {
            // Automatic cropping: get dimensions from selected passport type
            const selectedPassport = document.querySelector('input[name="passportType"]:checked');
            if (selectedPassport && passportSpecs[selectedPassport.value]) {
                const spec = passportSpecs[selectedPassport.value];
                // Use pixel dimensions directly for simplicity
                targetWidth = spec.width_px;
                targetHeight = spec.height_px;
                targetUnit = 'px';
                
                // Add passport type to form data
                formData.append('passport_type', selectedPassport.value);
            }
        }
        
        // Always send target dimensions
        if (targetWidth > 0 && targetHeight > 0) {
            formData.append('target_width', targetWidth.toString());
            formData.append('target_height', targetHeight.toString());
            formData.append('target_unit', targetUnit);
        }
    }

    updateProgressText('Processing image...');
    
    const response = await fetch('/process', {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
    }

    const result = await response.json();
    
    updateProgressText('Rendering results...');
    
    // Display results
    displayResults(result);
        
    } catch (error) {
        console.error('Error processing image:', error);
        showAlert('Error processing image. Please try again.', 'error');
        goToStep3();
    } finally {
        progressContainer.classList.add('hidden');
    }
}

function displayResults(result) {
    // Show original image - handle HEIC files specially
    const isHEIC = selectedFile.type === 'image/heic' || 
                   selectedFile.type === 'image/heif' || 
                   selectedFile.name.toLowerCase().endsWith('.heic') || 
                   selectedFile.name.toLowerCase().endsWith('.heif');
    
    if (isHEIC && heicConvertedCache) {
        // For HEIC files, use the converted image for display
        console.log('Using HEIC converted image for original image display');
        document.getElementById('originalImage').src = heicConvertedCache.dataUrl;
    } else {
        // For other formats, use standard file reader
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById('originalImage').src = e.target.result;
        };
        reader.readAsDataURL(selectedFile);
    }
    
    // Show original file info with type
    let originalInfo = `Original: ${result.original_size} pixels`;
    if (selectedFile.type) {
        const fileType = selectedFile.type.replace('image/', '').toUpperCase();
        originalInfo += ` • ${fileType}`;
    }
    document.getElementById('originalSize').textContent = originalInfo;
    
    // Add converted file info if HEIC was converted (as sibling element)
    const originalSizeElement = document.getElementById('originalSize');
    // Remove any existing converted info
    const existingConverted = originalSizeElement.parentNode.querySelector('.converted-info');
    if (existingConverted) {
        existingConverted.remove();
    }
    
    if (isHEIC && heicConvertedCache) {
        const convertedInfo = document.createElement('div');
        convertedInfo.className = 'text-xs text-gray-600 text-center mt-1 converted-info';
        convertedInfo.textContent = `Converted: HEIC → JPEG for processing`;
        originalSizeElement.parentNode.insertBefore(convertedInfo, originalSizeElement.nextSibling);
    }

    // Show processed image
    const format = selectedProcessingType === 'remove_bg' ? 'png' : 'jpeg';
    document.getElementById('resultImage').src = `data:image/${format};base64,${result.image}`;
    
    // Enhanced result info with target dimensions/size
    let resultInfo = `Result: ${result.width} × ${result.height} pixels`;
    
    // Add target dimensions inline - use backend response for verification
    if (result.target_dimensions) {
        const target = result.target_dimensions;
        resultInfo += ` (${target.width} × ${target.height} ${target.unit})`;
    } else if (result.physical_size_inches) {
        // Fallback to physical dimensions if no target dimensions
        resultInfo += ` (${result.physical_size_inches} inches)`;
    }
    
    resultInfo += ` • ${format.toUpperCase()}`;
    
    document.getElementById('resultSize').textContent = resultInfo;
    
    // Show face detection status
    const faceDetectionElement = document.getElementById('faceDetection');
    if (result.face_detected) {
        faceDetectionElement.innerHTML = '<span class="text-green-600">✓ Face detected</span>';
    } else {
        faceDetectionElement.innerHTML = '<span class="text-yellow-600">⚠ No face detected (center crop used)</span>';
    }

    // Store result for download
    downloadBtn.dataset.image = result.image;
    downloadBtn.dataset.format = format;

    // Handle photo sheet download if available (only for passport photos)
    if (result.sheet && selectedProcessingType === 'passport_photo') {
        downloadSheetBtn.classList.remove('hidden');
        downloadSheetBtn.dataset.sheetImage = result.sheet.image;
        downloadSheetBtn.dataset.sheetFormat = 'jpeg';
        
        // Update sheet info text
        document.getElementById('sheetInfo').textContent = `${result.sheet.count} photos, ${result.sheet.layout}`;
    } else {
        downloadSheetBtn.classList.add('hidden');
    }

    // Show result container
    resultContainer.classList.remove('hidden');
    
    showAlert('Image processed successfully!', 'success');
}

function downloadImage() {
    const imageData = downloadBtn.dataset.image;
    const format = downloadBtn.dataset.format;
    
    if (!imageData) {
        showAlert('No image to download', 'error');
        return;
    }

    // Create download link
    const link = document.createElement('a');
    link.href = `data:image/${format};base64,${imageData}`;
    
    // Generate filename
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `id-photo-single-${selectedProcessingType}-${timestamp}.${format}`;
    link.download = filename;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert('Single photo downloaded successfully!', 'success');
}

function downloadSheet() {
    const sheetImageData = downloadSheetBtn.dataset.sheetImage;
    const format = downloadSheetBtn.dataset.sheetFormat;
    
    if (!sheetImageData) {
        showAlert('No photo sheet to download', 'error');
        return;
    }

    // Create download link
    const link = document.createElement('a');
    link.href = `data:image/${format};base64,${sheetImageData}`;
    
    // Generate filename
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `id-photo-sheet-${selectedProcessingType}-${timestamp}.${format}`;
    link.download = filename;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert('Photo sheet downloaded successfully!', 'success');
}

function updateStepIndicators() {
    const indicators = document.querySelectorAll('.step-indicator');
    
    indicators.forEach((indicator, index) => {
        const stepNumber = index + 1;
        indicator.classList.remove('active', 'completed');
        
        if (stepNumber === currentStep) {
            indicator.classList.add('active');
        } else if (stepNumber < currentStep) {
            indicator.classList.add('completed');
        }
    });
}

function updateProgressText(text) {
    document.getElementById('progressText').textContent = text;
}

function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer');
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert mb-4 p-4 rounded-lg shadow-lg transition-all duration-300 transform translate-x-full`;
    
    const bgColor = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500';
    alertDiv.className += ` ${bgColor} text-white`;
    
    alertDiv.innerHTML = `
        <div class="flex items-center justify-between">
            <span>${message}</span>
            <button class="ml-4 text-white hover:text-gray-200" onclick="this.parentElement.parentElement.remove()">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
            </button>
        </div>
    `;
    
    alertContainer.appendChild(alertDiv);
    
    // Animate in
    setTimeout(() => {
        alertDiv.classList.remove('translate-x-full');
    }, 100);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentElement) {
            alertDiv.classList.add('translate-x-full');
            setTimeout(() => {
                if (alertDiv.parentElement) {
                    alertDiv.remove();
                }
            }, 300);
        }
    }, 5000);
}
