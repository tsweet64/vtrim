import pathlib
from subprocess import Popen,PIPE,STDOUT
from multiprocessing import Pool, cpu_count
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument('inputName', help='The input video to process')
parser.add_argument('outName', help='The output filename')
parser.add_argument('--threshold', '-t', type=float, default=0.02, help='Threshold to detect as silence (between 0 and 1) (default 0.02)')
parser.add_argument('--gap', '-g', type=float, default=0.1, help='Number of seconds to wait before cutting silence (default 0.1)')
parser.add_argument('--ignore-temp', action='store_true', help='ignore temp dir')
args = parser.parse_args()

inputFile = pathlib.Path(args.inputName)
assert inputFile.is_file()
outputFile = pathlib.Path(args.outName)
assert not outputFile.is_file()
tempListFile = pathlib.Path('segmentlist.txt')
assert not tempListFile.is_file()

#print(args.inputName + '\n' + str(args.threshold) + '\n' + str(args.gap))
#Prepares the output path.
outputDir = pathlib.Path("vtemp")
if outputDir.is_dir():
    assert not any(outputDir.iterdir()) or args.ignore_temp, "The temporary directory already exists and is non-empty. Please clear it."
else:
    outputDir.mkdir()

#Object for each segment of video

class VidSegment:
    fileID = 0
    def __init__(self, silence_end, t):
        self.ffmpeg_ss = silence_end
        self.ffmpeg_t = t
        VidSegment.fileID += 1
        self.outpath=pathlib.PurePath.joinpath(outputDir, f"{VidSegment.fileID:05d}" + '.mkv')
        self.ffmpegSplitCmd = ['ffmpeg', '-nostdin', '-c:v', 'h264_cuvid', '-i', str(inputFile), '-ss', self.ffmpeg_ss, '-t', self.ffmpeg_t, '-v', 'warning', '-c:a', 'copy', '-c:v', 'libx264', '-preset', 'ultrafast', str(self.outpath)]

    def start(self):
        with Popen(self.ffmpegSplitCmd, stdout=PIPE, stderr=STDOUT) as process:
            process.communicate()
            return(" ".join(self.ffmpegSplitCmd))

#Construct ffmpeg command. Note: ffmpeg outputs everything as stderr
def measureSilence():
    ffmpegDetectCmd = ['ffmpeg', '-i', str(inputFile), '-filter_complex', '[0:a]silencedetect=n=' + str(args.threshold) + ':d=' + str(args.gap) + '[outa]', '-map', '[outa]', '-y', '-f', 'null', '-']
    with Popen(ffmpegDetectCmd, stdout=PIPE, stderr=STDOUT) as process:
            return process.communicate()[0].decode('ascii')


def getVideoSegment():
    silence_end = None
    silence_start = None
    matchEnd = re.compile(r'silence_end: \S+')
    matchStart = re.compile(r'silence_start: \S+')
    for line in iter(measureSilence().splitlines()):
        if not silence_end:
            silence_end = matchEnd.search(line)
        if silence_end:
            silence_start = matchStart.search(line)
            if silence_start:
                ffmpeg_ss = silence_end[0].split(' ')[1]
                ffmpeg_t = float(silence_start[0].split(' ')[1])-float(ffmpeg_ss)
                if ffmpeg_t >= 0.01:
                    yield VidSegment(ffmpeg_ss,f"{ffmpeg_t:.4f}")
                silence_end = None
                silence_start = None

def callFFmpeg(seg):
    print(seg.start())

def getListEntry(path):
    filename = str(path.resolve())
    #Verify file integrity
    with Popen(['ffprobe', filename], stdout=PIPE, stderr=STDOUT) as process:
        process.communicate()
        if(process.returncode != 0):
            return ""
    return "file \'{}\'".format(filename)

#Get list of output files:
def writeSegmentList():
    segList = '\n'.join(map(getListEntry, sorted(outputDir.glob('*'))))
    tempListFile.write_text(segList)

def mergeSegments():
    ffmpegMergeCmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', str(tempListFile), '-c', 'copy', str(outputFile)]
    with Popen(ffmpegMergeCmd, stdout=PIPE, stderr=STDOUT) as process:
            return process.communicate()[0].decode('ascii')

#Generate segments
with Pool(cpu_count()) as pool:
    pool.map_async(callFFmpeg, getVideoSegment()).get()
writeSegmentList()
print(mergeSegments())