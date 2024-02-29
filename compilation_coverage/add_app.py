import subprocess
import re
import logging
import pymongo
import os
import shutil
from typing import Union
from symbol_engine import find_compilation_blocks_and_lines, CompilationBlock, find_children
from helpers import get_source_version_info, trigger_compilation_blocks, find_real_source_file, get_source_compilation_command, instrument_source
from helpers import SourceDocument, CompilationBlock, GitCommitStrategy, SHA1Strategy, SourceVersionStrategy
from coverity_vuln_scraper import fetch_vulnerabilities
import coverage
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from enum import Enum
DATABASE = coverage.DATABASE
SOURCES_COLLECTION = coverage.SOURCES_COLLECTION
COMPILATION_COLLECTION = coverage.COMPILATION_COLLECTION
COVERITY_DEFECTS_COLLECTION = coverage.COVERITY_DEFECTS_COLLECTION
db = coverage.db

logger = logging.getLogger(__name__)


class SourceStatus(Enum):
    NEW = 0
    DEPRECATED = 1
    EXISTING = 2
    UNKNOWN = 3


def is_new_source(src_path : str) -> SourceStatus:
    
    global db

    latest_version : Union[SourceVersionStrategy, dict] = get_source_version_info(src_path)

    existing_source : Union[SourceDocument, dict] = db[DATABASE][SOURCES_COLLECTION].find_one(
        {"source_path" : os.path.relpath(src_path, os.environ["UK_WORKDIR"])}
    )

    logger.debug(f"{src_path} has git commit log {latest_version}")
        
    if existing_source == None:
        logger.debug(f"{src_path} has not been found in the database. STATUS: NEW")
        return SourceStatus.NEW
    
    if GitCommitStrategy.version_key in latest_version and GitCommitStrategy.version_key in existing_source:
        if existing_source[GitCommitStrategy.version_key] == latest_version[GitCommitStrategy.version_key]:
            logger.debug(f"{src_path} source is already registered. STATUS: EXISTING checked using git commit id {latest_version[GitCommitStrategy.version_key]}")
            return SourceStatus.EXISTING
        else:
            # since it is a previous/deprecated version of that source we need to delete its compile blocks from the db, update the commit_id and restart the analysis process
            logger.debug(f"{src_path} has commit {latest_version[GitCommitStrategy.version_key]} but database has outdated commit {existing_source[GitCommitStrategy.version_key]}.STATUS: DEPRECATED")
            return SourceStatus.DEPRECATED
    
    if SHA1Strategy.version_key in latest_version and SHA1Strategy.version_key in existing_source:
        if existing_source[SHA1Strategy.version_key] == latest_version[SHA1Strategy.version_key]:
            logger.debug(f"{src_path} source is already registered. STATUS: EXISTING checked using sha1 id {latest_version[SHA1Strategy.version_key]}")
            return SourceStatus.EXISTING
        else:
            # since it is a previous/deprecated version of that source we need to delete its compile blocks from the db, update the commit_id and restart the analysis process
            logger.debug(f"{src_path} has hash {latest_version[SHA1Strategy.version_key]} but database has outdated hash {existing_source[SHA1Strategy.version_key]}.STATUS: DEPRECATED")
            return SourceStatus.DEPRECATED
        

    logger.critical(f"Cannot check source status. DB entry and current source have different version id types")
    logger.critical(f"{existing_source} VS {latest_version}")

    return SourceStatus.UNKNOWN
    
        

def update_db_activated_compile_blocks(activated_block_counters : list[int], src_path : str, compilation_tag: str) -> Union[SourceDocument, dict]:

    global db
    
    source_document : Union[SourceDocument, dict] = db[DATABASE][SOURCES_COLLECTION].find_one(
        {"source_path": os.path.relpath(src_path, os.environ["UK_WORKDIR"])}
    )

    logger.debug(f"BEFORE update of activated compile blocks\n{source_document}")

    logger.debug(f"ACTIVATED {activated_block_counters}")

    compile_blocks : Union[list[CompilationBlock], list[dict]] = source_document['compile_blocks']
        
    # maybe we are lucky and made some progress by activating new blocks :)
    # also calculate the number of compiled lines for this particular compilation for this source file
    compiled_lines = source_document["universal_lines"]
    for existing_block in compile_blocks:

        if existing_block['_local_id'] in activated_block_counters:
            existing_block['triggered_compilations'].append(compilation_tag)
            compiled_lines += existing_block["lines"]
        
    source_document["compiled_stats"][compilation_tag] = compiled_lines

    updated_source_document = db[DATABASE][SOURCES_COLLECTION].find_one_and_update(
        filter= {"source_path" : os.path.relpath(src_path, os.environ["UK_WORKDIR"])},
        update= {"$set" : source_document},
        return_document=pymongo.ReturnDocument.AFTER
    )

    logger.debug(f"AFTER update of compile regions\n{updated_source_document}")

    return updated_source_document

def init_source_in_db(source_status : SourceStatus, src_path : str, real_src_path : str, total_blocks : Union[list[CompilationBlock]], universal_lines : int, compilation_tag : str, lib_name : str) -> bool:

    global db

    find_children(total_blocks)

    # calculate total lines of code
    total_lines = universal_lines
    for cb in total_blocks:
        total_lines += cb.lines
    
    new_src_document : Union[SourceDocument, dict] = {
                "source_path" :  os.path.relpath(src_path, os.environ["UK_WORKDIR"]),
                "compile_blocks" : [compile_block.to_mongo_dict() for compile_block in total_blocks],
                "universal_lines" : universal_lines,
                "triggered_compilations" : [compilation_tag],
                "compiled_stats" : {},
                "total_lines" : total_lines,
                "lib" : lib_name
    }

    # TODO right now will only have git_commit_id since hashes are employed for generated or out of repo C source files
    version_info : Union[SourceVersionStrategy, dict] = get_source_version_info(real_src_path)

    new_src_document.update(version_info)

    #TODO what to add for real_src_path ? 

    # the source is new so we create a new entry in the database
    if source_status == SourceStatus.NEW:

        db[DATABASE][SOURCES_COLLECTION].insert_one(new_src_document)
        
        logger.debug(f"Initialized source in db\n{new_src_document}")

    # the source is deprecated we need to clear the compilation blocks of the existing entry and update latest git commit id
    elif source_status == SourceStatus.DEPRECATED:
        
        logger.debug(
            f"BEFORE source update due to deprecated commit\n" + 
            f"{db[DATABASE][SOURCES_COLLECTION].find_one({'source_path' : os.path.relpath(src_path, os.environ['UK_WORKDIR'])})}"
        )

        updated_source_document : Union[SourceDocument, dict] = db[DATABASE][SOURCES_COLLECTION].find_one_and_update(
            filter= {"source_path" : os.path.relpath(src_path, os.environ['UK_WORKDIR'])},
            update= {"$set" : new_src_document},
            return_document= ReturnDocument.AFTER
        )

        logger.debug(f"AFTER source update due to deprecated commit {updated_source_document}")
    else:
        logger.critical("Initialization failed since source_status is not NEW or DEPRECATED !")
        return False
    
    return True

def fetch_existing_compilation_blocks(src_path) -> list[CompilationBlock]:

    global db

    existing_blocks : Union[list[CompilationBlock], dict] = db[DATABASE][SOURCES_COLLECTION].find_one(
            filter= {"source_path" : os.path.relpath(src_path, os.environ['UK_WORKDIR'])},
            projection= {"compile_blocks" : 1, "_id" : 0}
        )

    total_blocks = []
    for raw_block in existing_blocks["compile_blocks"]:
        total_blocks.append(
            CompilationBlock(
                symbol_condition= raw_block["symbol_condition"],
                start_line= raw_block['start_line'],
                end_line= raw_block['end_line'],
                block_counter= raw_block['_local_id'],
                parent_counter= raw_block['_parent_id'],
                lines= raw_block['lines']
            )
        )
    logger.debug(f"Fetched compilation blocks from database:\n{total_blocks}")

    return total_blocks


def get_source_compile_coverage(compilation_tag : str, lib_name : str, app_build_dir : str, src_path : str) -> Union[SourceDocument, dict]:

    global db

    real_src_path = find_real_source_file(src_path, app_build_dir, lib_name)

    # TODO, analysis of c source files that do not exist but are generated by other files is disabled for now 
    if src_path != real_src_path:
        logger.warning(f"Found generator file {src_path} which will generate {real_src_path}. Skiping analysis for now ...")
        return None
    
    real_src_file_name = real_src_path.split("/")[-1]

    copy_source_path = f"{app_build_dir}/srcs/{real_src_file_name}"

    # very important !! the source file is copied before code instrumentation, later it will be back to its initial form
    shutil.copyfile(src_path, copy_source_path)

    source_status = is_new_source(src_path)

    # the source is already registered, so we can fetch all compilation blocks from the database
    # also bind the compilation id to this file since the universal lines of code are compiled
    if source_status == SourceStatus.EXISTING:
        total_blocks : list[CompilationBlock] = fetch_existing_compilation_blocks(src_path)

        db[DATABASE][SOURCES_COLLECTION].find_one_and_update(
            filter={"source_path" :  os.path.relpath(src_path, os.environ["UK_WORKDIR"])},
            update={"$push": {"triggered_compilations" : compilation_tag}}
        )

    # the source is not registered so we must parse the source file and find compilation blocks
    # or the source needs to be cleared due to deprecation so we must parse the updated source file and find compilation blocks
    elif source_status == SourceStatus.NEW or source_status == SourceStatus.DEPRECATED:

        total_blocks, universal_lines = find_compilation_blocks_and_lines(real_src_path)
        init_source_in_db(source_status, src_path, real_src_path, total_blocks, universal_lines, compilation_tag, lib_name)


    compile_command = get_source_compilation_command(app_build_dir, lib_name, real_src_path)

    if compile_command == None:
        logger.critical(f"No .o.cmd file which has compilation command for {src_path} in {lib_name}")
        db.find_one_and_delete({"source_path" : os.path.relpath(src_path, os.environ['UK_WORKDIR'])})
        return None

    instrument_source(total_blocks, real_src_path)

    activated_block_counters = trigger_compilation_blocks(compile_command)

    updated_src_document = update_db_activated_compile_blocks(
            activated_block_counters= activated_block_counters,
            src_path= src_path,
            compilation_tag= compilation_tag
    )
    
    # go back to source original code without instrumentation
    shutil.copyfile(copy_source_path, real_src_path)

    return updated_src_document



def analyze_application_sources(compilation_tag : str, app_build_dir : str, app_path : str):

    global rootTrie, db

    # get all source file using the make print-srcs
    logger.debug(app_path)
    proc = subprocess.Popen(f"cd {app_path} && make print-srcs", shell=True, stdout=subprocess.PIPE)

    stdout_raw, _ = proc.communicate()

    make_stdout = stdout_raw.decode()

    # try to find at least a lib and all sources on the next line, if not delete the compilation from the db
    lib_str_match = re.search("\s*([a-zA-Z]+:)\s*\n\s*(.*)\n", make_stdout)

    if lib_str_match == None:
        logger.critical("No lib or app source file dependencies found. Maybe `make print-srcs` was not called correctly")
        db[DATABASE][COMPILATION_COLLECTION].find_one_and_delete({"tag" : compilation_tag})
        exit(1)


    for lib_and_srcs_match in re.finditer("\s*([a-zA-Z_]+):\s*\n\s*(.*)\n", make_stdout):

        # match the first group -> [a-zA-Z_]
        lib_name = lib_and_srcs_match.group(1)

        # match the second group which is the next line after libblabla with source file paths -> .*
        srcs_line = lib_and_srcs_match.group(2)

        for src_path_raw in srcs_line.split(" "):
            src_path = src_path_raw.split("|")[0]

            if src_path[-2:] == ".c":
                logger.debug(f"---------------------{src_path}------------------------------------")

                get_source_compile_coverage(
                    compilation_tag= compilation_tag, 
                    lib_name= lib_name, 
                    app_build_dir= app_build_dir, 
                    src_path= src_path
                )


    
    # # get the Coverity defects and insert them in a table
    # defects = fetch_vulnerabilities()

    # for defect in defects:
    #     defect.update({"compilation_id" : compilation_id})

    # db[DATABASE][COVERITY_DEFECTS_COLLECTION].insert_many(defects)
    # print(defects)


def add_app_subcommand(app_workspace : str, app_build_dir : str, compilation_tag : str):

    global db

    if not os.path.exists(f"{app_build_dir}/srcs"):
        os.mkdir(f"{app_build_dir}/srcs")

    # check if an identic compilation occured

    existing_compilation = db[DATABASE][COMPILATION_COLLECTION].find_one(
                    {"tag" : compilation_tag}
        )
    if existing_compilation != None:
        logger.critical(f"An existing compilation has been previously registered with this tag and app\n{existing_compilation}")
        return
    
    logger.info(f"No compilation has been found. Proceeding with analyzing source {app_workspace}")

    compilation_id : ObjectId = db[DATABASE][COMPILATION_COLLECTION].insert_one({"tag" : compilation_tag, "app": app_workspace}).inserted_id
    logger.debug(f"New compilation has now id {compilation_id}")

    analyze_application_sources(compilation_tag, app_build_dir, app_workspace)