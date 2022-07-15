# Vimeo downloader helper

I was given a Vimeo link by coworkers, but they forgot to allow download of the files, so while waiting for the settings to change I made a little script that allows full download of the streams. This tool was built with the little timeframe I had, and for my very own purposes and needs, it might not work for every video.

## What it does

* Scans the streams
* Finds the split stream URLs
* Gives it to you in a neatly formatted way

## What it doesn't

* Download anything for you

## Example

```
$ python vimeo.py <URL>

VIDEO_TITLE [BEST_VIDEO_QUALITY@FRAMERATE]
Video [CODECS, RESOLUTION@FRAMERATE]: VIDEO_URL
* Audio [CHANNELS]: AUDIO_URL
* Subtitles [SUB_NAME SUB_LANGUAGE]: SUBTITLES_URL
```