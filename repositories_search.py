import os
import re

import git
import pandas
from git import GitCommandError


def clone_repos(rx_technology):
    repos_df = pandas.read_csv(f'CSVs/{rx_technology}.csv')
    counter = 50
    for index, row in repos_df.iterrows():
        if row["owner"] == "ReactiveX":
            continue
        try:
            git.Repo.clone_from(f'https://github.com/{row["full_name"]}.git',
                                f'repos/{rx_technology}/{row["owner"]}_{row["name"]}')
        except GitCommandError as e:
            print(e)
        counter = counter - 1
        if counter == 0:
            break


def get_files(path, extension, file_writer):
    for subdir, folders, files in os.walk(path):

        for folder in folders:
            get_files(f'{path}/{folder}', extension, file_writer)

        for file in files:

            filepath = f'{subdir}/{file}'

            if file.endswith(f'.{extension}') and re.search("src/main/java", subdir):
                file_writer.write(filepath + "\n")
            elif extension == "rxkotlin" and file.endswith(f'.{extension}') and re.search("src/main/kotlin", subdir):
                file_writer.write(filepath + "\n")
            elif file.endswith(f'.{extension}') and extension in ["js", "cs", "ts", "swift"]:
                file_writer.write(filepath + "\n")


def create_file_list(lib, extension):
    with open(f"indexes/{lib}.txt", "a+") as f:
        os.chdir(f"repos/{lib}")
        get_files(".", extension, f)
        os.chdir("../..")


def word_count(word, file):
    with open(file) as f:
        return f.read().count(word)



# clone_repos("rxjava")
# print(word_count('.to_csv'))
# create_file_list("rxjava", "java")
# create_file_list("rxjs", "cs")
# create_file_list("rxjs", "ts")
# create_file_list("rxjs", "js")
# create_file_list("rxkotlin", "kt")
# create_file_list("rxkotlin", "java")
# create_file_list("rxswift", "swift")

