#!/usr/bin/python3
# vim: expandtab shiftwidth=2 tabstop=2
import os
import sys
import unicodedata
import time

is_python_2 = sys.version_info.major == 2
is_python_3 = sys.version_info.major == 3
list_item_count = 0
blank_string = ""
quiet = False
really_quiet = False
music_extensions = [".mp3", ".ogg", ".mp2", ".wav", ".wma"]

try:
    # noinspection PyUnresolvedReferences
    import win_unicode_console
    win_unicode_console.enable()
except:
    pass  # just trying to make console not suck for windows

have_pathlib = False
try:
    from pathlib import Path
    have_pathlib = True
except:
    pass

try:
    import mutagen

    if (mutagen.version[0] < 1) or (mutagen.version[1] < 20):
        raise Exception("Mutagen minimum version requirement not met")
    from mutagen.oggvorbis import OggVorbis
    from mutagen.easyid3 import EasyID3
    from mutagen.mp3 import MP3
except Exception as ex:
    print(ex)
    print("fappy requires the mutagen library (at least version 1.20) to work. You can get it here:")
    print("http://code.google.com/p/mutagen")
    print("or, via subversion, with a command like:")
    print("svn co http://mutagen.googlecode.com/svn/trunk mutagen")
    print("or, if you're using a debian-based OS, do something like:")
    print("sudo apt-get install python-mutagen")
    print("This script is known to work with versions 1.4-1.6 and may")
    print("work with others as well")
    sys.exit(1)


def write2(fp, s):
    fp.write(s)


def write3(fp, s):
    fp.write(s.encode("utf-8", "ignore"))


if is_python_2:
    # write = lambda fp, str: fp.write(str)
    write = write2
elif is_python_3:
    # write = lambda fp, str: fp.write(str.encode('utf-8', 'ignore'))
    write = write3
else:
    raise Exception('Don\'t know how to write to files in Python v%i' % sys.version_info.major)


def convert_text(text, action="replace"):
    """
    Convert a string with embedded unicode characters to have XML entities instead
    - text, the text to convert
    - action, what to do with the unicode
    If it works return a string with the characters as XML entities
    If it fails return raise the exception
    """
    try:
        temp = text.encode("utf-8")
        fixed = unicodedata.normalize('NFKD', temp).encode('ASCII', action)
        print("convertText: fixed: %s" % fixed)
        return fixed
    except Exception:
        ret = ""
        for c in text:
            o = ord(c)
            if 31 < o < 123:
                ret += c
        return ret


def log(s):
    global really_quiet
    if really_quiet:
        return
    try:
        print(s)
    except Exception as e:
        print('print error: ', e)


def ls_recursive(folder):
    all_items = ls_recursive_all(folder)
    files = []
    for f in all_items:
        if os.path.isfile(f):
            files.append(f)
    status("")
    log("%i files" % (len(files)))
    files.sort()
    return files


def ls_recursive_all(folder):
    global list_item_count
    contents = os.listdir(folder)
    list_item_count += len(contents)
    status("%i items found..." % list_item_count)
    contents_copy = contents[:]
    contents = []
    for f in contents_copy:
        full_path = os.path.join(folder, f)
        if os.path.isfile(full_path):
            contents.append(full_path)
    for d in contents_copy:
        sub_path = os.path.join(folder, d)
        if os.path.isdir(sub_path):
            if d == '.' or d == '..':
                continue
            dir_contents = ls_recursive_all(sub_path)
            for sub in dir_contents:
                contents.append(sub)
    return contents


def usage():
    log("Usage: " + os.path.basename(sys.argv[0]) + " {options} -o [playlist file] [dir] {dir}...")
    log(" options:")
    log("  -a appends to the playlist file if it exists")
    log("  -m produces m3u output (default: you can leave this out)")
    log("  -x produces xspf output")
    sys.exit(0)


def write_m3u_playlist(m3u, f, append):
    try:
        if append:
            fp = open(f, "ab")
        else:
            fp = open(f, "wb")
    except Exception as e:
        if append:
            op = "append"
        else:
            op = "writing"
        log("Can't open %s for %s: %s" % (f, op, str(e)))
        return False

    try:
        write(fp, '#EXTM3U\n')
        for line in m3u:
            write(fp, line + '\n')
    except Exception as e:
        log("Can't write to %s: %s" % (f, str(e)))
        return False

    return True


def read_str(fp, offset, direction=2):
    fp.seek(offset, direction)
    buffer = fp.read()
    fp.seek(offset, direction)
    if is_python_3:
        return buffer.decode("utf-8")
    if is_python_2:
        return str(buffer)
    raise Exception("Don't know how to do bytes->string in this version of python")


def write_xspf_playlist(playlist, playlist_file, append):
    """Writes out an xspf playlist from info provided"""
    if append and os.path.isfile(playlist_file):
        fp = open(playlist_file, "rb+")
        offset = -128
        found = False
        tmp = read_str(fp, offset, 2)
        pos = tmp.find("</trackList>")
        if pos > -1:
            offset += pos
            tmp = read_str(fp, offset, 2)
            found = True
        if not found:
            fp.close()
            log("Can't find closing trackList tag in %f; can't append. Aborting" % playlist_file)
            return False
    else:
        fp = open(playlist_file, "wb")
        write(fp, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        write(fp, "<playlist version=\"1\" xmlns=\"http://xspf.org/ns/0/\">\n")
        write(fp, "  <trackList>\n")

    for item in playlist:
        write(fp, item + '\n')
    # write xml footer
    write(fp, "  </trackList>\n</playlist>\n")
    fp.close()
    return True


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


def get_xspf_info(f):
    # trust headers first
    head = open(f, "rb").read(3).lower()
    if head == "id3":
        return xspf_get_mp3_tag_info(f)
    if head == "ogg":
        return xspf_get_ogg_tag_info(f)
    # now try file extensions
    ext = os.path.splitext(f)[1].lower()
    if ext == ".mp3":
        return xspf_get_mp3_tag_info(f)
    if ext == ".ogg":
        return xspf_get_ogg_tag_info(f)
    # give up
    return ""


def xspf_get_mp3_tag_info(f):
    info = get_mp3_tag_info(f)
    return info_to_xspf_item(info)


def xspf_get_ogg_tag_info(f):
    info = get_ogg_tag_info(f)
    return info_to_xspf_item(info)


def info_to_xspf_item(info):
    """Converts one track info item to one xspf track item
      I've skipped using a real dom here for speed reasons:
      I have very simple XML needs: I might as well DIY"""
    title = ""
    for k in ["artist", "year", "album", "tracknumber", "title"]:
        if k in info:
            if title != "":
                title += " - "
            try:
                title += info[k]
            except:
                title += convert_text(info[k])
    ret = [
        "    <track>",
        "      <location>%s</location>" % xml_safe(xspf_location(info["file"])),
        "      <title>%s</title>" % xml_safe(title),
        "      <duration>%s</duration>" % (int(float(info["length"])) * 1000), "    </track>"]
    return "\n".join(ret)


def xml_safe(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def xspf_location(path):
    if have_pathlib:
        return Path(path).as_uri()
    return xml_safe("file://%s" % (path.replace(" ", "%20")))


def get_mp3_tag_info(f):
    ret = {"file": f, "length": "0"}
    try:
        i = MP3(f)
        ret["length"] = str(int(i.info.length))
        translation = {"TPE1": "artist", "TDRC": "year", "TYER": "year", "TDAT": "year",
                       "TRCK": "tracknumber", "TIT2": "title", "TALB": "album"}
        for k in ["TPE1", "TDRC|TYER|TDAT", "TALB", "TRCK", "TIT2"]:
            for subk in k.split("|"):
                if subk in i:
                    try:
                        val = str(i[subk].text[0])
                    except:
                        val = str(convert_text(i[subk].text[0]))
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
                    ret[translation[subk]] = val
                    break
    except Exception as e:
        log("\r%s\rWARN: Unable to read MP3 info for:\n%s" % (blank_string, f))
        log(" -> %s" % str(e))
    return ret


def m3u_get_mp3_tag_info(f):
    info = get_mp3_tag_info(f)
    i = info_to_m3u(info)
    return i


def m3u_get_ogg_tag_info(f):
    info = get_ogg_tag_info(f)
    return info_to_m3u(info)


def get_ogg_tag_info(f):
    global blank_string
    ret = {"file": f, "length": "0"}
    try:
        i = OggVorbis(f)
        ret["length"] = str(i.info.length)
        for k in ["artist", "album", "year", "tracknumber", "title"]:
            if k in i:
                ret[k] = str(i[k])
    except Exception as e:
        log("\r%s\rWARN: Unable to read OGG info for\n%s" % (blank_string, f))
        log(str(e))
    return ret


def info_to_m3u(info):
    ret = ""
    for k in ["artist", "album", "year", "tracknumber", "title"]:
        if k in info:
            val = str(convert_text(info[k]))
            val = val.strip()
            # ignore empty tags
            if len(val) == 0:
                continue
            # zero pad track number
            if k == "tracknumber" and len(val) < 2:
                val = "0" + val
            # ignore zero year
            try:
                if k == "year" and int(val) == 0:
                    continue
            except:
                # ignore badly-formatted year
                pass
            if ret != "":
                ret += " - "
            ret += val

    # fall back on file name
    if ret == "":
        ret += os.path.splitext(os.path.basename(info["file"]))[0]
    ret = "#EXTINF:" + str(int(float(info["length"]))) + "," + ret
    # add the file path for the playlist entry
    ret += "\n%s" % info["file"]
    return ret


def status(s):
    s = str(s)
    global quiet
    if quiet:
        return
    global blank_string
    if len(s) >= len(blank_string):
        s = s[0:len(blank_string) - 3]
        s += "..."
    sys.stdout.write("\r" + blank_string + "\r" + s + "\r")
    sys.stdout.flush()


def get_hr_time(t):
    t = ("%d" % t)
    t = int(t)
    minutes = str(int(float(t / 60)))
    secs = str(int(float(t % 60)))
    if len(minutes) < 2:
        minutes = "0" + minutes
    if len(secs) < 2:
        secs = "0" + secs
    return minutes + ":" + secs


def main():
    global blank_string
    global quiet
    global really_quiet

    if len(sys.argv) == 0:
        usage()

    for i in range(76):
        blank_string += " "

    playlist_file = ""
    dirs = []
    last_arg = ""
    append = False
    quiet = False
    really_quiet = False
    playlist_type = 0
    for arg in sys.argv[1:]:
        if arg == "-x":
            # set playlist type to xspf
            playlist_type = 1
            last_arg = ""
            continue
        if arg == "-q":
            quiet = True
            last_arg = ""
            continue
        if arg == "-qq":
            quiet = True
            really_quiet = True
            last_arg = ""
            continue
        if arg == "-m":
            # set playlist type to m3u (default)
            playlist_type = 0
            continue
        if arg == "-a":
            append = True
            continue
        if arg == "-h" or arg == "--help":
            usage()
        if arg == "-o":
            last_arg = arg
            continue
        if last_arg == "-o":
            playlist_file = arg
            last_arg = ""
            continue
        if os.path.isdir(arg):
            dirs.append(arg)
        else:
            log("Unable to locate dir '" + arg + "'")
            sys.exit(0)

    if len(dirs) == 0:
        log("You must specify at least one dir")
        sys.exit(1)

    playlist = []
    start = time.time()
    if len(playlist_file) == 0:
        log("You must specify an output file with -o")
    for d in dirs:
        log("Listing contents of '" + d + "'...")
        files = ls_recursive(d)
        log("Generating playlist content (" + str(len(files)) + " files)...")

        file_count = len(files)
        idx = 0
        gen_start = time.time()
        for file_path in files:
            idx += 1
            if playlist_type == 0:
                info = get_m3u_info(file_path)
            else:
                info = get_xspf_info(file_path)
            percent_complete = int(float(idx * 100 / file_count))
            p = str(percent_complete)
            if percent_complete < 10:
                p = "0%s" % p
            etr = (file_count - idx) * ((time.time() - gen_start) / float(idx))

            status("[%s %%] [etr: %s] %s" % (p, get_hr_time(etr), os.path.basename(file_path)))
            if len(info):
                playlist.append(info)

    if len(playlist) > 0:
        if playlist_type == 0:
            write_m3u_playlist(playlist, playlist_file, append)
        else:
            write_xspf_playlist(playlist, playlist_file, append)
    else:
        log("No information found")

    runtime = int(time.time() - start)
    status("")
    log("Run time: " + get_hr_time(runtime))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n (Aborted)")
