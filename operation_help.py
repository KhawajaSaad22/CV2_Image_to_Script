"""User-facing descriptions; processing and export do not depend on this module."""
HELP={
'resize':('Resize','Changes width and height. Explicit dimensions can change the aspect ratio. Area is a useful shrinking option; nearest keeps hard label boundaries.','cv2.resize'),
'crop':('Crop','Keeps a rectangular region and removes everything outside it. X/Y are the upper-left corner; width/height must fit the current image.','NumPy array slicing'),
'rotate':('Rotate','Turns the image around its center. Positive angles turn counterclockwise. Expand grows the frame to keep the image; keep retains the old frame and may cut corners. A 1920×1080 image at −90° becomes 1080×1920 in expand mode.','cv2.getRotationMatrix2D + cv2.warpAffine'),
'flip':('Flip','Mirrors the image horizontally, vertically, or both. It does not change the frame dimensions.','cv2.flip'),
'grayscale':('Grayscale','Removes color and produces a single brightness channel. Often used before edge detection and thresholding.','cv2.cvtColor (RGB → GRAY)'),
'brightness_contrast':('Brightness and contrast','Brightness adds/subtracts a value; contrast multiplies pixel intensity. Results are clipped to 0–255. Extreme settings can lose details.','NumPy float multiply/add + np.clip'),
'gamma':('Gamma correction','Adjusts midtone brightness nonlinearly. In this app gamma > 1 brightens and gamma < 1 darkens; 1 leaves the image unchanged.','cv2.LUT; output = 255 × (input / 255) ** (1 / gamma)'),
'gaussian_blur':('Gaussian blur','Smooths fine detail and noise using weighted neighboring pixels. Larger odd kernels blur more. Sigma controls the spread; zero lets OpenCV infer it.','cv2.GaussianBlur'),
'median_blur':('Median blur','Replaces each pixel with the neighborhood median. Useful for isolated bright/dark speckles, but large kernels remove small details.','cv2.medianBlur'),
'threshold':('Threshold','Produces a black/white image. Fixed uses your value; Otsu estimates one global threshold; adaptive calculates local thresholds using block size and C.','cv2.threshold / cv2.adaptiveThreshold'),
'canny':('Canny edge detection','Finds intensity boundaries as white edges on black. Low/high control weak and strong edge selection. The input is converted to grayscale.','cv2.Canny'),
'morphology':('Morphology','Uses a neighborhood kernel to alter small structures. Erode shrinks bright regions; dilate expands them; open removes small bright specks; close fills small dark gaps.','cv2.morphologyEx'),
'equalize':('Histogram equalization','Redistributes brightness to increase global contrast. On color images only Lab lightness is changed. It can exaggerate noise or change the overall appearance.','cv2.equalizeHist; RGB ↔ Lab for color'),
'clahe':('CLAHE — local contrast enhancement','Contrast Limited Adaptive Histogram Equalization improves contrast separately in small regions, useful when illumination is uneven. Clip limits how strongly contrast is amplified; tiles is the number of grid regions per axis, not a pixel size. Larger clip values can amplify noise. Color images keep their Lab color channels while lightness is adjusted.','cv2.createCLAHE(clipLimit=clip, tileGridSize=(tiles, tiles)).apply; RGB ↔ Lab for color')
}

PARAMETER_HELP={
'angle':'Degrees: positive is counterclockwise; negative is clockwise.',
'canvas':'Expand keeps the rotated image inside a resized frame. Keep retains the input frame and can clip edges.',
'border':'Fill newly exposed areas with black, white, or mirrored pixels. Paired annotations do not support reflected rotation.',
'clip':'CLAHE contrast limit. Higher values allow stronger enhancement and may amplify noise.',
'tiles':'CLAHE grid count along each axis (e.g. 8 means an 8×8 grid), not tile width in pixels.',
'kernel':'Odd neighborhood size in pixels. Larger values affect a wider region.',
'block':'Odd local neighborhood size for adaptive thresholding.',
'c':'Amount subtracted from the local adaptive-threshold estimate.',
'low':'Canny weak-edge threshold; must not exceed high.',
'high':'Canny strong-edge threshold; must be at least low.'
}
