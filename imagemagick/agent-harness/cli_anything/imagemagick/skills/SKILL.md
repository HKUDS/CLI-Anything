# ImageMagick Skill

## Overview
Image manipulation and conversion using ImageMagick. Supports format conversion, resizing, cropping, watermarks, montages, and batch processing.

## When to use
- Converting between image formats (PNG, JPEG, WebP, TIFF, etc.)
- Resizing, cropping, or transforming images
- Adding watermarks or borders
- Creating thumbnails or montages
- Batch processing multiple images
- Inspecting image metadata

## Capabilities
- **Format conversion**: Convert between any ImageMagick-supported formats
- **Transformations**: Resize, crop, rotate, flip, blur, sharpen
- **Adjustments**: Brightness, contrast, grayscale conversion
- **Composition**: Watermarks, borders, montages
- **Analysis**: Image info, RMSE comparison between images
- **Animation**: GIF metadata inspection
- **Batch**: Process multiple files with a single operation

## Requirements
- ImageMagick installed (`apt install imagemagick`)

## Example usage
```bash
cli-anything-imagemagick info photo.jpg
cli-anything-imagemagick convert photo.jpg photo.webp --quality 85 --width 1920
cli-anything-imagemagick thumbnail photo.jpg thumb.jpg --size 200
cli-anything-imagemagick watermark photo.jpg marked.jpg --text "Copyright 2026"
cli-anything-imagemagick montage *.jpg --output grid.png --tile 3x3
```
