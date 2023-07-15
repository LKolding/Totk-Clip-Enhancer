import os
import cv2
import shutil
import subprocess
from time import perf_counter
from multiprocessing import Process

import moviepy.editor as mp
from alive_progress import alive_bar

from helper_functions import dhash
from VideoConverter import convert_to_mp4
import ROIs

DEBUG = True

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
        
        self._frameCounter = 0
        self._removedFrames = 0
        self._totalCuts = []        # Cuts to be made in audio based on deleted frames
        self._cutStartTime = 0
        self._cutEndTime = 0
        self._frameHashes = []
        
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
        if not os.path.exists(ClipEnhancer.VIDEO_FILE_LOCATION + filename + ext):
            shutil.copy(filepath, newfilepath)
        
        # Check if format is correct, otherwise convert
        if ext != ClipEnhancer.VIDEO_FILE_EXTENSION:
            convert_to_mp4(
                inputf = newfilepath, 
                outputf= ClipEnhancer.VIDEO_FILE_LOCATION + filename + ClipEnhancer.VIDEO_FILE_EXTENSION, debug=DEBUG)
        
        # Store name of file and (potentially) updated filepath
        self.filename = filename
        self.filepath = newfilepath

    def run(self):
        self._clearFolders(only=['Frames'])
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
    
    def _chunk(l, n):
        # loop over the list in n-sized chunks
        for i in range(0, len(l), n):
            # yield the current n-sized chunk to the calling function
            yield l[i: i + n]
    
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
    
    def _frameInMenu(self, frame) -> bool:
        '''tries to locate UI elements inside of frame passed in img arg'''
        # back button check
        max_loc = self._matchImage(frame, ClipEnhancer.BACKBUTTON_TEMPLATE_LOCATION, ROI=ROIs.ROI)
        
        if max_loc == ROIs.ROI.back_button_location1:
            return True
        
        if max_loc == ROIs.ROI.back_button_location2:
            return True
        
        # back button check when in abilities menu
        max_loc = self._matchImage(frame, templatepath = ClipEnhancer.BACKBUTTON_TEMPLATE_LOCATION, ROI=ROIs.AbilitiesROI)
           
        if max_loc == ROIs.AbilitiesROI.back_button_location:
            return True
        
        # If no menu was detected
        return False
    
    def _frameBlurry(self, frame) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fm = cv2.Laplacian(gray, cv2.CV_64F).var()
        if DEBUG: cv2.putText(frame, 'Blurryness = %s'%fm, (10, 30), cv2.FONT_HERSHEY_COMPLEX, 1, (255,0,0), 2)
        if fm < 10.5: return True
        return False
    
    def extractFrames(self):
        cap = cv2.VideoCapture(ClipEnhancer.VIDEO_FILE_LOCATION + self.filename + ClipEnhancer.VIDEO_FILE_EXTENSION)
        
        if (cap.isOpened() == False):
            print(f'Could not load file {ClipEnhancer.VIDEO_FILE_LOCATION + self.filename + ClipEnhancer.VIDEO_FILE_EXTENSION}')
            exit()
            
        # No of total frames in video
        totalFrames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        # Necessary for figuring out audio track cuts/trims
        lastFrameWasInMenu = False

        # Multiprocessing
        '''
        framesToBeProcessed = [x for x in range(totalFrames)]
        
        workers = 8
        chuck_size = totalFrames / workers
        slice = [framesToBeProcessed[i:i+chuck_size] for i in range(0, len(framesToBeProcessed), chuck_size)]
        jobs = []
        '''
        print('[*] Extracting frames...')
        print()
        with alive_bar(totalFrames) as bar:
            counter = 0
            # Read until video is completed
            while(cap.isOpened()):
                # Capture frame-by-frame
                ret, frame = cap.read()
                counter += 1
                
                if ret == True:
                    lastFrameWasInMenu = self._compute(frame, counter, lastFrameWasInMenu, bar=bar)
                    
                else:
                    break
                    
                
        print()
        print(f'[*] Marked frames: {self._removedFrames} ({round(self._removedFrames/totalFrames*100, 1)}%)')
        print()
        self._frameCounter = 0
        self._removedFrames = 0
        # When everything done, release the video capture object
        cap.release()
       
    def _compute(self, frame, counter: int, lastFrameWasInMenu: bool, bar= None) -> int:
        frameIsInMenu = self._frameInMenu(frame)
        if not frameIsInMenu: frameIsInMenu = self._frameBlurry(frame)
        
        # If frame doesn't contain menu
        if not frameIsInMenu:
            cv2.imwrite('frames/%05d' % self._frameCounter + ClipEnhancer.FRAME_FILE_EXTENSION, frame)
            self._frameCounter += 1
            if bar: bar()

        # If frame does contain menu
        else:
            self._removedFrames += 1
            if bar: bar()
        
        # The code below is all for figuring out when to cut the audio track
        
        # If frame does contain menu AND starts a sequence of "menuframes"
        if frameIsInMenu and not lastFrameWasInMenu:            
            # Convert frame file name (frame number) as time (seconds) and store it
            self._cutStartTime = counter / self._framerate
            return True
                
        # If frame does contain menu and is just a part of a longer sequence, skip
        if frameIsInMenu and lastFrameWasInMenu:
            return True
                
        # If frame DOESN'T contain menu and current frame ends a sequence
        if not frameIsInMenu and lastFrameWasInMenu:
            self._cutEndTime = counter / self._framerate
            self._totalCuts.append((self._cutStartTime, self._cutEndTime))
            self._cutEndTime, self._cutStartTime = (0,0)
            return False
        
        # If frame DOESN'T contain menu and last frame wasn't in menu: just keep going
        if not frameIsInMenu and not lastFrameWasInMenu:
            return False
        
        raise Exception('A certain frame could not be interpreted. Check all possible conditions in extractFrames()')
          
    def extractAudio(self):
        newAudioFileLocation = ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + ClipEnhancer.AUDIO_FILE_EXTENSION
        clip = mp.VideoFileClip( ClipEnhancer.VIDEO_FILE_LOCATION + self.filename + ClipEnhancer.VIDEO_FILE_EXTENSION )
        clip.audio.write_audiofile(newAudioFileLocation, logger=None)
    
    def cutAudio(self):
        with mp.AudioFileClip(ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + ClipEnhancer.AUDIO_FILE_EXTENSION, buffersize=400000) as clip:
            # Cut audiofile
            for cut in reversed(self._totalCuts):
                if DEBUG:
                    print(f'Cutting {cut[0]} to {cut[1]}')
                start, stop = cut
                clip = clip.cutout(start, stop)

            # Save audiofile
            clip.write_audiofile(ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + 'TRIMMED' + ClipEnhancer.AUDIO_FILE_EXTENSION, logger=None)
    
    def _clearFolders(self, only: list[str] = None):
        if only:
            for path in only:
                for file in os.listdir(path):
                    file_path = os.path.join(path, file)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print('[*] Failed to delete %s. Reason: %s' % (file_path, e))
                    
            return
        
        paths = [ClipEnhancer.AUDIO_FILE_LOCATION,
                 ClipEnhancer.FRAME_FILE_LOCATION,
                 ClipEnhancer.VIDEO_FILE_LOCATION]
        
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
    
    file = '/Users/lkolding/Movies/OBS/SilverLynel 7:10.mkv'
    ce = ClipEnhancer(60, (1920, 1080), file)
    ce._preserveFolders = ['Frames/']
    ce.run()
    
    stop = perf_counter()
    print("\n[*] Finished in %s\n" % str(stop-start))