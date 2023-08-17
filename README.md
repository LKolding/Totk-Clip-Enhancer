# Totk-Clip-Enhancer

Enhance your clips by having all menus cut out. Abilities, weapon switching, shield and bow switching, fusing and lastly throwing.

Please be advised of the following:
Moviepy library might (will) break if clip is too long and raise IndexError if you don't fix the buffersize error when using the .cutout method from AudioFileClip.

# Setup:

```pip3 install -r requirements.txt```

You must also have ffmpeg installed and accessable from the command line

# Usage:
Change paths in TCE.py ClipEnhancer class
```
from TCE import ClipEnhancer
ce = ClipEnhancer(framerate: float, framesize: tuple, filepath: str)
ce.run()
```