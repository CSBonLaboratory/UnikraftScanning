
import subprocess
import logging
import os
import re
import logging
import hashlib
from bson.objectid import ObjectId
from dataclasses import dataclass
from typing import Union

def git_commit_strategy(real_src_path : str) -> ObjectId:
    src_tokens = real_src_path.split("/")

    src_sub_path = "/".join(src_tokens[:-1])

    src_name = src_tokens[-1]
    
    proc = subprocess.Popen(f"cd {src_sub_path} && git log -n 1 --pretty=format:%H {src_name}", shell=True, stdout=subprocess.PIPE)

    latest_commit_id_raw, _ = proc.communicate()

    latest_commit_id = latest_commit_id_raw.decode()

    return latest_commit_id


def remove_comments(cpy_src : str):

    # C comment remover, courtesy to https://gist.github.com/ChunMinChang/88bfa5842396c1fbbc5b

    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return "\n" * s.count( "\n" )
        else:
            return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )

    with open(cpy_src, "rt") as fdr:
        text = fdr.read()

    with open(cpy_src, "wt") as fdw:
        fdw.write(re.sub(pattern, replacer, text))

    return 

def hash_strategy(real_src_path) -> str:
    sha1 = hashlib.sha1()

    with open(real_src_path, 'rb') as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            sha1.update(data)

    return sha1.hexdigest()

class BackendMongoInterface:
    def to_mongo_dict(self) -> dict:
        pass


@dataclass
class SourceVersionStrategy(BackendMongoInterface):

    version_value = None

    version_key = None

    def apply_strategy(self, real_src_path : str):
        pass

    def to_mongo_dict(self) -> dict:
        return {self.version_key : self.version_value}

@dataclass
class GitCommitStrategy(SourceVersionStrategy):

    version_key = "git_commit_id"
    version_value = None

    def apply_strategy(self, real_src_path: str):
        self.version_value = git_commit_strategy(real_src_path)
        
    
    def to_mongo_dict(self) -> dict:
        return super().to_mongo_dict()

    
@dataclass 
class SHA1Strategy(SourceVersionStrategy, BackendMongoInterface):

    version_key = "sha1_id"
    version_value = None

    def apply_strategy(self, real_src_path: str):
        self.version_value = hash_strategy(real_src_path)
    
    def to_mongo_dict(self) -> dict:
        return super().to_mongo_dict()

@dataclass(init=False)
class CompilationBlock(BackendMongoInterface):

    symbol_condition : str
    triggered_compilations : list[ObjectId]
    start_line : int
    end_line : int
    block_counter : int
    parent_counter : int
    lines : int
    children : list[int]
    

    def __init__(self, mongo_dict : dict) -> None:
        
        self.symbol_condition = mongo_dict["symbol_condition"]
        

        if "triggered_compilations" in mongo_dict:
            self.triggered_compilations = mongo_dict["triggered_compilations"]
        else:
            self.triggered_compilations = []
        
        self.start_line = mongo_dict["start_line"]
        self.end_line = mongo_dict["end_line"]

        self.block_counter = mongo_dict["_local_id"]
        self.parent_counter = mongo_dict["_parent_id"]
        self.lines = mongo_dict["lines"]

        if "children" in mongo_dict:
            self.children = mongo_dict["children"]
        else:
            self.children = []

    def to_mongo_dict(self) -> dict:

        ans = {}

        ans["symbol_condition"] = self.symbol_condition
        ans["triggered_compilations"] = self.triggered_compilations
        ans["start_line"] = self.start_line
        ans["end_line"] = self.end_line
        ans["_local_id"] = self.block_counter
        ans["_parent_id"] = self.parent_counter
        ans["lines"] = self.lines
        ans["children"] = self.children
    
        return ans


@dataclass(init=False)
class SourceDocument(BackendMongoInterface):

    source_path : str
    triggered_compilations : list[ObjectId]
    universal_lines : int
    source_version : SourceVersionStrategy
    lib : str
    compile_blocks : list[CompilationBlock]

    # universal_lines + all lines from compilation blocks
    total_lines : int

    # dict where key is the compilation tag and value is number of compiled lines in this document for compilation tag in key
    compiled_stats : dict

    def __init__(self, mongo_dict : dict) -> None:
        
        self.source_path = mongo_dict["source_path"]

        if "triggered_compilations" in mongo_dict:
            self.triggered_compilations = mongo_dict["triggered_compilations"]
        else:
            self.triggered_compilations = []
        
        if "git_commit_id" in mongo_dict:
            self.source_version = GitCommitStrategy()
            self.source_version.version_value = mongo_dict["git_commit_id"]
        elif "sha1_id" in mongo_dict:
            self.source_version = SHA1Strategy()
            self.source_version.version_value = mongo_dict["sha1_id"]
        
        self.lib = mongo_dict["lib"]

        self.universal_lines = mongo_dict["universal_lines"]

        self.compile_blocks = [CompilationBlock(cb) for cb in mongo_dict["compile_blocks"]]

        self.total_lines = mongo_dict["total_lines"]

        if "compiled_stats" in mongo_dict:
            self.compiled_stats = mongo_dict["compiled_stats"]
        else:
            self.compiled_stats = {}

    def to_mongo_dict(self) -> dict:
        
        ans = {}

        ans["source_path"] = self.source_path
        ans["triggered_compilations"] = self.triggered_compilations
        
        ans.update(self.source_version.to_mongo_dict())

        ans["lib"] = self.lib

        ans["compile_blocks"] = [cb.to_mongo_dict() for cb in self.compile_blocks]

        return ans


def get_source_version_info(real_src_path) -> Union[SourceVersionStrategy, dict]:

    logger = logging.getLogger(__name__)

    latest_commit_id = git_commit_strategy(real_src_path)

    if latest_commit_id != "":
        return {GitCommitStrategy.version_key : latest_commit_id}

    logger.critical(f"{real_src_path} is not part of a valid git repository or submodule. Defaulting to SHA256 strategy ...")

    return {SHA1Strategy.version_key : hash_strategy(real_src_path)}


def trigger_compilation_blocks(activation_cmd : str) -> list[int]:

    logger = logging.getLogger(__name__)

    proc = subprocess.Popen(activation_cmd, shell=True, stderr = subprocess.PIPE)

    _, warnings_raw = proc.communicate()
    
    warnings = warnings_raw.decode()

    f = open("dorel","a")
    f.write(warnings)
    f.close()

    # return the numbers of compilation blocks found in warning directives
    activated_blocks = [int(block_match) for block_match in re.findall("warning: #warning COMPILATION_COVERAGE_([0-9]+)", warnings)]

    logger.debug(f"Compilation blocks triggered are {activated_blocks}")

    return activated_blocks


def find_real_source_file(src_path : str, app_build_dir : str, lib_name : str) -> str:

    logger = logging.getLogger(__name__)

    # copy the source so that after the code instrumentation of the original files, we swap back to the starting version
    # something like file swaping

    src_path_tokens = src_path.split('/')

    src_file_name = src_path_tokens[-1]

    src_parent_path = "/".join(src_path_tokens[ : -1])

    # in case there are some files like namemap.awk>.c
    # then src_file_name whould also include intermediate extension that might dissapear during compilation 
    src_file_name_no_extension = src_file_name.split(".")[0]

    # pure src file name with only .c extension for cases like namemap.awk>.c
    src_file_name_c_extension = src_file_name_no_extension + ".c"

    possible_src_locations = []

    possible_src_locations.append(
        (
            src_path,
            "Found the original src file in the path specified by make print-srcs"
        )
    )
    possible_src_locations.append(
        (
            src_parent_path + "/" + src_file_name_c_extension,
            "Found src file without intermediate extensions in the path specified by make print-srcs"
        )
    )
    possible_src_locations.append(
        (
            app_build_dir + "/" + lib_name + src_file_name,
            "Found original src file in the build directory"
        )
    )
    possible_src_locations.append(
        (
            app_build_dir + "/" + lib_name + src_file_name_c_extension,
            "Found src file without intermediate extensions in the build directory"
        )
    )

    real_src_path = None

    for (location, message) in possible_src_locations:
        if os.path.isfile(location):
            real_src_path = location
            logger.debug(message)
            logger.debug(f"Real path {real_src_path} VS Input path {src_path}")
            break

    if real_src_path == None:
        logger.critical(f"No source file found for {src_path}. Skiping this source file")
        return None
    
    return real_src_path


def instrument_source(parsed_compilation_bocks : list[CompilationBlock], copy_src_path):

    copy_src_fd = open(copy_src_path, 'r')

    instrumented_code = []

    lines = copy_src_fd.readlines()

    for i in range(len(lines)):
        instrumented_code.append(lines[i])
        
        current_block = [block for block in parsed_compilation_bocks if block.start_line == i]

        if current_block != []:
            instrumented_code.append(f"#warning COMPILATION_COVERAGE_{current_block[0].block_counter}\n")
    
    copy_src_fd.close()

    instr_copy_src_fd = open(copy_src_path, "r+")

    instr_copy_src_fd.writelines(instrumented_code)

    instr_copy_src_fd.close()



def get_source_compilation_command(app_build_dir, lib_name, real_src_path) -> str | None:

    # the source is a c file, we need .o.cmd extension, but there might be files that do not respect the naming convention
    # iterate through .o.cmd files

    src_file_name = real_src_path.split("/")[-1]

    logger = logging.getLogger(__name__)

    for compile_command_file in os.listdir(f"{app_build_dir}/{lib_name}"):

        if src_file_name[:-2] in compile_command_file and ".o.cmd" in compile_command_file:
            
            logger.debug(f"Searching compilation command for {src_file_name} in {compile_command_file}")

            cmd_file_fd = open(f"{app_build_dir}/{lib_name}/{compile_command_file}", "r")

            # ignore the "" from the command
            make_command = cmd_file_fd.readline()[2:]

            make_tokens = make_command.split()

            try:
                gcc_source_flag_idx = make_tokens.index("-c")
                if real_src_path == make_tokens[gcc_source_flag_idx + 1]:
                    cmd_file_fd.close()
                    return make_command
                else:
                    logger.debug(f"-c flag found but source is not correct: {real_src_path} VS {make_tokens[gcc_source_flag_idx + 1]}")
                    cmd_file_fd.close()
            except:
                logger.debug("-c flag not found. Continue...")
                cmd_file_fd.close()
        
    return None