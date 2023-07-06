import ffmpeg

def convert_to_mp4(inputf: str, outputf: str, debug: bool = False):
    try: ffmpeg.input(inputf).output(outputf).run(quiet=False if debug else True)
    except: print('Could not convert video {inputf} to {outputf}')
    else: return True