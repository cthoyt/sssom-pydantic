"""

Discover frm https://github.com/search?q=path%3A*.sssom.tsv%20-is%3Afork&type=code&ref=advsearch&p=5

"""
import json

from pystow.github import search_code
import pystow
from pystow.utils import write_json

QUERY = "path:*.sssom.tsv -is:fork"


def main():
    path = pystow.join("sssom", name="github-search.json")
    if not path.is_file():
        results = list(search_code(QUERY))
        write_json(results, path)
    else:
        results = json.loads(path.read_text())

    print(results[0])

if __name__ == '__main__':
    main()
