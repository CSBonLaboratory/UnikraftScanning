import logging
import pymongo
from colorama import Fore
import os
import coverage
from srcs_trie import SrcsTrie
from bson.objectid import ObjectId
logger = logging.getLogger(__name__)
from typing import Union
from helpers import SourceDocument, CompilationBlock
from pymongo.cursor import Cursor


def view_app_subcommand(compilation_tags : list[str], out_file_name : str):

    from coverage import DATABASE, SOURCES_COLLECTION, COMPILATION_COLLECTION, db


    app_src_documents : Union[list[SourceDocument], list[dict]] = db[DATABASE][SOURCES_COLLECTION].find(
        filter={"triggered_compilations" : {"$in" : compilation_tags}},
        sort={"source_path" : pymongo.ASCENDING}
    )

    appTrie = SrcsTrie(os.environ["UK_WORKDIR"])

    # remove other compiled stats of compilations that are not wished to be visualized 
    for src_doc in app_src_documents:
        
        # for i in range(len(src_doc["compile_blocks"])):
        #     if src_doc["compile_blocks"][i]["_local_id"] != i:
        #         print(src_doc)
        
        # return

        for tag in src_doc["compiled_stats"]:
            if tag not in compilation_tags:
                del src_doc["compiled_stats"][tag]
        appTrie.add_node(src_doc["source_path"].split("/"), src_doc)

    
    out_file = open(out_file_name, "a")

    appTrie.print_trie(out_file, compilation_tags)

    





