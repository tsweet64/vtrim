# vtrim
This is a python script that uses [`ffmpeg`](https://github.com/FFmpeg/FFmpeg) to automatically trim silent parts from videos. This can be used to watch lectures faster, for example. It can also handle audio-only files with the `-a` option.

## Dependencies
* A recent `python3`
* [`ffmpeg`](https://github.com/FFmpeg/FFmpeg)
* This script has only been tested on Arch and Manjaro Linux, however I expect it to work on any operating system that supports a recent `python3` and `ffmpeg`. Please report any errors with other operating systems.

## Usage
* `python vtrim.py inputvideo.mp4 outputvideo.mp4 [options]`
```
  -h, --help            show this help message and exit
  --audio, -a           Produce an audio-only output.
  --threshold THRESHOLD, -t THRESHOLD
                        Volume threshold to detect as silence (between 0 and 1) (default 0.02)
  --gap GAP, -g GAP     Number of seconds to wait before cutting silence (default 0.1)
  --ignore-temp         ignore temp dir (use this to restart an interrupted conversion
  --preset {ultrafast,superfast,veryfast,faster,fast,medium,slow,slower,veryslow,placebo}, -p {ultrafast,superfast,veryfast,faster,fast,medium,slow,slower,veryslow,placebo}
                        ffmpeg encoding preset for libx264. Faster presets create larger output and temporary files.
  --quiet, -q           don't print ffmpeg output
  --keep, -k            Keep the temporary files after running
  --reencode            Re-encode the final output. Saves space but may reduce quality
```

## Obtaining input files
If you want to run this script on a video found online, such as on youtube, you will need to download it. I recommend [yt-dlp](https://github.com/yt-dlp/yt-dlp), a FOSS command-line tool that can download videos and audio from hundreds of sites.

## Planned
* ~~Add support for audio-only files~~ v. 1.1
* Build url handling directly into the script via yt-dlp
