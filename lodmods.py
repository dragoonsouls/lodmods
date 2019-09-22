"""
Command line interface for LODModS tools.

Copyright (C) 2019 theflyingzamboni
"""

import argparse
import multiprocessing
import os
import sys
from config_handler import read_config, config_setup  # update_file_list
from disc_handler import backup_file, cdpatch, psxmode
from game_file_handler import extract_files, extract_all_from_list, insert_files, \
    insert_all_from_list, file_swap, swap_all_from_list, run_decompression, run_compression
"""import copy
import glob
import re
import shutil
import traceback
from id_dlg import find_dlg_from_file, find_hex_pattern, find_dlg_in_assets
from dump_insert import dump_script, dump_all, insert_script, insert_all
from csv_converter import scripts_to_csv, csv_to_scripts
from lod_patcher import update_mod_list, create_patches, patch"""


def _hex(x):
    """
    Convert str to hex int.

    Parameters
    ----------
    x : str
        Integer string.

    Returns
    -------
    int
        Hexadecimal integer.
    """

    return int(x, 16)


# noinspection PyShadowingNames
def _build_disc_dict(config_dict, version, disc_list, scripts_dir, game_files_dir):
    """
    Builds a disc_dict from a config file.

    Using information contained in the config dict, along with other
    information specified, build a disc_dict for use supplying necessary
    arguments to various LODModS commands.

    Parameters
    ----------
    config_dict : OrderedDict
        Dict of config file.
    version : str
        Game version to build disc_dict for.
    disc_list : list
        List of discs to include in disc_dict.
    scripts_dir : str
        Directory for script dumps.
    game_files_dir : str
        Directory where game files are extracted.

    Returns
    -------
    dict
        Dict containing information regarding game discs.
    """

    disc_dict = {}
    for disc in disc_list:
        if config_dict['[Game Discs]'][version][disc][0] != '':
            # If 'All Discs is specified, extract files from Disc 4.
            # Otherwise, do so for the disc specified.
            img = config_dict['[Game Discs]'][version][disc][0] \
                if disc != 'All Discs' \
                else config_dict['[Game Discs]'][version]['Disc 4'][0]
            disc_dir = os.path.join(version, disc)
            disc_dict[disc] = [
                os.path.join(config_dict['[Game Directories]'][version], img),
                [os.path.join(game_files_dir, disc_dir),
                 config_dict['[Game Discs]'][version][disc][1]],
                os.path.join(scripts_dir, disc_dir)]
        else:
            print('lodhack: %s file name not specified in config file' % disc)

    return disc_dict


def parse_arguments():
    """
    Argument parser for LODModS.

    Create argument parser for various functions in LODModS and return
    arguments namespace to pass to subcommands.
    """

    parser = argparse.ArgumentParser(
        usage='%(prog)s [-c config_file] command [command options]',
        description='''Command line utility for running The Legend of Dragoon
        Modding System tools. The first mandatory argument must be one of the
        commands from the command list, followed by any positional and optional
        arguments required by the function called. If desired, a non-default
        config file can be specified prior to the chosen command. Only one 
        function can be be called at a time. Use -h or --help after the
        selected function for  additional details on its usage. See readme for
        additional help and examples (Readme is currently work in progress).''')
    subparsers = parser.add_subparsers(dest='func')
    parser.add_argument('-c', '--config', dest='config_file',
                        default='lodmods.config', metavar='',
                        help='Configuration file name (default: lodmods.config)')

    # Create subparser for backup command.
    parser_b = subparsers.add_parser(
        'backup', usage='%(prog)s file [-r]', description='''Creates a backup
        files with the .orig extension for all listed files. If set to restore
        from backup, the files will be replaced with the backup file, if both 
        exist.''', help='Creates and restores files from backup')

    # Positional argument
    parser_b.add_argument('input_files', nargs='+', help='Files to backup')

    # Optional argument
    parser_b.add_argument('-r', '--restore', action='store_true',
                          dest='restore_from_backup',
                          help='''Replaces file with backup, if it exists. 
                          (default: False)''',)
    parser_b.set_defaults(file_backup=backup_file)

    # Create subparser for setup command.
    parser_su = subparsers.add_parser('setup', usage='%(prog)s version_1 version_2 ...',
                                      description='''Goes through the setup process to
                                      set the disc directory paths and disc names for
                                      each of the versions listed.''')

    # Positional arguments
    parser_su.add_argument('version_list', nargs='+',
                           help='List of all versions to set up')
    parser_su.set_defaults(config_setup=config_setup)

    # Create subparser for cdpatch command.
    parser_cd = subparsers.add_parser(
        'cdpatch', usage='%(prog)s version [-d disc_list] [-i]',
        description='''Wrapper for Neil Corlett's cdpatch utility. Extracts
        game files that are set to true in config file for game version and
        disc(s) specified. CDPatch is set to extract mode by default. For 
        insertion, cdpatch must be used for all XA and IKI files, but will
        not work for files larger than the original.''')

    # Positional argument
    parser_cd.add_argument('version', help='''Game version to extract/insert
                                           files from/into''')
    parser_cd.add_argument('-d', '--disc', nargs='+', required=True, metavar='',
                           help='''Discs to extract/insert files from/into
                           (use integers or 'all')''')

    # Optional argument
    parser_cd.add_argument('-i', '--insert', action='store_true', dest='mode',
                           help='Set cdpatch to insert mode')
    parser_cd.set_defaults(cdpatch=cdpatch)

    # Create subparser for psxmode command.
    parser_ps = subparsers.add_parser(
        'psxmode', usage='%(prog)s version [-d disc_list]',
        description='''Wrapper for CUE's psx-mode2 utility. Inserts game
        files that are set to true in config file for game version and
        disc(s) specified. Works for files larger than the original, 
        but will not insert XA and IKI files correctly.''')

    # Positional arguments
    parser_ps.add_argument('version', help='Game version to insert files into')
    parser_ps.add_argument('-d', '--disc', nargs='+', required=True, metavar='',
                           help='''Discs to insert files into (use integers or 'all')''')

    # Optional argument
    parser_ps.add_argument('-r', '--restore', action='store_true', dest='restore',
                           help='''Restore image from backup  before inserting
                           files (default: False)''')
    parser_ps.set_defaults(psxmode=psxmode)

    # Create subparser for decompress command.
    parser_dc = subparsers.add_parser(
        'decompress',
        usage='%(prog)s compressed_file [-s start_block] [-e end_block] [-b]',
        description='''Decompresses BPE-compressed files. Can optionally
        decompress specified   blocks only within range [start_block, 
        end_block).''', help='''Decompress BPE file''')

    # Positional argument
    parser_dc.add_argument('compressed_file', help='Specify file to decompress')

    # Optional arguments
    parser_dc.add_argument('-s', '--start', dest='start_block', type=int,
                           default=0, metavar='',
                           help='''Specify starting block (default: 0)''')
    parser_dc.add_argument('-e', '--end', dest='end_block', type=int,
                           default=512, metavar='',
                           help='''Specify ending block, non-inclusive 
                           (default: end of file)''')
    parser_dc.add_argument('-b', '--subfile', action='store_true',
                           dest='is_subfile', help='''Indicate that compressed
                           file is contained within another file 
                           (default: False)''')
    parser_dc.set_defaults(run_decompression=run_decompression)

    # Create subparser for compress command.
    parser_c = subparsers.add_parser(
        'compress',
        usage='%(prog)s decompressed_file [-m] [-b] [-a max_attempts] [-d]',
        description='''BPE-compresses files. If only a set of blocks was
        decompressed, inserts compressed block into compressed file.''',
        help='''BPE-compress file''')

    # Positional argument
    parser_c.add_argument('decompressed_file', help='File to compress')

    # Optional arguments
    parser_c.add_argument('-b', '--subfile', action='store_true',
                          dest='is_subfile', help='''Indicates that file to
                          compress is contained within another file 
                          (default: False)''')
    parser_c.add_argument('-m', '--mod', action='store_true', dest='mod_mode',
                          help='''Indicates file should be compressed to the
                          same size or smaller for mod compatibility (default:
                          False)''')
    parser_c.add_argument('-a', '--attempts', dest='max_attempts', type=int,
                          metavar='', default=100, help='''Maximum number of 
                          attempts to compress file if -b or -m have been used
                          (default: 100)''')
    parser_c.add_argument('-d', '--delete', action='store_true',
                          dest='delete_decompressed', help='''Indicate whether
                          to delete decompressed file after compression
                          (default: False)''')
    parser_c.set_defaults(run_compression=run_compression)

    """# Create subparser for finddlg command
    parser_ff = subparsers.add_parser('finddlg',
                                      usage='%(prog)s [-i input.txt]'
                                      ' [-o output.txt] target_folder',
                                      description='''Reads all text sample 
                                      entries from the input text file, searches
                                      the directory specified, and writes 
                                      files containing matches to the output
                                      file. Input file should contain one sample
                                      per line, with a tab delimited name to
                                      identify what the located file contains,
                                      if desired.''',
                                      help='''Find instances of all dialogue
                                      samples in input file''')

    # positional argument
    parser_ff.add_argument('folder', help='Specify folder to search')

    # optional arguments
    parser_ff.add_argument('-i', '--in', dest='input_file',
                           default='sample_dlg.txt', metavar='',
                           help='''Specify file containing list of text to 
                           search (default: %s\\sample_dlg.txt)''' %
                           os.path.dirname(os.path.realpath(sys.argv[0])))
    parser_ff.add_argument('-o', '--out', dest='output_file',
                           default='output.txt', metavar='',
                           help='''Specify output file for text locations
                           (default: %s\\output.txt)''' %
                           os.path.dirname(os.path.realpath(sys.argv[0])))
    parser_ff.set_defaults(find_dlg_from_file=find_dlg_from_file)

    # create subparser for findhex command
    parser_fh = subparsers.add_parser('findhex',
                                      usage='%(prog)s [-o output_file] '
                                      'target_folder',
                                      description='''Identifies all files that
                                      contain text and outputs their names to
                                      the specified location. Does not provide
                                      information on what text is included
                                      in which file. Use finddlg to locate
                                      specific text.''',
                                      help='''Find files containing instances
                                      of text end token''')

    # positional argument
    parser_fh.add_argument('folder', help='Specify folder to search')

    # optional arguments
    parser_fh.add_argument('-o', '--out', dest='output', default=None,
                           metavar='', help='''Specify output file for text
                           locations (prints to console by default)''')
    parser_fh.set_defaults(find_hex_pattern=find_hex_pattern)

    # create subparser for findassets command
    parser_fa = subparsers.add_parser('findassets',
                                     usage='%(prog)s input_file',
                                     description='''Uses text document list
                                     of subfiles containing dialogue (e.g. 
                                     DRGN21_299.bin, not DRGN21.bin) to 
                                     search asset files (e.g. DRGN21_299_3.bin)
                                     within folders generated by the exfiles
                                     or exfromlist functions, and appends file
                                     numbers of files that contain dialogue for
                                     each respective subfile entry. This
                                     can then be used for the dumpall and 
                                     insertall functions, after adding the
                                     necessary additional columns to each number
                                     entry. All columns should be tab delimited.''',
                                     help='''Find files containing text within
                                     subfolders''')

    # positional argument
    parser_fa.add_argument('file', help='''Specify text file containing the list 
                              of files whose asset folders are to be
                              searched''')
    parser_fa.set_defaults(find_dlg_in_assets=find_dlg_in_assets)"""

    # Create subparser for exfiles command.
    parser_e = subparsers.add_parser(
        'exfiles', usage='%(prog)s source_file [-p] [-f files numbers (int+)]',
        description='''Extracts specified file or files from the source MRG 
        file using the LBA table at the head of the file. Files to extract may
        be entered as single integers, hyphenated ranges, or a combination of
        the two.''', help='''Extract specified component
        files from target MRG file''')

    # Positional argument
    parser_e.add_argument('file', help='Specify extraction source file')

    # Optional arguments
    parser_e.add_argument('-p', '--padding', action='store_true',
                          dest='use_sector_padding', help='''Indicate
                          that file uses sector padding (e.g. DRGN2x.bin)''')
    parser_e.add_argument('-f', '--files', type=str, nargs='+',
                          dest='files_to_extract', default='*', metavar='',
                          help='''Enter file numbers and/or hyphenated 
                          ranges to extract (default: *; will extract all 
                          files)''')
    parser_e.set_defaults(extract_files=extract_files)

    # Create subparser for infiles command.
    parser_if = subparsers.add_parser(
        'infiles', usage='%(prog)s source_file [-p] [-f files numbers (int+)] [-d]',
        description='''Inserts specified file or files into the source MRG file
        using the file table at the head of the file. Files to insert may be entered
        as single integers, hyphenated ranges, or a combination of the two. The
        source file is automatically backed up if no backup exists. DO NOT delete
        backup file, as script insertion should always be done using the original
        file.''', help='''Insert specified .bin files into target MRG file''')

    # Positional argument
    parser_if.add_argument('file', help='''Specify file to insert files into''')

    # Optional arguments
    parser_if.add_argument('-p', '--padding', action='store_true',
                           dest='use_sector_padding', help='''Indicate that file
                           created uses sector padding (e.g. DRGN2x.bin)''')
    parser_if.add_argument('-f', '--files', type=str, nargs='+',
                           dest='files_to_insert', default='*', metavar='',
                           help='''Enter file numbers and/or hyphenated 
                           ranges to insert (default: *; will insert all 
                           files)''')
    parser_if.add_argument('-d', '--delete', action='store_true',
                           dest='del_component_folder', help='''Indicate whether
                           to delete folder containing files that were inserted
                           (default: False)''')
    parser_if.set_defaults(insert_files=insert_files)

    # Create subparser for exfromlist command.
    parser_el = subparsers.add_parser(
        'exfromlist', usage='%(prog)s game_version [-c file_category]',
        description='''Takes a text file listing files to extract (as
        generated by findhex or finddlg) and extracts or decompresses
        each file on the list. For each source file in the text file, 
        specify whether file uses sector padding (e.g. DRGN2x.BIN). The
        sector padding flag when set to true doubles as the subfile flag
        for BPE decompression. Use category option with 'swap' or '
        patch' to insert specific category of files only. Calls exfiles;
        see exfiles help for more details''', help='''Extract component
        files/decompress from all MRG/BPE files listed in input text
        file''')

    # Positional argument
    parser_el.add_argument('version', help='Game version as specified in config')

    # Optional argument
    parser_el.add_argument(
        '-c', '--category', dest='file_category', default='all', metavar='',
        help='''Category of files to extract from list file (default: extract
        all files''')
    parser_el.set_defaults(extract_all_from_list=extract_all_from_list)

    # Create subparser for infromlist command.
    parser_il = subparsers.add_parser(
        'infromlist', usage='%(prog)s game_version [-c file_category] [-d]',
        description='''Takes a text file listing files to insert (as generated
        by findhex or finddlg) and inserts or compresses each file on the list.
        For each  source file in the text file, specify whether file uses
        sector padding (e.g. DRGN2x.BIN). The sector padding flag when set to
        true doubles as the subfile flag for BPE compression. May specify
        whether to delete  component folder after inserting files. Use category
        option with  'swap' or 'patch' to extract specific category of file 
        only. Calls infiles and compress; see infiles and compress help for
        more  details.''', help='''Insert/compress specified files into MRG 
        files listed in input text file''')

    # Positional argument
    parser_il.add_argument('version', help='Game version as specified in config')

    # Optional arguments
    parser_il.add_argument('-c', '--category', dest='file_category', default='all',
                           metavar='', help='''Category of files to insert from list file
                           (default: insertt all files''')
    parser_il.add_argument('-d', '--delete', action='store_true',
                           dest='del_component_folders', help='''Indicate whether
                           to delete folders containing files that were inserted
                           (default: False)''')
    parser_il.set_defaults(insert_all_from_list=insert_all_from_list)

    # Create subparser for swap command.
    parser_s = subparsers.add_parser(
        'swap', usage='%(prog)s src_file dest_file',
        description='''Replace file with corresponding file from another
        version of  LOD. Destination file is backed up first.''',
        help='Swap file from another game version')

    # Positional arguments
    parser_s.add_argument('src_file', help='File to copy from')
    parser_s.add_argument('dest_file', help='File to copy to')
    parser_s.set_defaults(file_swap=file_swap)

    # Create subparser for the swapall command.
    parser_sa = subparsers.add_parser(
        'swapall', usage='%(prog)s swap_versions [-d]',
        description='''Takes text file containing list of asset files and
        copies those files from the source directory to the destination 
        directory. The destination files are backed up first.''',
        help='Swaps all files listed')

    # Positional arguments
    parser_sa.add_argument('swap_versions', help='File versions to swap '
                                                 '(format: src:dst)')

    # Optional arguments
    parser_sa.add_argument('-d', '--delete', action='store_true',
                           dest='del_src_dir', help='''Indicate whether
                           to delete source directory after files are
                           swapped (default: False)''')
    parser_sa.set_defaults(file_swap_from_list=swap_all_from_list)

    """# create subparser for dump command
    parser_d = subparsers.add_parser('dump',
                                     usage='%(prog)s file pointer_table_start '
                                     'pointer_table_end [-s] [-o output_folder] '
                                     '[-v ov_text_starts]',
                                     description='''Dumps the script in the input
                                     .bin file to a text file using its pointer 
                                     table(s). File may have either one pointer 
                                     table (text only) or two pointer tables (text
                                     and text window size). ptr_tbl_end indicates
                                     the end of the full pointer table, regardless
                                     of whether it is divided into two tables.''',
                                     help='Dump script to text file')

    # positional arguments
    parser_d.add_argument('file', help='Specify file to dump script from')
    parser_d.add_argument('ptr_tbl_start', type=str, help='''Offset of 
                          beginning of pointer table''')
    parser_d.add_argument('ptr_tbl_end', type=str, help='''Offset of 
                          end of pointer table''')

    # optional arguments
    parser_d.add_argument('-s', '--single', dest='single_ptr_tbl',
                          default='0', metavar='', help='''Indicates that
                          pointer table is a single table (default: False)''')
    parser_d.add_argument('-f', '--folder', dest='output_folder',
                          default='script_dumps', metavar='', help='''Specify
                          output folder for dumped script (default:
                          @Scripts under [Modding Directories])''')
    parser_d.add_argument('-v', '--ovl', dest='ov_text_starts',
                          default=None, metavar='', help='''Specify starting
                          offsets of text if file is .OV_ (default: None)''')
    parser_d.set_defaults(dump_script=dump_script)

    # create subparser for dumpall command
    parser_da = subparsers.add_parser('dumpall',
                                      usage='%(prog)s game_version [-f script_folder] '
                                      '[-c csv_file]',
                                      description='''Takes text file containing
                                      a list of asset files (as generated by
                                      the findassets command) and dumps the 
                                      dialogue from each file in the list to the
                                      output folder specified. Some modification
                                      of the findassets output is required.
                                      Additional tab-delimited columns must be
                                      added to each line for dumpall to 
                                      function. In order following the file
                                      name, these are: pointer table start
                                      offset, pointer table end offset (both in
                                      hex), and a boolean value indicating
                                      whether there is one pointer table (True
                                      or 1) or two (False or 0). If desired,
                                      script files can be merged into a CSV file,
                                      which may be edited and used to generate
                                      new script files.''',
                                      help='''Dump script from all files
                                      listed in input text file''')

    # positional argument
    parser_da.add_argument('version', help='''Game version to dump
                           scripts from''')

    # optional arguments
    parser_da.add_argument('-f', '--folder', dest='script_folder',
                           default=None, metavar='',
                           help='''Output folder for dumped scripts (default: 
                           @Scripts under [Modding Directories])''')
    parser_da.add_argument('-c', '--csv', action='store_true', dest='create_csv',
                           help='''Merge dumped scripts into a CSV
                           file (default: False)''')
    parser_da.set_defaults(dump_all=dump_all)

    # create subparser for insert command
    parser_i = subparsers.add_parser('insert',
                                     usage='%(prog)s script_file target'
                                     '_file pointer_table_start pointer_table_end'
                                     '[-s] [-c] [-v ov_text_starts]',
                                     description='''Inserts script file into
                                     target .bin file and updates the pointer
                                     table(s). File may have either one pointer 
                                     table (text only) or two pointer tables (text
                                     and text window size). ptr_tbl_end indicates
                                     the end of the full pointer table, regardless
                                     of whether it is divided into two tables. 
                                     Should be specified with optional switch if
                                     file is for combat or a cutscene.''',
                                     help='''Insert text script into .bin file''')

    # positional arguments
    parser_i.add_argument('script_file', help='Specify script file to insert')
    parser_i.add_argument('ptr_tbl_start', type=str, help='''Offset of 
                          beginning of pointer table''')
    parser_i.add_argument('ptr_tbl_end', type=str, help='''Offset of 
                          end of pointer table''')
    parser_i.add_argument('-f', '--file', dest='target_file', required=True,
                          metavar='', help='''Specify .bin file to insert 
                          script into''')

    # optional arguments
    parser_i.add_argument('-s', '--single', action='store_true',
                          dest='single_ptr_tbl', help='''Indicates that
                          pointer table is a single table (default: False)''')
    parser_i.add_argument('-c', '--combat', action='store_true',
                          dest='combat_ptrs', help='''Indicates that
                          script is from combat or cutscene file 
                          (default: False)''')
    parser_i.add_argument('-v', '--ovl', dest='ov_text_starts',
                          default=None, metavar='', help='''Specify starting
                          offsets of text if file is .OV_ (default: None)''')
    parser_i.set_defaults(insert_script=insert_script)

    # create subparser for insertall command
    parser_ia = subparsers.add_parser('insertall',
                                      usage='%(prog)s game_version [-f script_folder] '
                                      '[-c csv_file]',
                                      description='''Takes text file containing
                                      a list of asset files (as generated by
                                      the findassets command) and inserts the 
                                      dialogue from the script file that 
                                      corresponds to each .bin file in the list.
                                      Input text file should be the same one used
                                      for the dumpall command. Script files must
                                      have the same file name as the .bin files
                                      they correspond to (i.e. DRGN21_299_3.txt
                                      and DRGN21_299_3.bin). A CSV file containing
                                      the merged scripts may be used to generate
                                      new script files for insertion.''',
                                      help='''Inserts text scripts into all .bin
                                      files listed in input text file.''')

    # positional argument
    parser_ia.add_argument('version', help='''Game version to insert
                           scripts into''')

    # optional arguments
    parser_ia.add_argument('-f', '--folder', dest='script_folder',
                           default=None, metavar='',
                           help='''Folder containing dumped scripts to insert
                           (default: @Scripts under [Modding Directories])''')
    parser_ia.add_argument('-c', '--csv', action='store_true', dest='use_csv',
                           help='''Generate text files for insertion from
                           CSV files (default: False)''')
    parser_ia.set_defaults(insert_all=insert_all)

    # create subparser for tocsv command
    parser_tc = subparsers.add_parser('tocsv',
                                      usage='%(prog)s game_version -d disc(s) [-f script_folder]',
                                      description='''Converts script files specified
                                      in list_file into a single ordered CSV file,
                                      which can be edited and used for text insertion.''',
                                      help='''Convert .txt script files to CSV''')
    # positional arguments
    parser_tc.add_argument('version', help='''Game version to create CSV for''')
    parser_tc.add_argument('-d', '--disc', nargs='+', required=True, metavar='',
                           help='''Discs to create CSV for (use integer numbers or 'all')''')

    # optional arguments
    parser_tc.add_argument('-f', '--folder', dest='script_folder',
                           default=None, metavar='',
                           help='''Folder containing scripts to merge
                           (default: @Scripts under [Modding Directories])''')
    parser_tc.set_defaults(scripts_to_csv=scripts_to_csv)

    # create subparser for fromcsv command
    parser_fc = subparsers.add_parser('fromcsv',
                                      usage='%(prog)s game_version -d disc(s) [-f script_folder]',
                                      description='''Generates separate script text
                                      files in script_folders from 'New Dialogue' column
                                      in a script CSV''',
                                      help='''Convert CSVs to .txt script files''')

    # positional arguments
    parser_fc.add_argument('version', help='''Game version of CSV''')
    parser_fc.add_argument('-d', '--disc', nargs='+', required=True, metavar='',
                           help='''Discs to create scripts from (use integer numbers or 'all')''')

    # optional arguments
    parser_fc.add_argument('-f', '--folder', dest='script_folder',
                           default=None, metavar='',
                           help='''Folder to output new script files to
                           (default: @Scripts under [Modding Directories])''')
    parser_fc.set_defaults(csv_to_scripts=csv_to_scripts)"""

    """# create subparser for createpatch command
    parser_cp = subparsers.add_parser('createpatch',
                                      usage='',
                                      description='''''')

    # positional arguments
    parser_cp.add_argument('version',  help='Game version to create patches for')
    parser_cp.set_defaults(create_patches=create_patches)

    # create subparser for patch command
    parser_p = subparsers.add_parser('patch', usage='',
                                     description='''''')

    # positional arguments
    parser_p.add_argument('version', help='Game version to patch')

    # optional argument
    parser_p.add_argument('-s', '--swap', metavar='',
                          help='Game version to swap files from')
    parser_p.add_argument('-d', '--delete', action='store_true', dest='delete',
                          help='''Specify whether to delete game files folder
                          after patching (default: False)''')
    parser_p.set_defaults(patch=patch)"""

    # display help if no arguments passed to lodmods.py
    if len(sys.argv) == 1:
        parser.print_help()

    return parser.parse_args()


if __name__ == '__main__':
    multiprocessing.freeze_support()

    try:
        args = parse_arguments()
        config_dict = read_config(args.config_file)
        game_files_dir = config_dict['[Modding Directories]']['Game Files']
        scripts_dir = config_dict['[Modding Directories]']['Scripts']
        patch_dir = config_dict['[Modding Directories]']['Patches']
        patch_list = []

        if args.func == 'backup':
            for input_file in args.input_files:
                print('Backing up %s' % input_file)
                args.file_backup(input_file, args.restore_from_backup)
        elif args.func == 'setup':
            args.config_setup(args.config_file, config_dict, args.version_list)
        elif args.func == 'cdpatch':
            if args.disc[0] == '*':
                args.disc = ['All Discs', 'Disc 1', 'Disc 2', 'Disc 3', 'Disc 4']
            else:
                args.disc = ['All Discs' if x.lower() == 'all'
                             else ' '.join(('Disc', x)) for x in args.disc]
            disc_dict = _build_disc_dict(config_dict, args.version, args.disc,
                                         scripts_dir, game_files_dir)
            args.mode = '-i' if args.mode else '-x'
            args.cdpatch(disc_dict, args.mode)
        elif args.func == 'psxmode':
            if args.disc[0] == '*':
                args.disc = ['All Discs', 'Disc 1', 'Disc 2', 'Disc 3', 'Disc 4']
            else:
                args.disc = ['All Discs' if x.lower() == 'all'
                             else ' '.join(('Disc', x)) for x in args.disc]
            disc_dict = _build_disc_dict(config_dict, args.version, args.disc,
                                         scripts_dir, game_files_dir)
            if 'All Discs' in args.disc:
                for disc in ('Disc 1', 'Disc 2', 'Disc 3', 'Disc 4'):
                    if disc not in disc_dict.keys():
                        disc_dict[disc] = [config_dict['[Game Discs]'][args.version][disc][0],
                                           ['', {}], '']
            args.psxmode(disc_dict, args.restore)
        elif args.func == 'decompress':
            args.run_decompression(args.compressed_file, args.start_block,
                                   args.end_block, args.is_subfile)
        elif args.func == 'compress':
            args.run_compression(args.decompressed_file, args.mod_mode,
                                 args.is_subfile, args.max_attempts,
                                 args.delete_decompressed)
        elif args.func == 'exfiles':
            args.files_to_extract = [[x] for x in args.files_to_extract]
            args.extract_files(args.file, args.use_sector_padding, args.files_to_extract)
        elif args.func == 'exfromlist':
            file = config_dict['[File Lists]'][args.version]
            disc_list = list(config_dict['[Game Discs]'][args.version].keys())
            disc_dict = _build_disc_dict(config_dict, args.version, disc_list, scripts_dir,
                                         game_files_dir)
            args.file_category = ''.join(('[', args.file_category.upper(), ']'))
            args.extract_all_from_list(file, disc_dict, args.file_category)
        elif args.func == 'infiles':
            args.files_to_insert = [[x] for x in args.files_to_insert]
            args.insert_files(args.file, args.use_sector_padding, args.files_to_insert,
                              args.del_component_folder)
        elif args.func == 'infromlist':
            file = config_dict['[File Lists]'][args.version]
            disc_list = list(config_dict['[Game Discs]'][args.version].keys())
            disc_dict = _build_disc_dict(config_dict, args.version, disc_list, scripts_dir,
                                         game_files_dir)
            args.file_category = ''.join(('[', args.file_category.upper(), ']'))
            args.insert_all_from_list(file, disc_dict, args.file_category,
                                      args.del_component_folders)
        elif args.func == 'swap':
            args.file_swap(args.src_file, args.dest_file)
        elif args.func == 'swapall':
            list_file = config_dict['[File Swap]'][args.swap_versions]
            version_list = args.swap_versions.split(':')
            disc_dict_pair = []
            for version in version_list:
                disc_dict = {}
                for disc in config_dict['[Game Discs]'][version].keys():
                    if config_dict['[Game Discs]'][version][disc][0] != '0':
                        img = config_dict['[Game Discs]'][version][disc][0] \
                            if disc != 'All Discs' \
                            else config_dict['[Game Discs]'][version]['Disc 4'][0]
                        disc_dir = os.path.splitext(config_dict['[Game Discs]']
                                                    [version][disc][0])[0]
                        disc_dict[disc] = [
                            os.path.join(config_dict['[Game Directories]'][version], img),
                            [os.path.join(game_files_dir, disc_dir),
                             config_dict['[Game Discs]'][version][disc][1]]]
                disc_dict_pair.append(disc_dict)
            args.file_swap_from_list(list_file, disc_dict_pair, args.del_src_dir)
        """elif args.func == 'finddlg':
            args.find_dlg_from_file(args.folder, args.input_file, args.output_file)
        elif args.func == 'findhex':
            args.find_hex_pattern(args.folder, args.output)
        elif args.func == 'findassets':
            args.find_dlg_in_assets(args.file)
        elif args.func == 'dump':
            ptr_tbl_start = [int(x, 16) for x in args.ptr_tbl_start.split(',')]
            ptr_tbl_end = [int(x, 16) for x in args.ptr_tbl_end.split(',')]
            single_ptr_tbl = []
            for x in args.single_ptr_tbl.split(','):
                if x == '1' or x.lower() == 'true':
                    single_ptr_tbl.append(True)
                elif x == '0' or x.lower() == 'false':
                    single_ptr_tbl.append(False)
                else:
                    raise ValueError
            try:
                ov_text_starts = [int(x, 16) for x in args.ov_text_starts.split(',')]
            except AttributeError:
                ov_text_starts = None
            args.dump_script(args.file, args.output_folder, ptr_tbl_start, ptr_tbl_end,
                             single_ptr_tbl, ov_text_starts)
        elif args.func == 'dumpall':
            file = config_dict['[File Lists]'][args.version]
            if args.script_folder is None:
                args.script_folder = scripts_dir
            disc_list = list(config_dict['[Game Discs]'][args.version].keys())
            disc_dict = _build_disc_dict(config_dict, args.version, disc_list, args.script_folder, 
                                         game_files_dir)
            args.dump_all(file, disc_dict, args.create_csv, args.version)
        elif args.func == 'insert':
            ptr_tbl_start = [int(x, 16) for x in args.ptr_tbl_start.split(',')]
            ptr_tbl_end = [int(x, 16) for x in args.ptr_tbl_end.split(',')]
            ov_text_starts = [int(x, 16) for x in args.ov_text_starts.split(',')]
            args.insert_script(args.script_file, args.target_file,
                               ptr_tbl_start, ptr_tbl_end,
                               args.single_ptr_tbl, args.combat_ptrs,
                               ov_text_starts)
        elif args.func == 'insertall':
            file = config_dict['[File Lists]'][args.version]
            if args.script_folder is None:
                args.script_folder = scripts_dir
            disc_list = list(config_dict['[Game Discs]'][args.version].keys())
            disc_dict = _build_disc_dict(config_dict, args.version, disc_list, args.script_folder, 
                                         game_files_dir)
            args.insert_all(file, disc_dict, args.use_csv, args.version)
        elif args.func == 'tocsv':
            args.disc = ['All Discs' if x.lower() == 'all'
                         else ' '.join(('Disc', x)) for x in args.disc]
            if args.script_folder is None:
                args.script_folder = scripts_dir
            disc_dict = _build_disc_dict(config_dict, args.version, args.disc, args.script_folder, 
                                         game_files_dir)
            for disc, disc_val in disc_dict.items():
                if not os.path.exists(disc_val[2]):
                    print('\ntocsv: Script folder %s not found' % disc_val[2])
                    continue
                csv_file = os.path.join(os.path.dirname(disc_val[2]),
                    ''.join((args.version, '_',
                             disc.lower().replace(' ', ''), '.csv')))
                args.scripts_to_csv(csv_file, disc_val[2])
        elif args.func == 'fromcsv':
            args.disc = ['All Discs' if x.lower() == 'all'
                         else ' '.join(('Disc', x)) for x in args.disc]
            if args.script_folder is None:
                args.script_folder = scripts_dir
            disc_dict = _build_disc_dict(config_dict, args.version, args.disc, args.script_folder, 
                                         game_files_dir)
            for disc, disc_val in disc_dict.items():
                csv_file = os.path.join(os.path.dirname(disc_val[2]),
                    ''.join((args.version, '_',
                             disc.lower().replace(' ', ''), '.csv')))
                if not os.path.exists(csv_file):
                    print('\nfromcsv: CSV file %s not found' % csv_file)
                    continue
                args.csv_to_scripts(csv_file, disc_val[2])
        elif args.func == 'createpatch':
            list_file = config_dict['[File Lists]'][args.version]
            disc_dict = {}
            for disc, val in config_dict['[Game Discs]'][args.version].items():
                if (disc != 'All Discs' and
                    config_dict['[Game Discs]'][args.version][disc][0] != '') \
                        or (disc == 'All Discs' and
                            config_dict['[Game Discs]'][args.version]['Disc 4'][0] != ''):
                    img = config_dict['[Game Discs]'][args.version][disc][0] \
                        if disc != 'All Discs' \
                        else config_dict['[Game Discs]'][args.version]['Disc 4'][0]
                    disc_dir = os.path.join(args.version, disc)
                    disc_dict[disc] = [
                        os.path.join(config_dict['[Game Directories]'][args.version], img),
                        [os.path.join(game_files_dir, disc_dir),
                         config_dict['[Game Discs]'][args.version][disc][1]]]
            args.create_patches(list_file, game_files_dir, patch_dir, disc_dict)
        elif args.func == 'patch':
            print('\n---------------------------------------------\n'
                  'LODModS Patcher v 1.31 - (c) theflyingzamboni\n'
                  '---------------------------------------------\n')
            print('----------------------------\n'
                  'Additional Credits:\n'
                  'CDPatch - (c) Neill Corlett\n'
                  'PSX-Mode2 - (c) CUE\n'
                  'Xdelta3 - (c) Josh MacDonald\n\n'
                  'Links can be found in readme\n'
                  '----------------------------\n')

            version_list = (args.swap, args.version)

            try:
                config_setup(args.config_file, config_dict, [x for x in version_list if x], True)
                update_mod_list(args.config_file, config_dict, version_list)

                disc_dict_pair = []
                for version in version_list:
                    disc_dict = {}
                    if version is not None:
                        for disc in config_dict['[Game Discs]'][version].keys():
                            if (disc != 'All Discs' and
                                config_dict['[Game Discs]'][version][disc][0] != '') \
                                    or (disc == 'All Discs' and
                                        config_dict['[Game Discs]'][version]['Disc 4'][0] != ''):
                                img = config_dict['[Game Discs]'][version][disc][0] \
                                    if disc != 'All Discs' \
                                    else config_dict['[Game Discs]'][version]['Disc 4'][0]
                                disc_dir = os.path.join(version, disc)
                                disc_dict[disc] = [
                                    os.path.join(config_dict['[Game Directories]'][version], img),
                                    [os.path.join(game_files_dir, disc_dir),
                                     config_dict['[Game Discs]'][version][disc][1]]]
                    disc_dict_pair.append(disc_dict)

                list_file = config_dict['[File Lists]'][args.version]
                update_file_list(list_file, config_dict, disc_dict_pair[1])

                for mod, mod_val in config_dict['[Mod List]'].items():
                    if not mod_val:
                        continue
                    for file in glob.glob(os.path.join(mod, 'patches', '**', '*.xdelta'),
                                          recursive=True):
                        patch_list.append(file)

                print()
                args.patch(list_file, disc_dict_pair, copy.deepcopy(patch_list))

                if args.delete:
                    try:
                        shutil.rmtree(game_files_dir)
                    except PermissionError:
                        print('LODModS: Could not delete %s' % game_files_dir)
            except FileNotFoundError:
                print(traceback.format_exc())
                print('LODModS: %s not found' % sys.exc_info()[1].filename)
            except SystemExit:
                pass
            finally:
                block_range_pattern = re.compile('(\.{\d+-\d+})')
                for patch in patch_list:
                    backup = '.'.join((patch, 'orig'))
                    if block_range_pattern.search(patch) and os.path.exists(backup):
                        backup_file(patch, True)
                        os.remove(backup)"""
    except KeyboardInterrupt:
        print('\n')
