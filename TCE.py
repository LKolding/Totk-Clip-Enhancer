import os
import cv2
import shutil
import subprocess
from time import perf_counter
from numpy import ndarray

import moviepy.editor as mp
from alive_progress import alive_bar

from helper_functions import dhash
from VideoConverter import convert_to_mp4
import ROIs

DEBUG = False

class ClipEnhancer:
    VIDEO_FILE_LOCATION = 'Videos/'
    VIDEO_FILE_EXTENSION = '.mp4'
    VIDEO_FILE_LOCATION_FINISHED = 'Finished Videos/'
    
    FRAME_FILE_LOCATION = 'Frames/'
    FRAME_FILE_EXTENSION = '.jpg'
    
    AUDIO_FILE_LOCATION = 'Audio/'
    AUDIO_FILE_EXTENSION = '.mp3'
    
    BACKBUTTON_TEMPLATE_LOCATION = 'UI/back button_cropped.jpg'
    SORTBUTTON_TEMPLATE_LOCATION = 'UI/sort button.png'
    HOLDBUTTON_TEMPLATE_LOCATION = 'UI/hold button.png'
    
    def __init__(self, framerate: float, framesize: tuple, filepath: str = None):
        self._framerate = framerate
        self._framesize = framesize
        
        self.filename = ''          # Filename (without path and extension)
        
        self._showProgress = True
        self._preserveFolders = []  # list of folders to preserve
        
        self._frameCounter = 1
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
        self._clearFolders(only=['Frames', 'Audio'])
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
        output_path = ClipEnhancer.VIDEO_FILE_LOCATION_FINISHED + self.filename + ClipEnhancer.VIDEO_FILE_EXTENSION
    
        print(f'[*] Merging {frames_path} and {audio_path} into {output_path}')
    
        command = [
            'ffmpeg', 
            '-framerate', str(self._framerate), 
            '-i', frames_path, 
            '-i', audio_path, 
            '-c:a', 'copy',
            '-c:v', 'h264_videotoolbox',
            '-b:v', '16M',
            output_path
            ]
        subprocess.call(command, stdout=subprocess.DEVNULL)
    
    def _print_text_on_frame(self, frame, text: str, location=(10,10)):
        cv2.putText(frame, text, location, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 1)

    def _print_rect_on_frame(self, frame, max_loc, ROI, color=(0, 255, 0)):
        '''Prints two rectangles on frame: one around the ROI and one around the template'''
        # template dimensions
        w,h = ROI.img_size
        
        # ---------------------------------------
        # ----- Rectangle around entire ROI -----
        # ---------------------------------------
        
        # Top left x and y coordinates.
        x1, y1 = max_loc
        # Account for image being cropped
        x1 += ROI.x
        y1 += ROI.y
        # Bottom right x and y coordinates.
        x2, y2 = (x1 + w, y1 + h)
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # -------------------------------------
        # ----- Rectangle around template -----
        # -------------------------------------
        
        x1 = ROI.x
        y1 = ROI.y
        
        x2 = ROI.w + x1
        y2 = ROI.h + y1
    
        cv2.rectangle(frame, (x1, y1), (x2, y2),  color, 1)
    
    def _matchImage(self, img: ndarray, templatepath: str, ROI: object) -> tuple[int, int]:
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
    
    def _frameInMenu(self, frame: ndarray) -> bool:
        '''tries to locate UI elements (locations defined in ROIs.py) inside of frame passed in frame arg'''
        
        # Back button check in weapon switching menu.
        # Checks both both drop button is present and not
        max_loc = self._matchImage(frame, ClipEnhancer.BACKBUTTON_TEMPLATE_LOCATION, ROI=ROIs.ROI)
        
        if max_loc == ROIs.ROI.back_button_location1:
            return True
        
        if max_loc == ROIs.ROI.back_button_location2:
            return True
        
        # Back button check when in abilities menu
        max_loc = self._matchImage(frame, templatepath = ClipEnhancer.BACKBUTTON_TEMPLATE_LOCATION, ROI=ROIs.AbilitiesROI)
           
        if max_loc == ROIs.AbilitiesROI.back_button_location:
            return True
        
        # TODO
        # Sort button check in weapon switching menu
        max_loc = self._matchImage(frame, templatepath=ClipEnhancer.SORTBUTTON_TEMPLATE_LOCATION, ROI=ROIs.SortbuttonROI)
        self._print_rect_on_frame(frame, max_loc, ROIs.SortbuttonROI)
        
        if DEBUG:
            self._print_text_on_frame(frame, f'Srt_btn x: {round(max_loc[0], 5):7}', (10, 60))
            self._print_text_on_frame(frame, f'Srt_btn y: {round(max_loc[1], 5):7}', (10, 90))
        
        if max_loc == ROIs.SortbuttonROI.sort_button_location:
            return True
        
        # Hold button check when inventory is opened
        max_loc = self._matchImage(frame, templatepath=ClipEnhancer.HOLDBUTTON_TEMPLATE_LOCATION, ROI=ROIs.InventoryROI)
        self._print_rect_on_frame(frame, max_loc, ROIs.InventoryROI)
        
        if DEBUG:
            self._print_text_on_frame(frame, f'Hld_btn x: {round(max_loc[0], 5):7}', (10, 140))
            self._print_text_on_frame(frame, f'Hld_btn y: {round(max_loc[1], 5):7}', (10, 170))
        
        if max_loc == ROIs.InventoryROI.hold_button_location:
            return True
        
        # If no menu was detected
        return False
    
    def _frameBlurry(self, frame: ndarray) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fm = cv2.Laplacian(gray, cv2.CV_64F).var()
        if DEBUG: cv2.putText(frame, f'Blur: {round(fm, 5):7}', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 1, (255,180,0), 2)
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
       
    def _compute(self, frame: ndarray, counter: int, lastFrameWasInMenu: bool, bar= None) -> bool:
        frameIsInMenu = self._frameInMenu(frame)
        if not frameIsInMenu: frameIsInMenu = self._frameBlurry(frame)
        
        # If frame doesn't contain menu
        if not frameIsInMenu:
            cv2.imwrite(ClipEnhancer.FRAME_FILE_LOCATION + '%05d' % self._frameCounter + ClipEnhancer.FRAME_FILE_EXTENSION, frame)
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
        with mp.AudioFileClip(ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + ClipEnhancer.AUDIO_FILE_EXTENSION, buffersize=100_000) as clip:
            # Cut audiofile
            for cut in reversed(self._totalCuts):
                if DEBUG:
                    print(f'| Cutting {round(cut[0], 3):7} to {round(cut[1], 3):7} | Dur: {round(clip.duration, 3):7} |')
                start, stop = cut
                clip = clip.cutout(start, stop)

            # Save audiofile
            clip.write_audiofile(ClipEnhancer.AUDIO_FILE_LOCATION + self.filename + 'TRIMMED' + ClipEnhancer.AUDIO_FILE_EXTENSION, logger=None)

    def _clearFolders(self, only: list[str] = None) -> bool:
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
            # skip if path is in list of folders to be preserved
            if path in self._preserveFolders: continue 
            # otherwise wipe it
            for file in os.listdir(path):
                file_path = os.path.join(path, file)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print('[*] Failed to delete %s. Reason: %s' % (file_path, e))
                    return False
                    
        return True
    
if __name__=="__main__":
    start = perf_counter()
    
    if DEBUG:
        if not os.path.exists('Debug/'): os.mkdir('Debug/')
        ClipEnhancer.AUDIO_FILE_LOCATION = 'Debug/' + ClipEnhancer.AUDIO_FILE_LOCATION
        ClipEnhancer.FRAME_FILE_LOCATION = 'Debug/' + ClipEnhancer.FRAME_FILE_LOCATION
        ClipEnhancer.VIDEO_FILE_LOCATION = 'Debug/' + ClipEnhancer.VIDEO_FILE_LOCATION
    
    if not os.path.exists(ClipEnhancer.AUDIO_FILE_LOCATION): os.mkdir(ClipEnhancer.AUDIO_FILE_LOCATION)
    if not os.path.exists(ClipEnhancer.FRAME_FILE_LOCATION): os.mkdir(ClipEnhancer.FRAME_FILE_LOCATION)
    if not os.path.exists(ClipEnhancer.VIDEO_FILE_LOCATION): os.mkdir(ClipEnhancer.VIDEO_FILE_LOCATION)
    
    file = '/Users/lkolding/Movies/OBS/TotK 15-07-23 18-17.mkv'
    ce = ClipEnhancer(60, (1920, 1080), file)
    ce.run()
    
    stop = perf_counter()
    print("\n[*] Finished in %s (%s minutes)\n" % (round(stop-start, 2), round((stop-start)/60)))