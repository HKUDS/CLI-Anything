"""Filter management: apply, remove, configure filters on clips and tracks."""

from typing import Optional
from lxml import etree

from ..utils import mlt_xml
from .session import Session


# Registry of commonly used MLT filters with their parameters
FILTER_REGISTRY = {
    # Video filters
    "brightness": {
        "service": "brightness",
        "category": "video",
        "description": "Adjust brightness and contrast",
        "params": {
            "level": {"type": "float", "default": "1.0", "range": "0.0-2.0",
                      "description": "Brightness level (1.0 = normal)"},
        },
    },
    "volume": {
        "service": "volume",
        "category": "audio",
        "description": "Adjust audio volume",
        "params": {
            "level": {"type": "float", "default": "1.0", "range": "0.0-5.0",
                      "description": "Volume level (1.0 = normal)"},
            "gain": {"type": "float", "default": "0.0",
                     "description": "Gain in dB"},
        },
    },
    "blur": {
        "service": "frei0r.IIRblur",
        "category": "video",
        "description": "Gaussian blur effect",
        "params": {
            "amount": {"type": "float", "default": "0.2", "range": "0.0-1.0",
                       "description": "Blur amount"},
        },
    },
    "crop": {
        "service": "crop",
        "category": "video",
        "description": "Crop the video frame",
        "params": {
            "left": {"type": "int", "default": "0", "description": "Pixels from left"},
            "right": {"type": "int", "default": "0", "description": "Pixels from right"},
            "top": {"type": "int", "default": "0", "description": "Pixels from top"},
            "bottom": {"type": "int", "default": "0", "description": "Pixels from bottom"},
        },
    },
    "mirror": {
        "service": "mirror",
        "category": "video",
        "description": "Mirror the video horizontally or vertically",
        "params": {
            "mirror": {"type": "string", "default": "horizontal",
                       "description": "Mirror direction: horizontal, vertical, diagonal, xdiagonal, flip, flop"},
        },
    },
    "fadein-video": {
        "service": "brightness",
        "category": "video",
        "description": "Video fade in from black",
        "params": {
            "level": {"type": "string", "default": "00:00:00.000=0;00:00:01.000=1",
                      "description": "Keyframed brightness (timecode=value pairs)"},
            "alpha": {"type": "float", "default": "1",
                      "description": "Alpha value"},
        },
    },
    "fadeout-video": {
        "service": "brightness",
        "category": "video",
        "description": "Video fade out to black",
        "params": {
            "level": {"type": "string", "default": "00:00:00.000=1;00:00:01.000=0",
                      "description": "Keyframed brightness (timecode=value pairs)"},
        },
    },
    "fadein-audio": {
        "service": "volume",
        "category": "audio",
        "description": "Audio fade in",
        "params": {
            "level": {"type": "string", "default": "00:00:00.000=0;00:00:01.000=1",
                      "description": "Keyframed volume (timecode=value pairs)"},
        },
    },
    "fadeout-audio": {
        "service": "volume",
        "category": "audio",
        "description": "Audio fade out",
        "params": {
            "level": {"type": "string", "default": "00:00:00.000=1;00:00:01.000=0",
                      "description": "Keyframed volume (timecode=value pairs)"},
        },
    },
    "sepia": {
        "service": "sepia",
        "category": "video",
        "description": "Sepia tone effect",
        "params": {
            "u": {"type": "int", "default": "75", "description": "Chroma U value"},
            "v": {"type": "int", "default": "150", "description": "Chroma V value"},
        },
    },
    "charcoal": {
        "service": "charcoal",
        "category": "video",
        "description": "Charcoal drawing effect",
        "params": {
            "x_scatter": {"type": "int", "default": "1", "description": "Horizontal scatter"},
            "y_scatter": {"type": "int", "default": "1", "description": "Vertical scatter"},
        },
    },
    "saturation": {
        "service": "frei0r.saturat0r",
        "category": "video",
        "description": "Adjust color saturation",
        "params": {
            "saturation": {"type": "float", "default": "1.0", "range": "0.0-3.0",
                           "description": "Saturation (1.0 = normal, 0.0 = grayscale)"},
        },
    },
    "hue": {
        "service": "frei0r.hueshift0r",
        "category": "video",
        "description": "Shift hue of the image",
        "params": {
            "shift": {"type": "float", "default": "0.0", "range": "0.0-1.0",
                      "description": "Hue shift amount (0.0-1.0 = full circle)"},
        },
    },
    "glow": {
        "service": "frei0r.glow",
        "category": "video",
        "description": "Glow/bloom effect",
        "params": {
            "blur": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                     "description": "Glow blur amount"},
        },
    },
    "text": {
        "service": "dynamictext",
        "category": "video",
        "description": "Text overlay on video",
        "params": {
            "argument": {"type": "string", "default": "Text Here",
                         "description": "The text to display"},
            "geometry": {"type": "string", "default": "0%/0%:100%x100%:100",
                         "description": "Position geometry (x/y:wxh:opacity)"},
            "family": {"type": "string", "default": "Sans",
                       "description": "Font family"},
            "size": {"type": "int", "default": "48",
                     "description": "Font size"},
            "fgcolour": {"type": "string", "default": "#ffffffff",
                         "description": "Text color as #AARRGGBB"},
            "bgcolour": {"type": "string", "default": "#00000000",
                         "description": "Background color as #AARRGGBB"},
            "valign": {"type": "string", "default": "middle",
                       "description": "Vertical alignment: top, middle, bottom"},
            "halign": {"type": "string", "default": "center",
                       "description": "Horizontal alignment: left, center, right"},
        },
    },
    "affine": {
        "service": "affine",
        "category": "video",
        "description": "Position, scale, and rotate",
        "params": {
            "transition.geometry": {"type": "string", "default": "0/0:100%x100%:100",
                                    "description": "Geometry: x/y:wxh:opacity"},
            "transition.fix_rotate_x": {"type": "float", "default": "0",
                                        "description": "Rotation around X axis (degrees)"},
            "transition.fix_rotate_y": {"type": "float", "default": "0",
                                        "description": "Rotation around Y axis (degrees)"},
            "transition.fix_rotate_z": {"type": "float", "default": "0",
                                        "description": "Rotation around Z axis (degrees)"},
        },
    },
    "speed": {
        "service": "timewarp",
        "category": "video",
        "description": "Change playback speed",
        "params": {
            "speed": {"type": "float", "default": "1.0",
                      "description": "Playback speed (2.0 = double speed, 0.5 = half speed)"},
        },
    },
    # === Chroma Key / Keying ===
    "chroma-key": {
        "service": "frei0r.select0r",
        "category": "video",
        "description": "Chroma key (green/blue screen removal)",
        "params": {
            "color_to_select": {"type": "string", "default": "0.0 0.8 0.0",
                                "description": "Color to key out (R G B, 0.0-1.0)"},
            "delta_r__g___b_": {"type": "float", "default": "0.2", "range": "0.0-1.0",
                                "description": "Color tolerance"},
            "selection_subspace": {"type": "float", "default": "0.5",
                                   "description": "Subspace (0=HCI, 0.5=HSI)"},
        },
    },
    "chroma-key-advanced": {
        "service": "frei0r.keyspillm0pup",
        "category": "video",
        "description": "Advanced chroma key with spill suppression",
        "params": {
            "key_color": {"type": "string", "default": "0.0 0.8 0.0",
                          "description": "Key color (R G B, 0.0-1.0)"},
            "target_color": {"type": "string", "default": "0.5 0.5 0.5",
                             "description": "Target replacement color"},
            "mask_type": {"type": "int", "default": "0",
                          "description": "Mask type (0-3)"},
            "tolerance": {"type": "float", "default": "0.24", "range": "0.0-1.0",
                           "description": "Color tolerance"},
        },
    },
    "bluescreen": {
        "service": "frei0r.bluescreen0r",
        "category": "video",
        "description": "Blue/green screen removal (simpler than chroma-key)",
        "params": {
            "color": {"type": "string", "default": "0.0 0.85 0.0",
                      "description": "Screen color (R G B, 0.0-1.0)"},
            "distance": {"type": "float", "default": "0.288", "range": "0.0-1.0",
                          "description": "Color distance threshold"},
        },
    },
    # === Color Grading / Correction ===
    "color-grading": {
        "service": "frei0r.coloradj_RGB",
        "category": "video",
        "description": "RGB color adjustment (lift/gain per channel)",
        "params": {
            "r": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                  "description": "Red adjustment (0.5 = neutral)"},
            "g": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                  "description": "Green adjustment"},
            "b": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                  "description": "Blue adjustment"},
            "action": {"type": "int", "default": "0",
                       "description": "0=Shadows, 1=Midtones, 2=Highlights"},
            "keep_luma": {"type": "int", "default": "0",
                          "description": "Preserve luminance (0 or 1)"},
        },
    },
    "levels": {
        "service": "frei0r.levels",
        "category": "video",
        "description": "Levels adjustment (input/output black/white points)",
        "params": {
            "input_black_level": {"type": "float", "default": "0.0", "range": "0.0-1.0",
                                   "description": "Input black level"},
            "input_white_level": {"type": "float", "default": "1.0", "range": "0.0-1.0",
                                   "description": "Input white level"},
            "gamma": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                      "description": "Gamma (0.5 = 1.0 gamma)"},
            "channel": {"type": "int", "default": "0",
                        "description": "Channel: 0=All, 1=R, 2=G, 3=B"},
        },
    },
    "white-balance": {
        "service": "frei0r.balanc0r",
        "category": "video",
        "description": "White balance / color temperature adjustment",
        "params": {
            "neutral_color": {"type": "string", "default": "0.5 0.5 0.5",
                              "description": "Neutral color reference (R G B)"},
        },
    },
    "contrast": {
        "service": "frei0r.contrast0r",
        "category": "video",
        "description": "Adjust contrast",
        "params": {
            "contrast": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                          "description": "Contrast level (0.5 = normal)"},
        },
    },
    "gamma": {
        "service": "frei0r.gamma",
        "category": "video",
        "description": "Gamma correction",
        "params": {
            "gamma": {"type": "float", "default": "1.0", "range": "0.0-5.0",
                      "description": "Gamma value (1.0 = neutral)"},
        },
    },
    "color-temperature": {
        "service": "frei0r.colortap",
        "category": "video",
        "description": "Color temperature (warm/cool tint)",
        "params": {
            "table": {"type": "string", "default": "0",
                      "description": "Color preset table index"},
        },
    },
    "lut3d": {
        "service": "avfilter.lut3d",
        "category": "video",
        "description": "Apply 3D LUT color grading file (.cube, .3dl)",
        "params": {
            "av.file": {"type": "string", "default": "",
                        "description": "Path to .cube or .3dl LUT file"},
        },
    },
    "vibrance": {
        "service": "frei0r.colgate",
        "category": "video",
        "description": "Vibrance (intelligent saturation boost)",
        "params": {
            "neutral_color": {"type": "string", "default": "0.5 0.5 0.5",
                              "description": "Neutral reference color"},
            "color_temperature": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                                   "description": "Color temperature shift"},
        },
    },
    "invert": {
        "service": "frei0r.invert0r",
        "category": "video",
        "description": "Invert colors (negative)",
        "params": {},
    },
    "grayscale": {
        "service": "greyscale",
        "category": "video",
        "description": "Convert to grayscale",
        "params": {},
    },
    "threshold": {
        "service": "frei0r.threshold0r",
        "category": "video",
        "description": "Threshold (convert to black and white based on level)",
        "params": {
            "threshold": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                           "description": "Threshold level"},
        },
    },
    "posterize": {
        "service": "frei0r.posterize",
        "category": "video",
        "description": "Reduce color palette (posterization)",
        "params": {
            "levels": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                       "description": "Number of color levels (normalized)"},
        },
    },
    # === Distortion / FX ===
    "sharpen": {
        "service": "frei0r.sharpness",
        "category": "video",
        "description": "Sharpen the image",
        "params": {
            "amount": {"type": "float", "default": "0.3", "range": "0.0-1.0",
                       "description": "Sharpness amount"},
            "size": {"type": "float", "default": "0.0", "range": "0.0-1.0",
                     "description": "Sharpening kernel size"},
        },
    },
    "vignette": {
        "service": "frei0r.vignette",
        "category": "video",
        "description": "Vignette (darken edges)",
        "params": {
            "aspect": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                       "description": "Aspect ratio of vignette"},
            "clearcenter": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                            "description": "Size of clear center area"},
            "soft": {"type": "float", "default": "0.6", "range": "0.0-1.0",
                     "description": "Softness of vignette edge"},
        },
    },
    "grain": {
        "service": "frei0r.rgbnoise",
        "category": "video",
        "description": "Add film grain / noise",
        "params": {
            "noise": {"type": "float", "default": "0.2", "range": "0.0-1.0",
                      "description": "Noise amount"},
        },
    },
    "lens-correction": {
        "service": "frei0r.lenscorrection",
        "category": "video",
        "description": "Lens distortion correction (barrel/pincushion)",
        "params": {
            "xcenter": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                        "description": "Center X position"},
            "ycenter": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                        "description": "Center Y position"},
            "correctionnearcenter": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                                     "description": "Correction near center"},
            "correctionnearedges": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                                    "description": "Correction near edges"},
        },
    },
    "pixelize": {
        "service": "frei0r.pixeliz0r",
        "category": "video",
        "description": "Pixelation / mosaic effect",
        "params": {
            "blocksizex": {"type": "float", "default": "0.05", "range": "0.0-1.0",
                           "description": "Block size X (fraction of width)"},
            "blocksizey": {"type": "float", "default": "0.05", "range": "0.0-1.0",
                           "description": "Block size Y (fraction of height)"},
        },
    },
    "wave": {
        "service": "wave",
        "category": "video",
        "description": "Wave distortion effect",
        "params": {
            "start": {"type": "int", "default": "0", "description": "Start frame"},
            "speed": {"type": "float", "default": "5.0",
                      "description": "Wave speed"},
            "deformX": {"type": "int", "default": "1",
                        "description": "Deform in X (0 or 1)"},
            "deformY": {"type": "int", "default": "1",
                        "description": "Deform in Y (0 or 1)"},
            "amplitude": {"type": "int", "default": "25",
                          "description": "Wave amplitude in pixels"},
        },
    },
    "oldfilm": {
        "service": "oldfilm",
        "category": "video",
        "description": "Old film effect (scratches, dust, flickering)",
        "params": {
            "brightnessdelta_up": {"type": "int", "default": "20",
                                    "description": "Brightness variation up"},
            "brightnessdelta_down": {"type": "int", "default": "30",
                                      "description": "Brightness variation down"},
            "unevendevelop_duration": {"type": "int", "default": "70",
                                        "description": "Uneven development duration"},
        },
    },
    "vertigo": {
        "service": "frei0r.vertigo",
        "category": "video",
        "description": "Vertigo / dolly-zoom distortion effect",
        "params": {
            "phaseincrement": {"type": "float", "default": "0.02", "range": "0.0-1.0",
                               "description": "Phase increment"},
            "zoomrate": {"type": "float", "default": "0.2", "range": "0.0-1.0",
                         "description": "Zoom rate"},
        },
    },
    "elastic-scale": {
        "service": "frei0r.elastic_scale",
        "category": "video",
        "description": "Elastic scaling (non-linear stretch for aspect ratio fix)",
        "params": {
            "center": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                       "description": "Center of linear region"},
            "linearwidth": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                            "description": "Width of linear region"},
            "nonlinearscalefactor": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                                     "description": "Non-linear stretch factor"},
        },
    },
    # === Denoise ===
    "denoise": {
        "service": "frei0r.hqdn3d",
        "category": "video",
        "description": "High-quality 3D denoiser",
        "params": {
            "spatial": {"type": "float", "default": "0.04", "range": "0.0-1.0",
                        "description": "Spatial denoise strength"},
            "temporal": {"type": "float", "default": "0.06", "range": "0.0-1.0",
                         "description": "Temporal denoise strength"},
        },
    },
    # === Stabilization ===
    "stabilize": {
        "service": "vidstab",
        "category": "video",
        "description": "Video stabilization (reduce camera shake)",
        "params": {
            "shakiness": {"type": "int", "default": "5", "range": "1-10",
                          "description": "Shakiness detection (1=little, 10=very shaky)"},
            "accuracy": {"type": "int", "default": "15", "range": "1-15",
                         "description": "Detection accuracy"},
            "smoothing": {"type": "int", "default": "10",
                          "description": "Smoothing strength (frames)"},
            "zoom": {"type": "int", "default": "0",
                     "description": "Additional zoom (%)"},
        },
    },
    # === Text / Graphics ===
    "rich-text": {
        "service": "qtext",
        "category": "video",
        "description": "Rich text overlay with HTML support",
        "params": {
            "argument": {"type": "string", "default": "<h1>Title</h1>",
                         "description": "HTML text content"},
            "geometry": {"type": "string", "default": "0%/0%:100%x100%:100",
                         "description": "Position geometry (x/y:wxh:opacity)"},
            "family": {"type": "string", "default": "Sans",
                       "description": "Font family"},
            "fgcolour": {"type": "string", "default": "#ffffffff",
                         "description": "Foreground color (#AARRGGBB)"},
            "bgcolour": {"type": "string", "default": "#00000000",
                         "description": "Background color (#AARRGGBB)"},
        },
    },
    "timer": {
        "service": "timer",
        "category": "video",
        "description": "Timer/countdown overlay",
        "params": {
            "format": {"type": "string", "default": "%M:%S",
                       "description": "Time format string"},
            "duration": {"type": "string", "default": "00:00:10.000",
                         "description": "Timer duration"},
            "direction": {"type": "string", "default": "down",
                          "description": "Count direction: up or down"},
            "geometry": {"type": "string", "default": "0%/0%:100%x100%:100",
                         "description": "Position geometry"},
        },
    },
    # === Size / Position / Transform ===
    "size-position": {
        "service": "affine",
        "category": "video",
        "description": "Size, position, and rotation (picture-in-picture ready)",
        "params": {
            "transition.geometry": {"type": "string", "default": "0/0:100%x100%:100",
                                    "description": "Geometry: x/y:wxh:opacity"},
            "transition.fix_rotate_x": {"type": "float", "default": "0",
                                        "description": "X rotation (degrees)"},
            "transition.fix_rotate_y": {"type": "float", "default": "0",
                                        "description": "Y rotation (degrees)"},
            "transition.fix_rotate_z": {"type": "float", "default": "0",
                                        "description": "Z rotation (degrees)"},
            "background": {"type": "string", "default": "color:#00000000",
                           "description": "Background (color:#AARRGGBB or path)"},
        },
    },
    "rotate-scale": {
        "service": "affine",
        "category": "video",
        "description": "Rotate and scale (centered rotation)",
        "params": {
            "transition.fix_rotate_z": {"type": "float", "default": "0",
                                        "description": "Rotation angle (degrees)"},
            "transition.scale_x": {"type": "float", "default": "1.0",
                                   "description": "Scale X (1.0 = 100%)"},
            "transition.scale_y": {"type": "float", "default": "1.0",
                                   "description": "Scale Y (1.0 = 100%)"},
        },
    },
    "flip-horizontal": {
        "service": "avfilter.hflip",
        "category": "video",
        "description": "Flip video horizontally",
        "params": {},
    },
    "flip-vertical": {
        "service": "avfilter.vflip",
        "category": "video",
        "description": "Flip video vertically",
        "params": {},
    },
    # === Blend / Compositing ===
    "opacity": {
        "service": "brightness",
        "category": "video",
        "description": "Adjust clip opacity / transparency",
        "params": {
            "alpha": {"type": "float", "default": "1.0", "range": "0.0-1.0",
                      "description": "Opacity (0.0=transparent, 1.0=opaque)"},
            "level": {"type": "float", "default": "1.0",
                      "description": "Brightness level"},
        },
    },
    "mask-shape": {
        "service": "frei0r.alphaspot",
        "category": "video",
        "description": "Shape mask (rectangle, ellipse, triangle)",
        "params": {
            "position_x": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                           "description": "Center X position"},
            "position_y": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                           "description": "Center Y position"},
            "size_x": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                       "description": "Width"},
            "size_y": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                       "description": "Height"},
            "shape": {"type": "int", "default": "0",
                      "description": "Shape: 0=Rectangle, 1=Ellipse, 2=Triangle, 3=Diamond"},
            "operation": {"type": "int", "default": "0",
                          "description": "Operation: 0=Write on clear, 1=Max, 2=Min, 3=Add, 4=Subtract"},
        },
    },
    "mask-from-file": {
        "service": "frei0r.alphagrad",
        "category": "video",
        "description": "Gradient alpha mask",
        "params": {
            "position": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                         "description": "Position of gradient"},
            "tilt": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                     "description": "Tilt angle of gradient"},
            "min": {"type": "float", "default": "0.0", "range": "0.0-1.0",
                    "description": "Minimum alpha value"},
            "max": {"type": "float", "default": "1.0", "range": "0.0-1.0",
                    "description": "Maximum alpha value"},
        },
    },
    # === Audio Filters ===
    "equalizer": {
        "service": "ladspa.1901",
        "category": "audio",
        "description": "3-band audio equalizer",
        "params": {
            "0": {"type": "float", "default": "0", "range": "-70-30",
                  "description": "Low band gain (dB)"},
            "1": {"type": "float", "default": "0", "range": "-70-30",
                  "description": "Mid band gain (dB)"},
            "2": {"type": "float", "default": "0", "range": "-70-30",
                  "description": "High band gain (dB)"},
        },
    },
    "compressor": {
        "service": "ladspa.1913",
        "category": "audio",
        "description": "Dynamic range compressor",
        "params": {
            "0": {"type": "float", "default": "0",
                  "description": "Attack (ms)"},
            "1": {"type": "float", "default": "0.5",
                  "description": "Release (ms)"},
            "2": {"type": "float", "default": "0",
                  "description": "Threshold (dB)"},
            "3": {"type": "float", "default": "1",
                  "description": "Ratio"},
            "4": {"type": "float", "default": "0",
                  "description": "Knee radius (dB)"},
            "5": {"type": "float", "default": "0",
                  "description": "Makeup gain (dB)"},
        },
    },
    "reverb": {
        "service": "ladspa.1216",
        "category": "audio",
        "description": "Reverb effect (room simulation)",
        "params": {
            "0": {"type": "float", "default": "0.75",
                  "description": "Room size"},
            "1": {"type": "float", "default": "0.5",
                  "description": "Damping"},
            "2": {"type": "float", "default": "0.5",
                  "description": "Wet level"},
            "3": {"type": "float", "default": "1.0",
                  "description": "Dry level"},
            "4": {"type": "float", "default": "0.5",
                  "description": "Width"},
        },
    },
    "normalize-audio": {
        "service": "loudness",
        "category": "audio",
        "description": "Normalize audio loudness (EBU R128)",
        "params": {
            "target_loudness": {"type": "float", "default": "-23.0",
                                "description": "Target loudness in LUFS"},
        },
    },
    "lowpass": {
        "service": "ladspa.1052",
        "category": "audio",
        "description": "Low-pass audio filter",
        "params": {
            "0": {"type": "float", "default": "1000",
                  "description": "Cutoff frequency (Hz)"},
            "1": {"type": "float", "default": "1",
                  "description": "Stages (filter order)"},
        },
    },
    "highpass": {
        "service": "ladspa.1042",
        "category": "audio",
        "description": "High-pass audio filter",
        "params": {
            "0": {"type": "float", "default": "100",
                  "description": "Cutoff frequency (Hz)"},
            "1": {"type": "float", "default": "1",
                  "description": "Stages (filter order)"},
        },
    },
    "delay": {
        "service": "ladspa.1043",
        "category": "audio",
        "description": "Audio delay / echo effect",
        "params": {
            "0": {"type": "float", "default": "0.5",
                  "description": "Delay time (seconds)"},
            "1": {"type": "float", "default": "0.3",
                  "description": "Feedback"},
            "2": {"type": "float", "default": "0.5",
                  "description": "Wet/dry mix"},
        },
    },
    "mute": {
        "service": "volume",
        "category": "audio",
        "description": "Mute audio (set volume to zero)",
        "params": {
            "gain": {"type": "float", "default": "-100",
                     "description": "Gain in dB (-100 = silent)"},
        },
    },
    "balance": {
        "service": "panner",
        "category": "audio",
        "description": "Audio stereo balance / panning",
        "params": {
            "start": {"type": "float", "default": "0.5", "range": "0.0-1.0",
                      "description": "Pan position (0=left, 0.5=center, 1=right)"},
        },
    },
}


def list_available_filters(category: Optional[str] = None) -> list[dict]:
    """List all available filters from the registry.

    Args:
        category: Filter by category ("video", "audio", or None for all)
    """
    result = []
    for name, info in sorted(FILTER_REGISTRY.items()):
        if category and info["category"] != category:
            continue
        result.append({
            "name": name,
            "service": info["service"],
            "category": info["category"],
            "description": info["description"],
            "params": list(info["params"].keys()),
        })
    return result


def get_filter_info(filter_name: str) -> dict:
    """Get detailed info about a filter including its parameters."""
    if filter_name not in FILTER_REGISTRY:
        available = ", ".join(sorted(FILTER_REGISTRY.keys()))
        raise ValueError(f"Unknown filter: {filter_name!r}. Available: {available}")
    info = dict(FILTER_REGISTRY[filter_name])
    info["name"] = filter_name
    return info


def _resolve_target(session: Session, track_index: Optional[int] = None,
                    clip_index: Optional[int] = None) -> etree._Element:
    """Resolve the target element for a filter (clip producer or track playlist)."""
    if track_index is None:
        # Apply to the main tractor (global filter)
        return session.get_main_tractor()

    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    producer_id = tracks[track_index].get("producer")
    playlist = mlt_xml.find_element_by_id(session.root, producer_id)
    if playlist is None:
        raise RuntimeError(f"Track playlist not found")

    if clip_index is None:
        # Apply to the track
        return playlist

    # Apply to a specific clip's producer
    entries = mlt_xml.get_playlist_entries(playlist)
    clip_entries = [e for e in entries if e["type"] == "entry"]
    if clip_index < 0 or clip_index >= len(clip_entries):
        raise IndexError(f"Clip index {clip_index} out of range")

    clip_producer_id = clip_entries[clip_index]["producer"]
    producer = mlt_xml.find_element_by_id(session.root, clip_producer_id)
    if producer is None:
        raise RuntimeError(f"Producer {clip_producer_id!r} not found")
    return producer


def add_filter(session: Session, filter_name: str,
               track_index: Optional[int] = None,
               clip_index: Optional[int] = None,
               params: Optional[dict] = None) -> dict:
    """Add a filter to a clip, track, or the whole timeline.

    Args:
        session: Active session
        filter_name: Name from FILTER_REGISTRY, or raw MLT service name
        track_index: Track index (None = global)
        clip_index: Clip index on the track (None = whole track)
        params: Parameter overrides (name → value)
    """
    session.checkpoint()

    # Look up in registry, or use as raw service name
    if filter_name in FILTER_REGISTRY:
        reg = FILTER_REGISTRY[filter_name]
        service = reg["service"]
        # Start with defaults
        props = {}
        for pname, pinfo in reg["params"].items():
            props[pname] = pinfo["default"]
        # Apply overrides
        if params:
            props.update(params)
    else:
        # Assume it's a raw MLT service name
        service = filter_name
        props = params or {}

    target = _resolve_target(session, track_index, clip_index)
    filt = mlt_xml.add_filter_to_element(target, service, props)

    target_desc = "global"
    if track_index is not None and clip_index is not None:
        target_desc = f"track {track_index}, clip {clip_index}"
    elif track_index is not None:
        target_desc = f"track {track_index}"

    return {
        "action": "add_filter",
        "filter_name": filter_name,
        "service": service,
        "filter_id": filt.get("id"),
        "target": target_desc,
        "params": props,
    }


def remove_filter(session: Session, filter_index: int,
                  track_index: Optional[int] = None,
                  clip_index: Optional[int] = None) -> dict:
    """Remove a filter by index from a target element.

    Args:
        filter_index: Index of the filter among filters on the target
        track_index: Track (None = global/tractor filters)
        clip_index: Clip (None = track-level filters)
    """
    session.checkpoint()
    target = _resolve_target(session, track_index, clip_index)

    filters = target.findall("filter")
    if filter_index < 0 or filter_index >= len(filters):
        raise IndexError(f"Filter index {filter_index} out of range (0-{len(filters)-1})")

    filt = filters[filter_index]
    filter_id = filt.get("id")
    service = mlt_xml.get_property(filt, "mlt_service", "")
    target.remove(filt)

    return {
        "action": "remove_filter",
        "filter_index": filter_index,
        "filter_id": filter_id,
        "service": service,
    }


def set_filter_param(session: Session, filter_index: int,
                     param_name: str, param_value: str,
                     track_index: Optional[int] = None,
                     clip_index: Optional[int] = None) -> dict:
    """Set a parameter on a filter.

    Args:
        filter_index: Index of the filter on the target
        param_name: Property name to set
        param_value: New value
        track_index: Track (None = global)
        clip_index: Clip (None = track-level)
    """
    session.checkpoint()
    target = _resolve_target(session, track_index, clip_index)

    filters = target.findall("filter")
    if filter_index < 0 or filter_index >= len(filters):
        raise IndexError(f"Filter index {filter_index} out of range")

    filt = filters[filter_index]
    old_value = mlt_xml.get_property(filt, param_name)
    mlt_xml.set_property(filt, param_name, param_value)

    return {
        "action": "set_filter_param",
        "filter_index": filter_index,
        "param": param_name,
        "old_value": old_value,
        "new_value": param_value,
    }


def list_filters(session: Session,
                 track_index: Optional[int] = None,
                 clip_index: Optional[int] = None) -> list[dict]:
    """List all filters on a target element.

    Args:
        track_index: Track (None = global/tractor filters)
        clip_index: Clip (None = track-level filters)
    """
    target = _resolve_target(session, track_index, clip_index)
    filters = target.findall("filter")

    result = []
    for i, filt in enumerate(filters):
        service = mlt_xml.get_property(filt, "mlt_service", "")
        # Get all properties
        props = {}
        for prop in filt.findall("property"):
            name = prop.get("name", "")
            if name and name != "mlt_service":
                props[name] = prop.text or ""

        result.append({
            "index": i,
            "id": filt.get("id"),
            "service": service,
            "params": props,
        })

    return result
