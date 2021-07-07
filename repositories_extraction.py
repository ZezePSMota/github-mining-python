import time
import datetime
import pandas
import os
import json
from pandas import json_normalize
from github import Github

from windows_inhibitor import WindowsInhibitor


def extract_repo_info(repo):
    repo_dict = {"full_name": repo.full_name,
                 "forks_count": repo.forks_count,
                 "has_downloads": repo.has_downloads,
                 "has_issues": repo.has_issues,
                 "has_pages": repo.has_pages,
                 "has_wiki": repo.has_wiki,
                 "id": repo.id,
                 "language": repo.language,
                 "last_modified": repo.last_modified,
                 "name": repo.name,
                 "owner": repo.owner.login,
                 "size": repo.size,
                 "stargazers_count": repo.stargazers_count,
                 "subscribers_count": repo.subscribers_count,
                 "watchers_count": repo.watchers_count}
    return repo_dict


class GithubSearcher:
    token = ""
    github_client = None

    def __init__(self) -> None:
        self.token = self.read_token()
        self.github_client = Github(self.token)
        self.total_repositories = pandas.DataFrame(columns=["full_name", "forks_count", "has_downloads", "has_issues",
                                                            "has_pages", "has_wiki", "id", "language", "last_modified",
                                                            "name", "owner", "size", "stargazers_count",
                                                            "subscribers_count", "watchers_count"])
        print(self.github_client)

    @staticmethod
    def read_token():
        try:
            with open("github.token") as f:
                return f.readline()
        except FileNotFoundError:
            print("No OAUTH Token")

    def check_rate_limit(self):

        rate_limits = self.github_client.get_rate_limit()
        if rate_limits.search.remaining == 0:
            rate_limit = rate_limits.search

        elif rate_limits.core.remaining == 0:
            rate_limit = rate_limits.core

        else:
            return

        time_diff = rate_limit.reset - datetime.datetime.utcnow()
        wait_time = time_diff.total_seconds()

        print(f'Now: {datetime.datetime.now()}\nWait: {int(wait_time / 3600)} hours, {int(wait_time / 60)} '
              f'minutes, {int(wait_time % 60)} seconds.')

        while wait_time > 100:
            self.github_client.get_rate_limit()
            time_diff = rate_limit.reset - datetime.datetime.utcnow()
            wait_time = time_diff.total_seconds()
            # print(f'{rate_limit.reset}   {datetime.datetime.utcnow()}')
            print(f'Now: {datetime.datetime.now()}\nWait: {int(wait_time / 3600)} hours, {int(wait_time / 60)}'
                  f' minutes, {int(wait_time % 60)} seconds.')
            time.sleep(30)
        time.sleep(wait_time)
        print(f'Remaining Rate Limit:{rate_limits.search.remaining}; {rate_limits.core.remaining}')

    def search(self, query, min_stars, max_stars):

        self.check_rate_limit()
        query = f'{query} stars:{min_stars}..{max_stars}'
        query_response = self.github_client.search_repositories(query=query, sort="stars")
        return query_response, min_stars, max_stars

    def exhaustive_search(self, query="", min_stars=23, max_stars=1000000):

        while max_stars >= 0:

            query_response, min_stars, max_stars = self.search(query, min_stars, max_stars)
            print(query_response.totalCount, min_stars, max_stars)
            if query_response.totalCount == 1000 and min_stars + 1 <= max_stars:
                min_stars = min_stars + 1
            else:
                max_stars = min_stars - 1
                if min_stars - 10 < 0:
                    min_stars = 0
                else:
                    min_stars = min_stars - 10

                for repo in query_response:
                    self.check_rate_limit()
                    repo_dict = extract_repo_info(repo)
                    self.total_repositories = self.total_repositories.append(repo_dict, ignore_index=True)


print(datetime.datetime.now())
osSleep = None
# in Windows, prevent the OS from sleeping while we run
if os.name == 'nt':
    osSleep = WindowsInhibitor()
    osSleep.inhibit()

    g = GithubSearcher()

    g.exhaustive_search("rxjs")
    g.total_repositories.to_csv('repos/rxjs.csv')

    g.exhaustive_search("rxswift")
    g.total_repositories.to_csv('repos/rxswift.csv')

    g.exhaustive_search("rxkotlin")
    g.total_repositories.to_csv('repos/rxkotlin.csv')

    g.exhaustive_search("rxjava")
    g.total_repositories.to_csv('repos/rxjava.csv')

if osSleep:
    osSleep.allow()
