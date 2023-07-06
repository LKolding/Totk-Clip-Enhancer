import os
import cv2
import shutil
import subprocess
from time import perf_counter

import moviepy.editor as mp
from alive_progress import alive_bar

from VideoConverter import convert_to_mp4
import ROIs

DEBUG = False

class ClipEnhancer:
    VIDEO_FILE_LOCATION = "Videos/"
    VIDEO_FILE_EXTENSION = ".mp4"
    
    FRAME_FILE_LOCATION = 'Frames/'
    FRAME_FILE_EXTENSION = '.jpg'
    
    AUDIO_FILE_LOCATION = 'Audio/'
    AUDIO_FILE_EXTENSION = '.mp3'
    
    BACKBUTTON_TEMPLATE_LOCATION = 'UI/back button_cropped.jpg'
    
    def __init__(self, framerate: float, framesize: tuple, filepath: str = None):
        self._framerate = framerate
        self._framesize = framesize
        
        self.filename = ''          # Filename (without path and extension)
        
        self._showProgress = True
        self._preserveFolders = []  # list of folders to preserve
        
        self._totalCuts = []        # Cuts to be made in audio based on deleted frames
        self._frameCounter = 0
        
        if filepath:
            self.loadClip(filepath)
    
    def loadClip(self, filepath):
        '''Loads clip in filepath into instance attribute. 
        Moves provided video file (from filepath) into program folder.
        Checks for, and corrects, wrong format.'''
        oldfilepath, ext = os.path.splitext(filepath)
        path, filename = os.path.split(oldfilepath)
        
        # Might actually not be a 'new' path (just like oldfilepath might not be 'old')
        # but a check is done beneath regardless
        newfilepath = ClipEnhancer.VIDEO_FILE_LOCATION + filename + ext
        
        # Move file to correct folder (if not already)
        if os.path.split(path)[1] != ClipEnhancer.VIDEO_FILE_LOCATION:
            path = ClipEnhancer.VIDEO_FILE_LOCATION
            shutil.copy(filepath, newfilepath)
        
        # Check if format is correct, otherwise convert
        if ext != ClipEnhancer.VIDEO_FILE_EXTENSION:
            convert_to_mp4(
                inputf = newfilepath, 
                outputf= ClipEnhancer.VIDEO_FILE_LOCATION + filename + ClipEnhancer.VIDEO_FILE_EXTENSION)
        
        # Store name of file and (potentially) updated filepath
        self.filename = filename
        self.filepath = newfilepath

    def run(self):
        self._clearFolders()
        self.extractAudio()
        self.extractFrames()
        self.cutAudio()
        self.compile()
        if not self._clearFolders(): print('Could not properly clean up. Please check folders for unnecessary files.')

    def compile(self):
        """Generates a single video from images in Frames/ folder and audio from Audio/ folder.
        Will search for audio file with: Audio/self.filename + "TRIMMED" + AUDIO_FILE_EXTENSION
        """
        frames_path = os.path.join(ClipEnhancer.FRAME_FILE_LOCATION, "%05d.jpg")
        audio_path = ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + "TRIMMED" + ClipEnhancer.AUDIO_FILE_EXTENSION
        output_path = self.filename + ClipEnhancer.VIDEO_FILE_EXTENSION
    
        if DEBUG:
            print(f'Merging {frames_path} and {audio_path} into {output_path}')
    
        command = ['ffmpeg', '-framerate', str(self._framerate), '-i', frames_path, '-i', audio_path, '-c:a', 'copy', '-c:v', 'h264_videotoolbox', '-b:v', '16M', output_path] # libx264
        subprocess.call(command)
    
    def _matchImage(self, img, templatepath: str, ROI: object):
        template = cv2.imread(templatepath, 0)
        # Crop image such that only our ROI will be looked through
        x,y = ROI.x, ROI.y
        w,h = ROI.w, ROI.h
        cropped_img = img[y:y+h, x:x+w]
        
        # Convert cropped copy of image to Grayscale format
        img_gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
        
        # Compute
        result = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(result)
    
        return max_loc
    
    def _checkFrame(self, frame) -> tuple:
        '''tries to locate UI elements inside of frame passed in img arg'''
        # back button check
        max_loc = self._matchImage(frame, ClipEnhancer.BACKBUTTON_TEMPLATE_LOCATION, ROI=ROIs.ROI)
        
        if max_loc == ROIs.ROI.back_button_location1:
            return (frame, True)
        
        if max_loc == ROIs.ROI.back_button_location2:
            return (frame, True)
        
        # back button check when in abilities menu
        max_loc = self._matchImage(frame, templatepath = ClipEnhancer.BACKBUTTON_TEMPLATE_LOCATION, ROI=ROIs.AbilitiesROI)
           
        if max_loc == ROIs.AbilitiesROI.back_button_location:
            return (frame, True)
        
        # If no menu was detected
        return (frame, False)
    
    def extractFrames(self):
        cap = cv2.VideoCapture(ClipEnhancer.VIDEO_FILE_LOCATION + self.filename + ClipEnhancer.VIDEO_FILE_EXTENSION)
        
        if (cap.isOpened() == False):
            print(f'Could not load file {ClipEnhancer.VIDEO_FILE_LOCATION + self.filename + ClipEnhancer.VIDEO_FILE_EXTENSION}')
            exit()
            
        # Increases upon each frame iteration. Necessary for figuring out audio track cuts/trims
        counter = 0
        # Increases upen each written frame
        frame_counter = 1
        # Increases upon each removed frame
        totalRemovedFrames = 0
        # No of total frames in video
        totalFrames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        # Necessary for figuring out audio track cuts/trims
        lastFrameWasInMenu = False

        print('[*] Extracting frames...')
        print()
        with alive_bar(totalFrames) as bar:
            # Read until video is completed
            while(cap.isOpened()):
                # Capture frame-by-frame
                ret, frame = cap.read()
                counter += 1
                
                if ret == True:
                    # ENTIRE BOTTLENECK HALTING THE PROGRAM UPON EACH FRAME FOUND RIGHT HERE
                    result = self._checkFrame(frame)
                    
                    # If frame doesn't contain menu
                    if not result[1]:
                        cv2.imwrite('frames/%05d'%frame_counter + ClipEnhancer.FRAME_FILE_EXTENSION, result[0])
                        frame_counter += 1
                        bar()

                    # If frame does contain menu
                    else:
                        totalRemovedFrames += 1
                        bar()
                    
                    # If frame does contain menu AND starts a sequence of "menuframes"
                    if result[1] and not lastFrameWasInMenu:            
                        # Convert frame file name (frame number) as time (seconds) and store it
                        cut_start_time = counter / self._framerate
                        # Reset
                        lastFrameWasInMenu = True
                        continue
                            
                    # If frame does contain menu and is just a part of a longer sequence, skip
                    if result[1] and lastFrameWasInMenu:
                        lastFrameWasInMenu = True
                        continue
                            
                    # If frame DOESN'T contain menu and current frame ends a sequence
                    if not result[1] and lastFrameWasInMenu:
                        cut_end_time = counter / self._framerate
                        self._totalCuts.append((cut_start_time, cut_end_time))
                        cut_start_time, cut_end_time = (0,0)
                        # Reset
                        lastFrameWasInMenu = False
                        continue
                    
                    # If frame DOESN'T contain menu and last frame wasn't in menu: just keep going
                    if not result[1] and not lastFrameWasInMenu:
                        lastFrameWasInMenu = False
                        continue
                    
                    raise Exception('A certain frame could not be interpreted. Check all possible conditions in extractFrames()')
                    
                else:
                    break
                
        print()
        print(f'[*] Marked frames: {totalRemovedFrames} ({round(totalRemovedFrames/totalFrames*100, 1)}%)')
        print()
        # When everything done, release the video capture object
        cap.release()
        
    def extractAudio(self):
        newAudioFileLocation = ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + ClipEnhancer.AUDIO_FILE_EXTENSION
        clip = mp.VideoFileClip( ClipEnhancer.VIDEO_FILE_LOCATION + self.filename + ClipEnhancer.VIDEO_FILE_EXTENSION)
        clip.audio.write_audiofile(newAudioFileLocation, logger=None)
    
    def cutAudio(self):
        with mp.AudioFileClip(ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + ClipEnhancer.AUDIO_FILE_EXTENSION, buffersize=100000) as clip:
            # Cut audiofile
            for cut in reversed(self._totalCuts):
                if DEBUG:
                    print(f'Cutting {cut[0]} to {cut[1]}')
                start, stop = cut
                clip = clip.cutout(start, stop)

            # Save audiofile
            clip.write_audiofile(ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + 'TRIMMED' + ClipEnhancer.AUDIO_FILE_EXTENSION, logger=None)
    
    def _clearFolders(self):
        paths = ['Audio/', 'Frames/']
        for path in paths:
            if path in self._preserveFolders: continue
            
            for file in os.listdir(path):
                file_path = os.path.join(path, file)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print('[*] Failed to delete %s. Reason: %s' % (file_path, e))
                    
        return True
    
if __name__=="__main__":
    start = perf_counter()
    
    if not os.path.exists(ClipEnhancer.AUDIO_FILE_LOCATION): os.mkdir(ClipEnhancer.AUDIO_FILE_LOCATION)
    if not os.path.exists(ClipEnhancer.FRAME_FILE_LOCATION): os.mkdir(ClipEnhancer.FRAME_FILE_LOCATION)
    if not os.path.exists(ClipEnhancer.VIDEO_FILE_LOCATION): os.mkdir(ClipEnhancer.VIDEO_FILE_LOCATION)
    
    file = '/Users/lkolding/Local Documents/Coding & programming/Python/Totk Clip Enhancer/Videos/TotK 30-06-23 00-42.mkv'
    ce = ClipEnhancer(60, (1920, 1080), file)
    ce._preserveFolders = ['Videos/'] # deleting this will delete old, unenhanced files/clips - kinda annoying when debugging
    ce.run()
    
    stop = perf_counter()
    print("\n[*] Finished in %s\n" % start-stop)