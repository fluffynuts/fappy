#!/usr/bin/python
# vim: expandtab shiftwidth=2 tabstop=2
import os
import sys
try:
	import psyco
except:
	pass
import time
from mutagen.oggvorbis import OggVorbis
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

music_extensions = [".mp3", ".ogg", ".mp2", ".wav", ".wma"]

def convertText(text, action = "replace"):
  """
  Convert a string with embedded unicode characters to have XML entities instead
  - text, the text to convert
  - action, what to do with the unicode
  If it works return a string with the characters as XML entities
  If it fails return raise the exception
  """
  try:
    temp = unicode(text, "utf-8")
    fixed = unicodedata.normalize('NFKD', temp).encode('ASCII', action)
    return fixed
  except Exception, errorInfo:
    ret = ""
    for c in text:
      if c > 31 and c < 123:
        ret += c
    return ret

def ls_R(dir):
  ls = [dir]
  os.path.walk(dir, walk_cb, ls)
  ls = ls[1:]
  sys.stdout.write("\r" + blankstr + "\r")
  sys.stdout.flush()
  ls.sort()
  return ls

def walk_cb(ls, dirname, fnames):
  global music_extensions
  d = dirname[len(ls[0]):]
  for f in fnames:
    fpath = os.path.join(dirname, f)
    if os.path.isfile(fpath):
      if music_extensions.count(os.path.splitext(f)[1].lower()) > 0:
        ls.append(os.path.join(d, f))
        items = len(ls) - 1
        if items % 100 == 0:
          sys.stdout.write("\r" + blankstr + "\r" + str(items))
          sys.stdout.flush()

def usage():
  print("Usage: " + os.path.basename(sys.argv[0]) + " -o [path to m3u file] [dir] {dir}...")
  sys.exit(0)

def write_playlist(m3u, f, append):
  if append:
    fp = open(f, "ab")
  else:
    fp = open(f, "wb")
  fp.write("#EXTM3U\n")
  for line in m3u:
    fp.write(line)
    fp.write("\n")

def get_m3u_info(f):
  # trust headers first
  head = open(f, "rb").read(3).lower()
  if head == "id3":
    return m3u_get_mp3_tag_info(f)
  if head == "ogg":
    return m3u_get_ogg_tag_info(f)
  # now try file extensions
  ext = os.path.splitext(f)[1].lower()
  if ext == ".mp3":
    return m3u_get_mp3_tag_info(f)
  if ext == ".ogg":
    return m3u_get_ogg_tag_info(f)
  # give up
  return ""

def m3u_get_mp3_tag_info(f):
  global blankstr
  try:
    i = MP3(f)
    ret = "#EXTINF:" + str(int(i.info.length)) + ","
    have_something = False
    for k in ["TPE1", "TDRC|TYER|TDAT", "TALB", "TRCK", "TIT2"]:
      val = ""
      for subk in k.split("|"):
        if i.has_key(subk):
          try:
            val = str(i[subk].text[0])
          except:
            val = str(convertText(i[subk].text[0]))
          val = val.strip()
          # ignore empty tags
          if len(val) == 0:
            continue
          # ignore zero year
          if subk == "TDRC" or subk == "TDAT":
            try:
              val = str(int(val.split("-")[0]))
            except:
              continue
          elif subk == "TYER":
            try:
              val = str(int(val))
            except:
              continue
          elif subk == "TRCK" and len(val) < 2:
            # zero pad track number
            val = "0" + val
          if have_something:
            ret += " - "
          ret += val
          have_something = True
          break
    # fall back on file name
    if not have_something:
      ret += os.path.splitext(os.path.basename(f))[0]
    return ret
  except Exception, e:
    print("\r" + blankstr + "\rUnable to get ID3 info for:")
    print(f)
    print(str(e))
    return ""

def m3u_get_ogg_tag_info(f):
  global blankstr
  try:
    i = OggVorbis(f)
    ret = "#EXTINF:" + str(int(i.info.length)) + ","
    have_something = False
    for k in ["artist", "album", "year", "tracknumber", "title"]:
      if i.has_key(k):
        val = str(convertText(i[k][0]))
        val = val.strip()
        # ignore empty tags
        if len(val) == 0:
          continue
        # zero pad track number
        if k == "tracknumber" and len(val) < 2:
          val = "0" + val
        # ignore zero year
        if k == "year" and int(val) == 0:
          continue
        if have_something:
          ret += " - "
        ret += val
        have_something = True

    # fall back on file name
    if not have_something:
      ret += os.path.splitext(os.path.basename(f))[0]
    return ret 
  except Exception, e:
    print("\r" + blankstr + "\rUnable to read OGG info for:")
    print(f)
    print(str(e))
    return ""

def status(s):
  global blankstr
  if (len(s) >= len(blankstr)):
    s = s[0:len(blankstr)-3]
    s += "..."
  sys.stdout.write("\r" + blankstr + "\r" + s + "\r")
  sys.stdout.flush()

def get_hr_time(t):
  t = int(t)
  min = str(t / 60)
  secs = str(t % 60)
  if len(min) < 2:
    min = "0" + min
  if len(secs) < 2:
    secs = "0" + secs
  return min + ":" + secs

if __name__ == "__main__":
  global blankstr
  blankstr = ""

  if len(sys.argv) == 0:
    usage()

  for i in range(76):
    blankstr += " "
  
  playlistfile = ""
  dirs = []
  lastarg = ""
  append = False
  for arg in sys.argv[1:]:
    if arg == "-a":
      append = True
      continue
    if arg == "-h" or arg == "--help":
      usage()
    if arg == "-o":
      lastarg = arg
      continue
    if lastarg == "-o":
      playlistfile = arg
      lastarg = ""
      continue
    if os.path.isdir(arg):
      dirs.append(arg)
    else:
      print("Unable to locate dir '" + arg + "'")
      sys.exit(0)

  if len(dirs) == 0:
    print("You must specify at least one dir")
    sys.exit(1)

  m3u = []
  start = time.time()
  if len(playlistfile) == 0:
    print("No output playlist file specified. Perhaps try reading the help (-h)")
    sys.exit(1)

  for d in dirs:
    print("Listing contents of '" + d + "'...")
    files = ls_R(d)
    print("Generating m3u content (" + str(len(files)) + " files)...")
    
    numfiles = len(files)
    idx = 0
    m3ustart = time.time()
    for f in files[1:]:
      idx += 1
      if f[0] != os.sep:
        fpath = d + os.sep + f
      else:
        fpath = d + f
      minfo = get_m3u_info(fpath)
      perc = idx * 100 / numfiles
      p = str(perc)
      if perc < 10:
        p + "0" + p
      etr = (numfiles - idx) * ((time.time() - m3ustart) / float(idx))
      status("[ " + p + " %] [etr: " + get_hr_time(etr) + "] " + os.path.basename(f))
      if len(minfo):
        m3u.append(minfo)
      m3u.append(fpath)

  if (len(m3u) > 0):
    write_playlist(m3u, playlistfile, append)
  else:
    print("No information found")

  runtime = int(time.time() - start);
  status("")
  print("Run time: " + get_hr_time(runtime))
  
    

