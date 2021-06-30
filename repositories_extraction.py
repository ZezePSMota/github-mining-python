import time
import datetime
import pandas
import json
from pandas import json_normalize
from github import Github


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

    def check_rate_limit(self, is_search=False):
        rate_limits = self.github_client.get_rate_limit()

        if rate_limits.search.remaining == 0:
            time_diff = rate_limits.search.reset - datetime.datetime.utcnow()
            wait_time = time_diff.total_seconds()

            print(f'Search, wait: {int(wait_time/3600)} hours, {int(wait_time/60)} minutes, {int(wait_time%60)} seconds.')

            time.sleep(wait_time)

        elif rate_limits.core.remaining == 0:
            time_diff = rate_limits.core.reset - datetime.datetime.utcnow()
            wait_time = time_diff.total_seconds()

            print(f'Core, wait: {int(wait_time/3600)} hours, {int(wait_time/60)} minutes, {int(wait_time%60)} seconds.')

            time.sleep(wait_time)

        print(f'Remaining Rate Limit:{rate_limits.search.remaining}; {rate_limits.core.remaining}')
        pass

    def search(self, query, min_stars, max_stars):

        self.check_rate_limit(True)
        query = f'{query} stars:{min_stars}..{max_stars}'
        query_response = self.github_client.search_repositories(query=query, sort="stars")
        return query_response, min_stars, max_stars

    def exhaustive_search(self, query="", min_stars=10, max_stars=1000000):

        while max_stars >= 0:

            query_response, min_stars, max_stars = self.search(query, min_stars, max_stars)
            print(query_response.totalCount, min_stars, max_stars)
            if query_response.totalCount == 1000 and min_stars+1 <= max_stars:
                min_stars = min_stars+1
            else:
                max_stars = min_stars-1
                if min_stars-10 < 0:
                    min_stars = 0
                else:
                    min_stars = min_stars-10

                for repo in query_response:
                    repo_dict = extract_repo_info(repo)
                    self.total_repositories = self.total_repositories.append(repo_dict, ignore_index=True)


g = GithubSearcher()

# g.exhaustive_search("rxjs")
# g.total_repositories.to_csv('rxjs.csv')

g.exhaustive_search("rxjava")
g.total_repositories.to_csv('rxjava.csv')

g.exhaustive_search("rxswift")
g.total_repositories.to_csv('rxjava.csv')

g.exhaustive_search("rxkotlin")
g.total_repositories.to_csv('rxjava.csv')
