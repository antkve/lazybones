import requests
import json
import re
import csv
import html
import logging
from time import sleep

logger = logging.getLogger(__name__)

PAGINATION_STEP= 25
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0",
    "Referer": "https://duckduckgo.com/",
}
SESSION = requests.Session()
SESSION.headers = HEADERS
VQD_DICT = dict()
RE_STRIP_TAGS = re.compile("<.*?>")

def _get_vqd(keywords):
    global SESSION

    vqd_bytes = VQD_DICT.get(keywords, None)
    if vqd_bytes:
        # move_to_end (LRU cache)
        VQD_DICT[keywords] = VQD_DICT.pop(keywords)
        return vqd_bytes.decode()

    payload = {"q": keywords}
    for _ in range(2):
        try:
            resp = SESSION.post("https://duckduckgo.com", data=payload, timeout=10)
            resp.raise_for_status()
            vqd_index_start = resp.content.index(b"vqd='") + 5
            vqd_index_end = resp.content.index(b"'", vqd_index_start)
            vqd_bytes = resp.content[vqd_index_start:vqd_index_end]

            if vqd_bytes:
                # delete the first key to reduce memory consumption
                if len(VQD_DICT) > 32768:
                    VQD_DICT.pop(next(iter(VQD_DICT)))
                VQD_DICT[keywords] = vqd_bytes
                return vqd_bytes.decode()

        except Exception:
            logger.exception("")

        # refresh SESSION if not vqd
        prev_proxies = SESSION.proxies
        SESSION.close()
        SESSION = requests.Session()
        SESSION.headers = HEADERS
        SESSION.proxies = prev_proxies
        logger.warning(
            "keywords=%s. _get_vqd() is None. Refresh SESSION and retry...", keywords
        )
        VQD_DICT.pop(keywords, None)
        sleep(0.25)

    # sleep to prevent blocking
    sleep(0.25)


def _save_json(jsonfile, data):
    with open(jsonfile, "w") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def _save_csv(csvfile, data):
    with open(csvfile, "w", newline="", encoding="utf-8") as file:
        if data:
            headers = data[0].keys()
            writer = csv.DictWriter(file, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(data)


def _normalize(raw_html):
    """strip HTML tags"""
    if raw_html:
        return html.unescape(re.sub(RE_STRIP_TAGS, "", raw_html))


def ddg(
    keywords,
    region="wt-wt",
    safesearch="moderate",
    max_results=None,
    page=1,
):
    """DuckDuckGo text search. Query params: https://duckduckgo.com/params

    Args:
        keywords (str): keywords for query.
        region (str, optional): wt-wt, us-en, uk-en, ru-ru, etc. Defaults to "wt-wt".
        safesearch (str, optional): on, moderate, off. Defaults to "moderate".
        time (Optional[str], optional): d, w, m, y. Defaults to None.
        max_results (Optional[int], optional): maximum number of results, max=200. Defaults to None.
            if max_results is set, then the parameter page is not taken into account.
        page (int, optional): page for pagination. Defaults to 1.
        output (Optional[str], optional): csv, json. Defaults to None.
        download (bool, optional): if True, download and save dociments to 'keywords' folder.
            Defaults to False.

    Returns:
        Optional[List[dict]]: DuckDuckGo text search results.
    """
    if not keywords:
        return None

    # get vqd
    vqd = _get_vqd(keywords)
    if not vqd:
        return None

    # prepare payload
    safesearch_base = {"On": 1, "Moderate": -1, "Off": -2}
    payload = {
        "q": keywords,
        "l": region,
        "p": safesearch_base[safesearch.capitalize()],
        "s": 0,
        "df": None,
        "o": "json",
        "vqd": vqd,
    }
    # get results
    cache = set()
    payload["s"] = max(PAGINATION_STEP * (page - 1), 0)
    page_data = None
    try:
        resp = SESSION.get("https://links.duckduckgo.com/d.js", params=payload)
        resp.raise_for_status()
        page_data = resp.json().get("results", None)
    except Exception:
        logger.exception("")
        if not max_results:
            return None
    page_results = []
    if page_data:
        for row in page_data:
            if "n" not in row and row["u"] not in cache:
                cache.add(row["u"])
                body = _normalize(row["a"])
                if body:
                    page_results.append(
                        {
                            "title": _normalize(row["t"]),
                            "href": row["u"],
                            "body": body,
                        }
                    )
    if not page_results:
        return None
    return page_results


""" using html method
    payload = {
        'q': keywords,
        'l': region,
        'p': safesearch_base[safesearch],
        'df': time
        }
    results = []
    while True:
        res = SESSION.post('https://html.duckduckgo.com/html', data=payload, **kwargs)
        tree = html.fromstring(res.text)
        if tree.xpath('//div[@class="no-results"]/text()'):
            return results
        for element in tree.xpath('//div[contains(@class, "results_links")]'):
            results.append({
                'title': element.xpath('.//a[contains(@class, "result__a")]/text()')[0],
                'href': element.xpath('.//a[contains(@class, "result__a")]/@href')[0],
                'body': ''.join(element.xpath('.//a[contains(@class, "result__snippet")]//text()')),
            })
        if len(results) >= max_results:
            return results
        next_page = tree.xpath('.//div[@class="nav-link"]')[-1]
        names = next_page.xpath('.//input[@type="hidden"]/@name')
        values = next_page.xpath('.//input[@type="hidden"]/@value')
        payload = {n: v for n, v in zip(names, values)}
        sleep(2)
"""