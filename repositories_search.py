import json
import os
import re

import git
import pandas
from git import GitCommandError

TECHNOLOGIES = ["rxjava", "rxjs", "rxkotlin"]  # , "rxswift"]
FILE_EXTENSIONS = [("rxjava", "java"), ("rxjs", "cs"), ("rxjs", "ts"), ("rxjs", "js"), ("rxkotlin", "kt"),
                   ("rxkotlin", "java"), ("rxswift", "swift")]
OPERANDS_PATH = "indexes\\operands.json"
USAGE_PATH = "indexes\\operands_usage.json"
STATS_PATH = "indexes\\operands_stats.json"


def clone_repos():
    for technology in TECHNOLOGIES:
        repos_df = pandas.read_csv(f'CSVs/{technology}.csv')
        counter = 50
        for index, row in repos_df.iterrows():
            if row["owner"] == "ReactiveX":
                continue
            try:
                git.Repo.clone_from(f'https://github.com/{row["full_name"]}.git',
                                    f'repos/{technology}/{row["owner"]}_{row["name"]}')
            except GitCommandError as e:
                print(e)
            counter = counter - 1
            if counter == 0:
                break


def get_files(path, extension, file_writer):
    for subdir, folders, files in os.walk(path):

        for folder in folders:
            folder_path = f'{path}\\{folder}'
            get_files(folder_path, extension, file_writer)

        for file in files:

            file_path = f'{subdir[1:]}\\{file}'

            if file.endswith(f'.{extension}') and re.search("src.main.java", subdir):
                file_writer.write(file_path + "\n")
            elif extension == "kt" and file.endswith(f'.{extension}') and re.search("src.main.kotlin", subdir):
                file_writer.write(file_path + "\n")
            elif file.endswith(f'.{extension}') and extension in ["js", "cs", "ts", "swift"]:
                file_writer.write(file_path + "\n")
            else:
                try:
                    os.remove(os.path.abspath(os.getcwd()) + file_path)
                except (FileNotFoundError, PermissionError) as e:
                    print(e)

        try:
            os.rmdir(path)
        except (FileNotFoundError, OSError) as e:
            print(e)


def create_file_list():
    for technology, extension in FILE_EXTENSIONS:
        with open(f"indexes\\{technology}.txt", "a+") as f:
            os.chdir(f"repos\\{technology}")
            get_files(".", extension, f)
            os.chdir("..\\..")


def count_word(word, file):
    with open(file, encoding="utf-8", errors="ignore") as f:
        return f.read().count(word)


def count_usage():
    for technology in TECHNOLOGIES:
        file_list_path = f"indexes\\{technology}.txt"
        with open(file_list_path, "r") as file_list_file, open(OPERANDS_PATH, "r") as operands_file:
            file_list = [x for x in file_list_file.read().split("\n") if x]
            operands = json.load(operands_file)
            for file in file_list:
                project = file[2: file[2:].find("\\") + 2]
                print(technology, project)
                technology_operands = operands[technology].keys()
                for operand in technology_operands:
                    word = f"pipe({operand}" if technology == "rxjs" else f".{operand}"
                    word_count = count_word(word, "repos\\" + technology + file[1:])
                    try:
                        operands[technology][operand][project] = operands[technology][operand][project] + word_count
                    except KeyError as e:
                        operands[technology][operand][project] = word_count
    with open(USAGE_PATH, "w+") as usage_json:
        json.dump(operands, usage_json, indent=4, sort_keys=True)


def calculate_stats():
    result = {}
    with open(USAGE_PATH, "r") as operands_usage_file:
        operands_usage_full = json.load(operands_usage_file)
        for technology in TECHNOLOGIES:
            result[technology] = {}
            operands_usage = operands_usage_full[technology]
            operands = list(operands_usage.keys())
            for operand in operands:
                repos = list(operands_usage[operand].keys())
                result[technology][operand] = {}
                result[technology][operand]["total_uses"] = 0
                result[technology][operand]["repos_present"] = 0
                for repo in repos:
                    if operands_usage[operand][repo] > 0:
                        result[technology][operand]["total_uses"] = result[technology][operand]["total_uses"] + \
                                                                    operands_usage[operand][repo]
                        result[technology][operand]["repos_present"] = result[technology][operand]["repos_present"] + 1
                result[technology][operand]["coverage"] = result[technology][operand]["repos_present"]/50
    with open(STATS_PATH, "w+") as stats_json:
        json.dump(result, stats_json, indent=4, sort_keys=True)


# clone_repos()
# create_file_list()
# count_usage()
calculate_stats()
