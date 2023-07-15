import ffmpeg
import subprocess

def convert_to_mp4(inputf: str, outputf: str, debug: bool = False):
    try: subprocess.call(["ffmpeg", "-i", f"{inputf}", "-codec", "copy", f"{outputf}"], stdout=subprocess.DEVNULL)
    except : print(f'Could not convert video {inputf} to {outputf}')
    else: return True

def _convert_to_mp4(inputf: str, outputf: str, debug: bool = False):
    try: ffmpeg.input(inputf).output(outputf).run(quiet=False if debug else True)
    except: print('Could not convert video {inputf} to {outputf}')
    else: return True