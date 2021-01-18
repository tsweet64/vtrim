import pathlib
from subprocess import Popen,PIPE,STDOUT,DEVNULL
from multiprocessing import Pool, cpu_count
from shutil import rmtree
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument('inputName', help='The input video to process')
parser.add_argument('outName', help='The output filename')
parser.add_argument('--audio', '-a', action='store_true', help='Produce an audio-only output.')
parser.add_argument('--threshold', '-t', type=float, default=0.02, help='Volume threshold to detect as silence (between 0 and 1) (default 0.02)')
parser.add_argument('--gap', '-g', type=float, default=0.1, help='Number of seconds to wait before cutting silence (default 0.1)')
parser.add_argument('--ignore-temp', action='store_true', help='ignore temp dir (use this to restart an interrupted conversion')
parser.add_argument('--preset', '-p', type=str, default='ultrafast', help='ffmpeg encoding preset for libx264. Faster presets create larger output and temporary files.', choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow', 'placebo'])
parser.add_argument('--quiet', '-q', action='store_true', help='don\'t print ffmpeg output')
parser.add_argument('--keep', '-k', action='store_true', help='Keep the temporary files after running')
parser.add_argument('--reencode', action='store_true', help='Re-encode the final output. Saves space but may reduce quality')
args = parser.parse_args()

inputFile = pathlib.Path(args.inputName)
assert inputFile.is_file()
outputFile = pathlib.Path(args.outName)
assert not outputFile.is_file()
if not args.audio:
    tempListFile = pathlib.Path('segmentlist.txt')
    assert not tempListFile.is_file()

    #print(args.inputName + '\n' + str(args.threshold) + '\n' + str(args.gap))
    #Prepares the output path for the temporary directory.
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
        self.ffmpegSplitCmd = ['ffmpeg', '-nostdin', '-ss', self.ffmpeg_ss, '-i', str(inputFile), '-t', self.ffmpeg_t, '-v', 'warning', '-c:a', 'aac', '-c:v', 'libx264', '-preset', args.preset, str(self.outpath)]

    def start(self):
        with Popen(self.ffmpegSplitCmd, stdout=DEVNULL, stderr=DEVNULL) as process:
            process.communicate()
            return(" ".join(self.ffmpegSplitCmd))

#Construct ffmpeg command. Note: ffmpeg outputs everything as stderr
def measureSilence():
    print('Analyzing audio...')
    ffmpegDetectCmd = ['ffmpeg', '-nostdin', '-i', str(inputFile), '-filter_complex', '[0:a]silencedetect=n=' + str(args.threshold) + ':d=' + str(args.gap) + '[outa]', '-map', '[outa]', '-y', '-f', 'null', '-']
    with Popen(ffmpegDetectCmd, stdout=PIPE, stderr=STDOUT) as process:
            output = process.communicate()[0].decode('utf-8')
            print('Splitting video...')
            return output


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
    if not args.quiet:
        print(seg.start())
    else:
        seg.start()

def getListEntry(path):
    filename = str(path.resolve())
    #Verify file integrity
    with Popen(['ffprobe', filename], stdout=DEVNULL, stderr=DEVNULL) as process:
        process.communicate()
        if(process.returncode != 0):
            return ""
    return "file \'{}\'".format(filename)

#Get list of output files:
def writeSegmentList():
    print("Verifying segment integrity")
    segList = '\n'.join(map(getListEntry, sorted(outputDir.glob('*'))))
    tempListFile.write_text(segList)

def mergeSegments():
    print('Merging video')
    codec = 'copy'
    if args.reencode:
        codec='libx264'
    ffmpegMergeCmd = ['ffmpeg', '-nostdin', '-f', 'concat', '-safe', '0', '-i', str(tempListFile), '-c:v', codec, str(outputFile)]
    with Popen(ffmpegMergeCmd, stdout=PIPE, stderr=STDOUT) as process:
            return process.communicate()[0].decode('utf-8')

def removeTemp():
    print('Cleaning up')
    tempListFile.unlink()
    rmtree(outputDir)

def processAudioOnly():
    print('Processing audio only with ffmpeg silenceremove...')
    ffmpegAudioCommand = ['ffmpeg', '-nostdin', '-i', str(inputFile), '-vn', '-af', 'silenceremove=stop_threshold=' + str(args.threshold) + ':stop_duration=' + str(args.gap) + 'stop_periods=-1', str(outputFile)]
    with Popen(ffmpegAudioCommand, stdout=PIPE, stderr=STDOUT) as process:
        return process.communicate()[0].decode(utf-8)

#Handle video files
if args.audio:
    if not args.quiet:
        print(processAudioOnly())
    else:
        processAudioOnly()
else:
    #Generate segments
    with Pool(cpu_count()) as pool:
        pool.map_async(callFFmpeg, getVideoSegment()).get()
    writeSegmentList()
    if not args.quiet:
        print(mergeSegments())
    else:
        mergeSegments()
        print('Merging complete')
    if not args.keep:
        removeTemp()
