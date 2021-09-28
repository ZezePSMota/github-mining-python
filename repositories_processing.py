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

TECHNOLOGIES = ["rxjava", "rxjs", "rxswift", "rxkotlin"]
FILE_EXTENSIONS = {"rxjava": ["java"],
                   "rxjs": ["cs", "ts", "js"],
                   "rxkotlin": ["kt", "java"],
                   "rxswift": ["swift"],
                   "rxdart": ["dart"]}
RX_GH_USERS = ["ReactiveX", "dotnet", "neuecc", "bjornbytes", "alfert", "Reactive-Extensions"]


GRAY_LIST_PATH = "gray_list.json"
REPO_LIST_PATH = "repo_list.json"

OPERANDS_PATH = "indexes/operands.json"
USAGE_PATH = "indexes/operands_usage.json"
USAGE_CSV = "indexes/operands_usage.csv"
STATS_PATH = "indexes/operands_stats.json"
STATS_CSV = "indexes/operands_stats.csv"
UNUSED_PATH = "indexes/usage_stats.json"
UNUSED_CSV = "indexes/usage_stats.csv"


def clone_repos():
    for technology in TECHNOLOGIES:
        repos_df = pandas.read_csv(f'CSVs/{technology}.csv')
        counter = 60
        with open(GRAY_LIST_PATH, "r") as gray_list_file:
            gray_list = json.load(gray_list_file)
            blacklist = gray_list["blacklist"]
            for index, row in repos_df.iterrows():
                if counter == 0 or row["stargazers_count"] < 14:
                    break
                if row[u"owner"] in RX_GH_USERS or f'{row["owner"]}_{row["name"]}' in blacklist:
                    continue
                try:
                    git.Repo.clone_from(f'https://github.com/{row["full_name"]}.git',
                                        f'repos/{technology}/{row["owner"]}_{row["name"]}')
                except GitCommandError as e:
                    pass
                    # print(e)
                counter -= 1


def get_files(path, extension, file_writer):
    for subdir, folders, files in os.walk(path):

        for folder in folders:
            folder_path = f'{path}/{folder}'
            get_files(folder_path, extension, file_writer)

        for file in files:

            file_path = f'{subdir}/{file}'
            if "rxjava" in subdir:
                if file.endswith(f'.{extension}') and re.search("src.main.java", subdir):
                    file_writer.write(file_path + "\n")

            elif "rxkotlin" in subdir:
                if file.endswith(f'.{extension}') and re.search("src.main.kotlin", subdir):
                    file_writer.write(file_path + "\n")

            elif "rxswift" in subdir or "rxdart" in subdir or "rxjs" in subdir:
                if file.endswith(f'.{extension}') and extension in ["js", "cs", "ts", "swift", "dart"]:
                    try:
                        file_writer.write(file_path + "\n")
                    except UnicodeEncodeError:
                        print(file_path)
                        print(UnicodeEncodeError)

        #     if removable:
        #         try:
        #             removal_path = f"{os.getcwd()}/{file_path}"
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
        with open(f"indexes/{technology}.txt", "a+") as f:
            os.chdir("repos/")
            get_files(f"{technology}", extension, f)
            os.chdir("..")


def count_word(word, path_file, technology):
    try:
        with open(path_file, encoding="utf-8", errors="ignore") as f:
            file_text = f.read()
            return len(re.findall(r"\."+word+r"[^\w;\.]*\(", file_text))
    except FileNotFoundError:
        return 0


def count_usage_unthreaded():
    with open(OPERANDS_PATH, "r") as operands_file:
        operands = json.load(operands_file)
        for technology in TECHNOLOGIES:
            operands = count_usage(operands, technology)
        with open(USAGE_PATH, "w+") as usage_json:
            json.dump(operands, usage_json, indent=4, sort_keys=True)
        usage_json_to_csv()


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
    file_list_path = f"indexes/{technology}.txt"
    with open(file_list_path, "r") as file_list_file, open(REPO_LIST_PATH, "r") as repo_list_file:
        whitelist = json.load(repo_list_file)[technology]
        file_list = set([x for x in file_list_file.read().split("\n") if x])
        for file in file_list:
            project = file[technology_length+1: file[technology_length+1:].find("/") + technology_length+1]
            if project not in whitelist:
                continue
            # if technology == "rxjs":
            #     operands = count_usage_rxjs(path_file=f"repos/{file}", operands=operands, project=project)

            technology_operands = operands[technology].keys()
            for operand in technology_operands:
                path_file = f"repos/{file}"
                word_count = count_word(word=operand, path_file=path_file, technology=technology)
                try:
                    if operands[technology][operand][project] > 0:
                        operands[technology][operand][project] = operands[technology][operand][project] + word_count
                    else:
                        operands[technology][operand][project] = word_count
                except KeyError as e:
                    operands[technology][operand][project] = word_count
    return operands


def calculate_stats():
    result = {}
    with open(USAGE_PATH, "r") as operands_usage_file:
        operands_usage_full = json.load(operands_usage_file)
        for technology in TECHNOLOGIES:
            if technology == "rxjs":
                technology_csv = "RxJS"
            if technology == "rxjava":
                technology_csv = "RxJava"
            if technology == "rxswift":
                technology_csv = "RxSwift"
            if technology == "rxkotlin":
                technology_csv = "RxKotlin"
            if technology == "rxdart":
                technology_csv = "RxDart"
            result[technology_csv] = {}
            operands_usage = operands_usage_full[technology]
            operands = list(operands_usage.keys())
            for operand in operands:
                values = list(operands_usage[operand].values())
                result[technology_csv][operand] = {}
                if values:
                    total = sum(values)
                    presence = len([i for i in values if i > 0])
                    result[technology_csv][operand]["total_uses"] = total
                    result[technology_csv][operand]["repos_present"] = presence
                    result[technology_csv][operand]["median"] = statistics.median(values)
                    result[technology_csv][operand]["average_all"] = total/len(values)
                    result[technology_csv][operand]["average_present"] = total/presence if presence > 0 else 0
                    result[technology_csv][operand]["coverage"] = presence/len(values)
                    try:
                        result[technology_csv][operand]["mode"] = statistics.mode(values)
                    except statistics.StatisticsError:
                        count_dict = Counter(values)
                        count_values = list(count_dict.values())
                        most_common = [str(i[0]) for i in sorted(
                            count_dict.most_common(count_values.count(max(count_values))))]
                        result[technology_csv][operand]["mode"] = f'"{"|".join(most_common)}"'
                else:
                    result[technology_csv][operand]["total_uses"] = 0
                    result[technology_csv][operand]["repos_present"] = 0
                    result[technology_csv][operand]["median"] = 0
                    result[technology_csv][operand]["average_all"] = 0
                    result[technology_csv][operand]["average_present"] = 0
                    result[technology_csv][operand]["coverage"] = 0
                    result[technology_csv][operand]["mode"] = 0

    with open(STATS_PATH, "w+") as stats_json:
        json.dump(result, stats_json, indent=4, sort_keys=True)
    stats_json_to_csv()


def stats_json_to_csv():
    with open(STATS_PATH, "r") as operands_stats_file, open(STATS_CSV, "w+") as csv_file:
        csv_file.write('"distribution","operand","total uses","presence","coverage","median","mode","average_all",'
                       '"average_present"')
        operands_stats = json.load(operands_stats_file)
        for technology in TECHNOLOGIES:
            if technology == "rxjs":
                technology = "RxJS"
            if technology == "rxjava":
                technology = "RxJava"
            if technology == "rxswift":
                technology = "RxSwift"
            if technology == "rxkotlin":
                technology = "RxKotlin"
            if technology == "rxdart":
                technology = "RxDart"
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


def usage_json_to_csv():
    with open(USAGE_PATH, "r") as operands_usage_file, open(USAGE_CSV, "w+") as csv_file:
        csv_file.write('"distribution","repo","operand","usage"')
        operands_usage = json.load(operands_usage_file)
        for technology in TECHNOLOGIES:
            if technology == "rxjs":
                technology_csv = "RxJS"
            if technology == "rxjava":
                technology_csv = "RxJava"
            if technology == "rxswift":
                technology_csv = "RxSwift"
            if technology == "rxkotlin":
                technology_csv = "RxKotlin"
            if technology == "rxdart":
                technology_csv = "RxDart"
            operands = list(operands_usage[technology].keys())
            for operand in operands:
                repos = list(operands_usage[technology][operand].keys())
                for repo in repos:
                    total_uses = operands_usage[technology][operand][repo]
                    csv_file.write(f'\n{technology_csv},{repo},{operand},{total_uses}')


# def count_closest_to_pipe(operands, file, project, technology="rxjs"):
#     print("rxjs")
#     technology_length = len(technology)
#     file_list_path = f"indexes/{technology}.txt"
#     with open(file_list_path, "r") as file_list_file:
#         file_list = [x for x in file_list_file.read().split("\n") if x]
#         for file in file_list:
#             project = file[technology_length + 1: file[technology_length + 1:].find("/") + 1]
#             # print(technology, project)
#             technology_operands = operands[technology].keys()
#             for operand in technology_operands:
#                 is_js = True if technology == "rxjs" else False
#                 word_count = count_word(operand, "repos/" + file, is_js)
#                 try:
#                     operands[technology][operand][project] = operands[technology][operand][project] + word_count
#                 except KeyError as e:
#                     operands[technology][operand][project] = word_count


def count_usage_rxjs(path_file, operands, project):
    try:
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
                    if re.match(operand+r"\(", valid_sub_text):
                        try:
                            operands["rxjs"][operand][project] += 1
                        except KeyError:
                            operands["rxjs"][operand][project] = 1
                position = next_position + 5
            return operands
    except FileNotFoundError:
        print(FileNotFoundError)
        return operands


def find_unused():
    result = {}
    with open(USAGE_PATH, "r") as operands_usage_file:
        operands_usage_full = json.load(operands_usage_file)
        for technology in TECHNOLOGIES:
            result[technology] = {}
            operands_usage = operands_usage_full[technology]
            operands = list(operands_usage.keys())
            for operand in operands:
                repos = list(operands_usage[operand].keys())
                for repo in repos:
                    try:
                        if operands_usage[operand][repo] > 0:
                            result[technology][repo] += 1
                    except KeyError:
                        result[technology][repo] = 0
            total_used = [i for i in list(result[technology].keys()) if result[technology][i] > 0]
            total_unused = [i for i in list(result[technology].keys()) if result[technology][i] == 0]
            print(technology, len(total_used), len(total_unused), "\n", list(total_used), "\n", list(total_unused), "\n", list(result[technology]), "\n")
    with open(UNUSED_PATH, "w+") as unused_json:
        json.dump(result, unused_json, indent=4, sort_keys=True)
    with open(UNUSED_PATH, "r") as unused_stats_file, open(UNUSED_CSV, "w+") as csv_file:
        csv_file.write('"distribution","repos","total uses"')
        operands_stats = json.load(unused_stats_file)
        for technology in TECHNOLOGIES:
            repos = list(operands_stats[technology].keys())
            for repo in repos:
                total_uses = operands_stats[technology][repo]
                csv_file.write(f'\n"{technology}","{repo}",{total_uses}')


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

        # if "--clone" in sys.argv or "--all" in sys.argv:
        #     clone_repos()
        #     print_runtime(start)

        # if "--flu" in sys.argv or "--all" in sys.argv or "--process" in sys.argv:
        #     create_file_list_unthreaded()
        #     print_runtime(start)

        if "--countu" in sys.argv or "--all" in sys.argv or "--process" in sys.argv:
            count_usage_unthreaded()
            print_runtime(start)

        if "--stats" in sys.argv or "--all" in sys.argv or "--process" in sys.argv:
            # find_unused()
            calculate_stats()
            print_runtime(start)

        print(datetime.now())

    if osSleep:
        osSleep.allow()
