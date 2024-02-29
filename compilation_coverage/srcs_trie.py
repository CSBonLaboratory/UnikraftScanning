
from __future__ import annotations
from colorama import Fore
from helpers import SourceVersionStrategy, SourceDocument, GitCommitStrategy, SHA1Strategy, CompilationBlock
from typing import Union
from queue import LifoQueue
from functools import reduce

PLACEHOLDER_INFO = "    "
PLACEHOLDER_NODE = "  | "
PLACEHOLDER_LEAF = "  +-- "
class SrcsTrie:

    next_nodes : list[SrcsTrie] = None
    path_token : str = None
    info : dict = None
    def __init__(self, token : str) -> None:
        # the root will have absolute path up to the UK_WORKDIR
        self.next_nodes = []
        self.path_token = token
    def add_node(self, srcs_tokens : list[str], src_doc : Union[SourceDocument, dict]) -> None:
        
        correct_child = None

        for child in self.next_nodes:
            if child.path_token == srcs_tokens[0]:
                correct_child = child
                break
            
        
        if correct_child == None:
            correct_child = SrcsTrie(srcs_tokens[0])
            self.next_nodes.append(correct_child)

        if len(srcs_tokens) > 1:
            correct_child.add_node(srcs_tokens[1:], src_doc)
        else:
            correct_child.info = src_doc

    def print_compile_blocks(self, base, tabs, out_file, compilation_tags : list[str]):

        compile_blocks : Union[list[CompilationBlock], list[dict]] = self.info["compile_blocks"]

        # this is an artificial root block since documents will have multiple compilation blocks with no parent
        # it helps when traversing
        root_block = {"children" : []}
        for cb in compile_blocks:
            if cb["_parent_id"] == -1:
                root_block["children"].append(cb["_local_id"])

        queue = LifoQueue()
        queue.put((root_block, tabs))

        while not queue.empty():

            current, depth = queue.get()
            
            # this is for the artificial root compilation block
            if "symbol_condition" not in current:
                for child_local_id in reversed(current["children"]):
                    queue.put((compile_blocks[child_local_id], depth + 1))
                continue
            

            if current["triggered_compilations"] == []:
                out_file.write(base * PLACEHOLDER_NODE + (depth - base) * PLACEHOLDER_INFO + Fore.RED + current["symbol_condition"] + Fore.RESET + "\n")

            elif reduce(lambda acc, compile_name : acc | True if compile_name in current["triggered_compilations"] else acc | False, compilation_tags, False):
                out_file.write(base * PLACEHOLDER_NODE + (depth - base) * PLACEHOLDER_INFO + Fore.GREEN + current["symbol_condition"] + Fore.RESET + "\n")
            else:
                out_file.write(base * PLACEHOLDER_NODE + (depth - base) * PLACEHOLDER_INFO + Fore.YELLOW + current["symbol_condition"] + Fore.RESET + "\n")
                
            
            out_file.write(base * PLACEHOLDER_NODE + (depth - base) * PLACEHOLDER_INFO + f"Start line: {current['start_line']}\n")

            out_file.write(base * PLACEHOLDER_NODE + (depth - base) * PLACEHOLDER_INFO + f"End line: {current['end_line']}\n")

            out_file.write(base * PLACEHOLDER_NODE + (depth - base) * PLACEHOLDER_INFO + f"Block counter: {current['_local_id']}\n")

            out_file.write(base * PLACEHOLDER_NODE + (depth - base) * PLACEHOLDER_INFO + f"Triggered compilations/apps: {current['triggered_compilations']}\n")
            
            out_file.write(base * PLACEHOLDER_NODE + "\n")
            
            for child_local_id in reversed(current["children"]):
                queue.put((compile_blocks[child_local_id], depth + 1))
        

    def print_source(self, tabs, out_file, compilation_tags : list[str]):
        complete = True

        ans = ""
        for tag, compiled_lines in self.info["compiled_stats"].items():

            if compiled_lines < self.info["total_lines"]:
                ratio = compiled_lines / self.info["total_lines"]
                ans += (tabs - 1) * PLACEHOLDER_NODE + PLACEHOLDER_INFO + f"Compilation stats({Fore.RED}{tag}{Fore.RESET}): Compiled:{Fore.RED}{compiled_lines}{Fore.RESET}, Total: {self.info['total_lines']}, Ration:{Fore.RED}{'{:.2%}'.format(ratio)}{Fore.RESET}\n"
                complete = False
                    
            else:
                ans += (tabs - 1) * PLACEHOLDER_NODE + PLACEHOLDER_INFO + f"Compilation stats({Fore.GREEN}{tag}{Fore.RESET}): Compiled:{Fore.GREEN}{compiled_lines}{Fore.RESET}, Total: {self.info['total_lines']}, Ration:{Fore.GREEN}100%{Fore.RESET}\n"

        if complete:
            ans = (tabs - 2) * PLACEHOLDER_NODE + PLACEHOLDER_LEAF + f"{Fore.GREEN}{self.info['source_path']}:{Fore.RESET}\n" + ans
        else:
            ans = (tabs - 2) * PLACEHOLDER_NODE + PLACEHOLDER_LEAF + f"{Fore.RED}{self.info['source_path']}:{Fore.RESET}\n" + ans

        ans += (tabs - 1) * PLACEHOLDER_NODE + PLACEHOLDER_INFO + "Library: " + self.info["lib"] + "\n"
        ans += (tabs - 1) * PLACEHOLDER_NODE + PLACEHOLDER_INFO + f"Triggered compilations/apps:{self.info['triggered_compilations']}\n"
                    
        # print the type of source version strategy (git commit hash or sha1 etc.)
        if GitCommitStrategy.version_key in self.info:
            ans += (tabs - 1) * PLACEHOLDER_NODE + PLACEHOLDER_INFO + f"{GitCommitStrategy.version_key}:{self.info[GitCommitStrategy.version_key]}\n"
        elif SHA1Strategy.version_key in self.info:
            ans += (tabs - 1) * PLACEHOLDER_NODE + PLACEHOLDER_INFO + f"{SHA1Strategy.version_key}:{self.info[SHA1Strategy.version_key]}\n"

        out_file.write(ans)

        out_file.write((tabs - 1) * PLACEHOLDER_NODE + PLACEHOLDER_INFO + "Compilation blocks\n")

        self.print_compile_blocks(tabs - 1, tabs, out_file, compilation_tags)

    def print_trie(self, out_file, compilation_tags : list[str], tabs = 0):

        ans = ""

        queue = LifoQueue()
        queue.put((self, tabs))

        while not queue.empty():

            current, depth = queue.get()

            if current.path_token[-2:] == ".c":
                current.print_source(depth + 1, out_file, compilation_tags)
            else:
                out_file.write(depth * PLACEHOLDER_NODE + current.path_token + "\n")

    
            for child_node in current.next_nodes:
                queue.put((child_node, depth + 1))
        
