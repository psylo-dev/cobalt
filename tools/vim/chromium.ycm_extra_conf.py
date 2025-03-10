# Copyright 2012 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Autocompletion config for YouCompleteMe in Chromium.
#
# USAGE:
#
#   1. Install YCM [https://github.com/Valloric/YouCompleteMe]
#          (Googlers should check out [go/ycm])
#
#   2. Create a symbolic link to this file called .ycm_extra_conf.py in the
#      directory above your Chromium checkout (i.e. next to your .gclient file).
#
#          cd src
#          ln -rs tools/vim/chromium.ycm_extra_conf.py ../.ycm_extra_conf.py
#
#   3. (optional) Whitelist the .ycm_extra_conf.py from step #2 by adding the
#      following to your .vimrc:
#
#          let g:ycm_extra_conf_globlist=['<path to .ycm_extra_conf.py>']
#
#      You can also add other .ycm_extra_conf.py files you want to use to this
#      list to prevent excessive prompting each time you visit a directory
#      covered by a config file.
#
#   4. Profit
#
#
# Usage notes:
#
#   * You must use ninja & clang to build Chromium.
#
#   * You must have built Chromium recently.
#
# For improved performance you can use a clang compile-commands.json database. To
# enable this you must use the --export-compile-commands when running gn gen, eg:
#
#   gn gen out_$BOARD/Release --export-compile-commands
#
#   Next you'll need to set an environment variable CHROMIUM_BUILD_DIR with the path
#   to your build. eg:
#
#   export CHROMIUM_BUILD_DIR=$HOME/chromium/src/out_$BOARD/Release
#
#   And then you can start vim.
#
# Hacking notes:
#
#   * The purpose of this script is to construct an accurate enough command line
#     for YCM to pass to clang so it can build and extract the symbols.
#
#   * Right now, we only pull the -I and -D flags. That seems to be sufficient
#     for everything I've used it for.
#
#   * That whole ninja & clang thing? We could support other configs if someone
#     were willing to write the correct commands and a parser.
#
#   * This has only been tested on Linux and macOS.

import os
import os.path
import re
import shlex
import subprocess
import sys
import ycm_core

# If the user has set the environment variable CHROMIUM_BUILD_DIR we will
# first attempt to find compilation flags in the compile-commands.json file in that
# directory first.
database = None
compilation_database_folder=os.getenv('CHROMIUM_BUILD_DIR')
if compilation_database_folder and os.path.exists(compilation_database_folder):
  database = ycm_core.CompilationDatabase(compilation_database_folder)

# Flags from YCM's default config.
_default_flags = [
    '-DUSE_CLANG_COMPLETER',
    '-std=c++14',
    '-x',
    'c++',
]

_header_alternates = ('.cc', '.cpp', '.c', '.mm', '.m')

_extension_flags = {
    '.m': ['-x', 'objective-c'],
    '.mm': ['-x', 'objective-c++'],
}


def PathExists(*args):
  return os.path.exists(os.path.join(*args))


def FindChromeSrcFromFilename(filename):
  """Searches for the root of the Chromium checkout.

  Simply checks parent directories until it finds .gclient and src/.

  Args:
    filename: (String) Path to source file being edited.

  Returns:
    (String) Path of 'src/', or None if unable to find.
  """
  curdir = os.path.normpath(os.path.dirname(filename))
  while not (
      os.path.basename(curdir) == 'src' and PathExists(curdir, 'DEPS') and
      (PathExists(curdir, '..', '.gclient') or PathExists(curdir, '.git'))):
    nextdir = os.path.normpath(os.path.join(curdir, '..'))
    if nextdir == curdir:
      return None
    curdir = nextdir
  return curdir


def GetDefaultSourceFile(chrome_root, filename):
  """Returns the default source file to use as an alternative to |filename|.

  Compile flags used to build the default source file is assumed to be a
  close-enough approximation for building |filename|.

  Args:
    chrome_root: (String) Absolute path to the root of Chromium checkout.
    filename: (String) Absolute path to the source file.

  Returns:
    (String) Absolute path to substitute source file.
  """
  blink_root = os.path.join(chrome_root, 'third_party', 'WebKit')
  if filename.startswith(blink_root):
    return os.path.join(blink_root, 'Source', 'core', 'CoreInitializer.cpp')
  else:
    if 'test.' in filename:
      return os.path.join(chrome_root, 'base', 'logging_unittest.cc')
    return os.path.join(chrome_root, 'base', 'logging.cc')


def GetNinjaBuildOutputsForSourceFile(out_dir, filename):
  """Returns a list of build outputs for filename.

  The list is generated by invoking 'ninja -t query' tool to retrieve a list of
  inputs and outputs of |filename|. This list is then filtered to only include
  .o and .obj outputs.

  Args:
    out_dir: (String) Absolute path to ninja build output directory.
    filename: (String) Absolute path to source file.

  Returns:
    (List of Strings) List of target names. Will return [] if |filename| doesn't
        yield any .o or .obj outputs.
  """
  # Ninja needs the path to the source file relative to the output build
  # directory.
  rel_filename = os.path.relpath(filename, out_dir)

  p = subprocess.Popen(
      ['ninja', '-C', out_dir, '-t', 'query', rel_filename],
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      universal_newlines=True)
  stdout, _ = p.communicate()
  if p.returncode != 0:
    return []

  # The output looks like:
  #   ../../relative/path/to/source.cc:
  #     outputs:
  #       obj/reative/path/to/target.source.o
  #       obj/some/other/target2.source.o
  #       another/target.txt
  #
  outputs_text = stdout.partition('\n  outputs:\n')[2]
  output_lines = [line.strip() for line in outputs_text.split('\n')]
  return [
      target for target in output_lines
      if target and (target.endswith('.o') or target.endswith('.obj'))
  ]


def GetClangCommandLineForNinjaOutput(out_dir, build_target):
  """Returns the Clang command line for building |build_target|

  Asks ninja for the list of commands used to build |filename| and returns the
  final Clang invocation.

  Args:
    out_dir: (String) Absolute path to ninja build output directory.
    build_target: (String) A build target understood by ninja

  Returns:
    (String or None) Clang command line or None if a Clang command line couldn't
        be determined.
  """
  p = subprocess.Popen(
      ['ninja', '-v', '-C', out_dir, '-t', 'commands', build_target],
      stdout=subprocess.PIPE,
      universal_newlines=True)
  stdout, stderr = p.communicate()
  if p.returncode != 0:
    return None

  # Ninja will return multiple build steps for all dependencies up to
  # |build_target|. The build step we want is the last Clang invocation, which
  # is expected to be the one that outputs |build_target|.
  for line in reversed(stdout.split('\n')):
    if 'clang' in line:
      return line
  return None


def GetClangCommandLineFromNinjaForSource(out_dir, filename):
  """Returns a Clang command line used to build |filename|.

  The same source file could be built multiple times using different tool
  chains. In such cases, this command returns the first Clang invocation. We
  currently don't prefer one toolchain over another. Hopefully the tool chain
  corresponding to the Clang command line is compatible with the Clang build
  used by YCM.

  Args:
    out_dir: (String) Absolute path to Chromium checkout.
    filename: (String) Absolute path to source file.

  Returns:
    (String or None): Command line for Clang invocation using |filename| as a
        source. Returns None if no such command line could be found.
  """
  build_targets = GetNinjaBuildOutputsForSourceFile(out_dir, filename)
  for build_target in build_targets:
    command_line = GetClangCommandLineForNinjaOutput(out_dir, build_target)
    if command_line:
      return command_line
  return None

def ProcessIndividualFlag(flag, out_dir):
  def abspath(path):
    return os.path.normpath(os.path.join(out_dir, path))

  include_pattern = re.compile(r'^(-I|-isystem|-F)(.+)$')
  include_match = include_pattern.match(flag)
  if include_match:
    # Relative paths need to be resolved, because they're relative to the
    # output dir, not the source.
    path = abspath(include_match.group(2))
    return include_match.group(1) + path
  elif flag.startswith('-std') or flag == '-nostdinc++':
    return flag
  elif flag.startswith('-march=arm'):
    # Value armv7-a of this flag causes a parsing error with a message
    # "ClangParseError: Failed to parse the translation unit."
    return None
  elif flag.startswith('-') and flag[1] in 'DWfmO':
    if flag == '-Wno-deprecated-register' or flag == '-Wno-header-guard':
      # These flags causes libclang (3.3) to crash. Remove it until things
      # are fixed.
      return None
    return flag
  elif flag == '-isysroot' or flag == '-isystem' or flag == '-I':
    if flag_index + 1 < len(clang_tokens):
      return flag.append(abspath(clang_tokens[flag_index + 1]))
  elif flag.startswith('--sysroot='):
    # On Linux we use a sysroot image.
    sysroot_path = flag.lstrip('--sysroot=')
    if sysroot_path.startswith('/'):
      return flag
    else:
      return '--sysroot=' + abspath(sysroot_path)
  return flag

def GetClangOptionsFromCommandLine(clang_commandline, out_dir,
                                   additional_flags):
  """Extracts relevant command line options from |clang_commandline|

  Args:
    clang_commandline: (String) Full Clang invocation.
    out_dir: (String) Absolute path to ninja build directory. Relative paths in
        the command line are relative to |out_dir|.
    additional_flags: (List of String) Additional flags to return.

  Returns:
    (List of Strings) The list of command line flags for this source file. Can
    be empty.
  """
  clang_flags = [] + additional_flags

  # Parse flags that are important for YCM's purposes.
  clang_tokens = shlex.split(clang_commandline)
  for flag_index, flag in enumerate(clang_tokens):
      clang_flags.append(ProcessIndividualFlag(flag, out_dir))
  return clang_flags

def FileCompilationCandidates(filename):
  basename, extension = os.path.splitext(filename)
  if extension == '.h':
    candidates = [basename + ext for ext in _header_alternates]
  else:
    candidates = [filename]

  return candidates

def GetAdditionalFlags(chrome_root):
  # Generally, everyone benefits from including Chromium's src/, because all of
  # Chromium's includes are relative to that.
  additional_flags = ['-I' + os.path.join(chrome_root)]

  # Version of Clang used to compile Chromium can be newer then version of
  # libclang that YCM uses for completion. So it's possible that YCM's libclang
  # doesn't know about some used warning options, which causes compilation
  # warnings (and errors, because of '-Werror');
  additional_flags.append('-Wno-unknown-warning-option')
  return additional_flags



def GetClangOptionsFromNinjaForFilename(chrome_root, filename):
  """Returns the Clang command line options needed for building |filename|.

  Command line options are based on the command used by ninja for building
  |filename|. If |filename| is a .h file, uses its companion .cc or .cpp file.
  If a suitable companion file can't be located or if ninja doesn't know about
  |filename|, then uses default source files in Blink and Chromium for
  determining the commandline.

  Args:
    chrome_root: (String) Path to src/.
    filename: (String) Absolute path to source file being edited.

  Returns:
    (List of Strings) The list of command line flags for this source file. Can
    be empty.
  """
  if not chrome_root:
    return []

  additional_flags = GetAdditionalFlags(chrome_root)

  sys.path.append(os.path.join(chrome_root, 'tools', 'vim'))
  from ninja_output import GetNinjaOutputDirectory
  out_dir = GetNinjaOutputDirectory(chrome_root)

  clang_line = None
  buildable_extension = os.path.splitext(filename)[1]
  for candidate in FileCompilationCandidates(filename):
    clang_line = GetClangCommandLineFromNinjaForSource(out_dir, candidate)
    if clang_line:
      buildable_extension = os.path.splitext(candidate)[1]
      break

  additional_flags += _extension_flags.get(buildable_extension, [])

  if not clang_line:
    # If ninja didn't know about filename or it's companion files, then try a
    # default build target. It is possible that the file is new, or build.ninja
    # is stale.
    clang_line = GetClangCommandLineFromNinjaForSource(out_dir,
                                                       GetDefaultSourceFile(
                                                           chrome_root,
                                                           filename))

  if not clang_line:
    return additional_flags

  return GetClangOptionsFromCommandLine(clang_line, out_dir, additional_flags)

def GetClangOptionsFromDBForFilename(chrome_root, filename):
  if not chrome_root:
    return []

  if not database:
    return None

  additional_flags = GetAdditionalFlags(chrome_root)

  for candidate in FileCompilationCandidates(filename):
    compilation_info = database.GetCompilationInfoForFile(candidate)
    if compilation_info:
        # ycm_core returns a StringVector we need to convert it.
        flags = [] + additional_flags
        for flag in compilation_info.compiler_flags_:
            flags.append(ProcessIndividualFlag(flag, compilation_database_folder))
        return flags
  return None

# FlagsForFile entrypoint is deprecated in YCM and has replaced by
# Settings.
def FlagsForFile(filename):
  """This is the old entry point for YCM. Its interface is fixed.

  Args:
    filename: (String) Path to source file being edited.

  Returns:
    (Dictionary)
      'flags': (List of Strings) Command line flags.
      'do_cache': (Boolean) True if the result should be cached.
  """
  return Settings(filename=filename)

def Settings(**kwargs):
  filename = kwargs['filename']
  abs_filename = os.path.abspath(filename)
  chrome_root = FindChromeSrcFromFilename(abs_filename)

  # Always check the compilation-commands.json database first.
  clang_flags = GetClangOptionsFromDBForFilename(chrome_root, filename)

  if not clang_flags:
    clang_flags = GetClangOptionsFromNinjaForFilename(chrome_root, abs_filename)

  # If clang_flags could not be determined, then assume that was due to a
  # transient failure. Preventing YCM from caching the flags allows us to try to
  # determine the flags again.
  should_cache_flags_for_file = bool(clang_flags)

  final_flags = _default_flags + clang_flags

  return {'flags': final_flags, 'do_cache': should_cache_flags_for_file}
