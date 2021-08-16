import json
import os
import re
import sys
import time
import statistics
from collections import Counter
from datetime import datetime
from joblib import Parallel, delayed

import git
import pandas
from git import GitCommandError

from windows_inhibitor import WindowsInhibitor

TECHNOLOGIES = ["rxjava", "rxjs", "rxkotlin", "rxswift", "rxdart"]
FILE_EXTENSIONS = {"rxjava": ["java"],
                   "rxjs": ["cs", "ts", "js"],
                   "rxkotlin": ["kt", "java"],
                   "rxswift": ["swift"],
                   "rxdart": ["dart"]}
RX_GH_USERS = ["ReactiveX", "dotnet", "neuecc", "bjornbytes", "alfert", "Reactive-Extensions"]

OPERANDS_PATH = "indexes\\operands.json"
USAGE_PATH = "indexes\\operands_usage.json"
STATS_PATH = "indexes\\operands_stats.json"
STATS_CSV = "indexes\\operands_stats.csv"


def clone_repos():
    for technology in TECHNOLOGIES:
        repos_df = pandas.read_csv(f'CSVs/{technology}.csv')
        counter = 50
        for index, row in repos_df.iterrows():
            if row["owner"] in RX_GH_USERS:
                continue
            try:
                git.Repo.clone_from(f'https://github.com/{row["full_name"]}.git',
                                    f'repos/{technology}/{row["owner"]}_{row["name"]}')
            except GitCommandError as e:
                # print(e)
                pass
            counter = counter - 1
            if counter == 0:
                break


def get_files(path, extension, file_writer):
    for subdir, folders, files in os.walk(path):

        for folder in folders:
            folder_path = f'{path}\\{folder}'
            get_files(folder_path, extension, file_writer)

        for file in files:

            file_path = f'{subdir}\\{file}'
            if "rxjava" in subdir:
                if file.endswith(f'.{extension}') and re.search("src.main.java", subdir):
                    file_writer.write(file_path + "\n")

            elif "rxkotlin" in subdir:
                if file.endswith(f'.{extension}') and re.search("src.main.kotlin", subdir):
                    file_writer.write(file_path + "\n")

            elif "rxjs" in subdir:
                if file.endswith(f'.{extension}') and extension in ["js", "cs", "ts", "swift", "dart"]:
                    file_writer.write(file_path + "\n")

            elif "rxswift" in subdir or "rxdart" in subdir:
                if file.endswith(f'.{extension}') and extension in ["js", "cs", "ts", "swift", "dart"]:
                    file_writer.write(file_path + "\n")

        #     if removable:
        #         try:
        #             removal_path = f"{os.getcwd()}\\{file_path}"
        #             os.remove(os.path.abspath(removal_path))
        #         except (FileNotFoundError, PermissionError) as e:
        #             # print(e)
        #             pass
        #
        # try:
        #     os.rmdir(path)
        # except (FileNotFoundError, OSError) as e:
        #     # print(e)
        #     pass


def create_file_list_threaded():
    Parallel(n_jobs=len(TECHNOLOGIES))(delayed(create_file_list)(technology) for technology in TECHNOLOGIES)


def create_file_list_unthreaded():
    for technology in TECHNOLOGIES:
        create_file_list(technology)


def create_file_list(technology):
    # for technology in TECHNOLOGIES:
    for extension in FILE_EXTENSIONS[technology]:
        with open(f"indexes\\{technology}.txt", "a+") as f:
            os.chdir("repos\\")
            get_files(f"{technology}", extension, f)
            os.chdir("..")


def count_word(word, path_file, is_js=False):
    with open(path_file, encoding="utf-8", errors="ignore") as f:
        file_text = f.read()
        if is_js:
            regex = r"pipe\([^;]*?" + word + r"\("
            flags = re.MULTILINE | re.DOTALL
            matches = re.findall(regex, file_text, flags)
            return len(matches)

        else:
            return file_text.count(f".{word}(")


def count_usage_unthreaded():
    with open(OPERANDS_PATH, "r") as operands_file:
        operands = json.load(operands_file)
        for technology in TECHNOLOGIES:
            count_usage(operands, technology)
        with open(USAGE_PATH, "w+") as usage_json:
            json.dump(operands, usage_json, indent=4, sort_keys=True)


def count_usage_threaded():
    with open(OPERANDS_PATH, "r") as operands_file:
        operands = json.load(operands_file)
        Parallel(n_jobs=len(TECHNOLOGIES-1))(delayed(count_usage)
                                           (operands, technology) for technology in TECHNOLOGIES)
        with open(USAGE_PATH+"t", "w+") as usage_json:
            json.dump(operands, usage_json, indent=4, sort_keys=True)


def count_usage(operands, technology):
    print(technology)
    technology_length = len(technology)
    file_list_path = f"indexes\\{technology}.txt"
    with open(file_list_path, "r") as file_list_file:
        file_list = set([x for x in file_list_file.read().split("\n") if x])
        for file in file_list:
            project = file[technology_length+1: file[technology_length+1:].find("\\") + 1]
            if technology == "rxjs":
                operands = count_usage_rxjs(path_file=f"repos\\{file}", operands=operands, project=project)
            else:
                technology_operands = operands[technology].keys()
                # print(technology, project)
                for operand in technology_operands:
                    word_count = count_word(operand, "repos\\" + file)
                    try:
                        operands[technology][operand][project] = operands[technology][operand][project] + word_count
                    except KeyError as e:
                        operands[technology][operand][project] = word_count


def calculate_stats():
    result = {}
    with open(USAGE_PATH, "r") as operands_usage_file:
        operands_usage_full = json.load(operands_usage_file)
        for technology in TECHNOLOGIES:
            result[technology] = {}
            operands_usage = operands_usage_full[technology]
            operands = list(operands_usage.keys())
            for operand in operands:
                values = list(operands_usage[operand].values())
                result[technology][operand] = {}
                if values:
                    total = sum(values)
                    presence = len([i for i in values if i > 0])
                    result[technology][operand]["total_uses"] = total
                    result[technology][operand]["repos_present"] = presence
                    result[technology][operand]["median"] = statistics.median(values)
                    result[technology][operand]["average_all"] = total/len(values)
                    result[technology][operand]["average_present"] = total/presence if presence > 0 else 0
                    result[technology][operand]["coverage"] = presence/len(values)
                    try:
                        result[technology][operand]["mode"] = statistics.mode(values)
                    except statistics.StatisticsError:
                        count_dict = Counter(values)
                        count_values = list(count_dict.values())
                        most_common = [str(i[0]) for i in sorted(
                            count_dict.most_common(count_values.count(max(count_values))))]
                        result[technology][operand]["mode"] = f'"{"|".join(most_common)}"'
                else:
                    result[technology][operand]["total_uses"] = 0
                    result[technology][operand]["repos_present"] = 0
                    result[technology][operand]["median"] = 0
                    result[technology][operand]["average_all"] = 0
                    result[technology][operand]["average_present"] = 0
                    result[technology][operand]["coverage"] = 0
                    result[technology][operand]["mode"] = 0

    with open(STATS_PATH, "w+") as stats_json:
        json.dump(result, stats_json, indent=4, sort_keys=True)
    json_to_csv()


def json_to_csv():
    with open(STATS_PATH, "r") as operands_stats_file, open(STATS_CSV, "w+") as csv_file:
        csv_file.write('"distribution","operand","total uses","presence","coverage","median","mode","average_all",'
                       '"average_present"')
        operands_stats = json.load(operands_stats_file)
        for technology in TECHNOLOGIES:
            operands = list(operands_stats[technology].keys())
            for operand in operands:
                operand_stats = operands_stats[technology][operand]
                total_uses = operand_stats["total_uses"]
                presence = operand_stats["repos_present"]
                coverage = operand_stats["coverage"]
                median = operand_stats["median"]
                mode = operand_stats["mode"]
                average_all = operand_stats["average_all"]
                average_present = operand_stats["average_present"]
                csv_file.write(f'\n{technology},{operand},{total_uses},{presence},{coverage},{median}'
                               f',{mode},{average_all},{average_present}')


# def count_closest_to_pipe(operands, file, project, technology="rxjs"):
#     print("rxjs")
#     technology_length = len(technology)
#     file_list_path = f"indexes\\{technology}.txt"
#     with open(file_list_path, "r") as file_list_file:
#         file_list = [x for x in file_list_file.read().split("\n") if x]
#         for file in file_list:
#             project = file[technology_length + 1: file[technology_length + 1:].find("\\") + 1]
#             # print(technology, project)
#             technology_operands = operands[technology].keys()
#             for operand in technology_operands:
#                 is_js = True if technology == "rxjs" else False
#                 word_count = count_word(operand, "repos\\" + file, is_js)
#                 try:
#                     operands[technology][operand][project] = operands[technology][operand][project] + word_count
#                 except KeyError as e:
#                     operands[technology][operand][project] = word_count


def count_usage_rxjs(path_file, operands, project):
    with open(path_file, encoding="utf-8", errors="ignore") as f:
        file_text = f.read()
        final_position = len(file_text)-1
        position = file_text.find("pipe(")+5 if file_text.find("pipe(") != -1 else final_position
        while position < final_position:
            next_position = file_text[position:].find("pipe(")
            next_position = next_position + position if next_position != -1 else final_position
            rxjs_operands = operands["rxjs"].keys()
            for operand in rxjs_operands:
                valid_sub_text = file_text[position:next_position]
                if f"{operand}(" in valid_sub_text:
                    try:
                        operands["rxjs"][operand][project] += 1
                    except KeyError as e:
                        operands["rxjs"][operand][project] = 1
            position = next_position + 5
        return operands


def print_runtime(start_time):
    total = time.time() - start_time
    hours = int((total / 3600) % 60)
    minutes = int((total / 60) % 60)
    seconds = int(total % 60)
    print(f"{hours}:{minutes}:{seconds}")


if __name__ == "__main__":

    osSleep = None
    # in Windows, prevent the OS from sleeping while running
    if os.name == 'nt':
        osSleep = WindowsInhibitor()
        osSleep.inhibit()
        start = time.time()
        print(datetime.now())

        if "--clone" in sys.argv or "--all" in sys.argv or "--allt" in sys.argv:
            clone_repos()
            print_runtime(start)

        if "--flu" in sys.argv or "--allu" in sys.argv:
            create_file_list_unthreaded()
            print_runtime(start)

        if "--flt" in sys.argv or "--all" in sys.argv:
            create_file_list_threaded()
            print_runtime(start)

        if "--countu" in sys.argv or "--all" in sys.argv:
            count_usage_unthreaded()
            print_runtime(start)

        if "--countt" in sys.argv or "--allt" in sys.argv:
            count_usage_threaded()
            print_runtime(start)

        if "--stats" in sys.argv or "--all" in sys.argv or "--allt" in sys.argv:
            calculate_stats()
            print_runtime(start)

        print(datetime.now())

    if osSleep:
        osSleep.allow()