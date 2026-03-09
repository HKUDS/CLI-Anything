# OBS Studio - Standard Operating Procedure

## Overview

OBS Studio (Open Broadcaster Software) is a free, open-source application for
live streaming and video recording. This CLI harness provides programmatic
control over OBS scene collections via JSON configuration files.

## Key Concepts

- **Scene Collection**: A project file containing all scenes, sources, and settings
- **Scene**: A composition of sources that can be switched between during streaming
- **Source**: A video/audio/image element placed within a scene
- **Filter**: An effect applied to a source (video or audio processing)
- **Transition**: Visual effect used when switching between scenes
- **Audio Source**: Global audio input/output with volume and monitoring controls

## CLI Harness Location

```
~/cli-anything/obs-studio/agent-harness/cli/
```

## Usage

### Creating a Stream Setup

```bash
cd ~/cli-anything/obs-studio/agent-harness

# 1. Create project
python3 -m cli.obs_cli project new --name "my_stream" -o stream.json

# 2. Add camera with chroma key
python3 -m cli.obs_cli --project stream.json source add video_capture --name "Webcam"
python3 -m cli.obs_cli --project stream.json filter add chroma_key -S 0 -p similarity=400

# 3. Add game capture
python3 -m cli.obs_cli --project stream.json source add display_capture --name "Game"

# 4. Add overlay
python3 -m cli.obs_cli --project stream.json source add image --name "Overlay" -S file=/path/to/overlay.png

# 5. Set up scenes
python3 -m cli.obs_cli --project stream.json scene add --name "BRB"
python3 -m cli.obs_cli --project stream.json scene add --name "Starting Soon"

# 6. Configure streaming output
python3 -m cli.obs_cli --project stream.json output streaming --service twitch --key "live_xxx"
python3 -m cli.obs_cli --project stream.json output settings --preset balanced

# 7. Configure recording
python3 -m cli.obs_cli --project stream.json output recording --format mp4 --quality high

# 8. Save
python3 -m cli.obs_cli --project stream.json project save
```

### Using the REPL

```bash
python3 -m cli.obs_cli repl --project stream.json
```

## JSON Scene Collection Format

```json
{
  "version": "1.0",
  "name": "my_stream",
  "settings": {
    "output_width": 1920,
    "output_height": 1080,
    "fps": 30,
    "video_bitrate": 6000,
    "audio_bitrate": 160,
    "encoder": "x264"
  },
  "scenes": [
    {
      "id": 0,
      "name": "Main Scene",
      "sources": [
        {
          "id": 0, "name": "Camera", "type": "video_capture",
          "visible": true, "locked": false,
          "position": {"x": 0, "y": 0},
          "size": {"width": 1920, "height": 1080},
          "crop": {"top": 0, "bottom": 0, "left": 0, "right": 0},
          "rotation": 0, "opacity": 1.0,
          "filters": [], "settings": {}
        }
      ]
    }
  ],
  "transitions": [
    {"name": "Cut", "type": "cut", "duration": 0},
    {"name": "Fade", "type": "fade", "duration": 300}
  ],
  "active_scene": 0,
  "audio_sources": [],
  "streaming": {"service": "twitch", "server": "auto", "key": ""},
  "recording": {"path": "./recordings/", "format": "mkv", "quality": "high"}
}
```

## Source Types

| Type | Description |
|------|-------------|
| video_capture | Webcam/capture card |
| display_capture | Full screen capture |
| window_capture | Single window capture |
| image | Static image file |
| media | Video/audio file |
| browser | Web page source |
| text | Text overlay |
| color | Solid color |
| audio_input | Microphone |
| audio_output | Desktop audio |
| group | Source group |
| scene | Nested scene |

## Filter Types

| Type | Category | Description |
|------|----------|-------------|
| color_correction | video | Adjust gamma, contrast, brightness, saturation |
| chroma_key | video | Green/blue screen removal |
| color_key | video | Key on specific color |
| lut | video | Apply color LUT file |
| image_mask | video | Alpha/blend mask |
| crop_pad | video | Crop edges |
| scroll | video | Scrolling effect |
| sharpen | video | Sharpen filter |
| noise_suppress | audio | Noise suppression (RNNoise/Speex) |
| gain | audio | Volume gain |
| compressor | audio | Dynamic range compression |
| noise_gate | audio | Noise gate |
| limiter | audio | Audio limiter |

## Testing

```bash
cd ~/cli-anything/obs-studio/agent-harness
python3 -m pytest cli/tests/ -v
```

All tests run without OBS Studio installed.
