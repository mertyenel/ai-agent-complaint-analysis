# settings.py
BOT_NAME = "sv_vestel"

SPIDER_MODULES = ["sv_vestel.spiders"]
NEWSPIDER_MODULE = "sv_vestel.spiders"

ROBOTSTXT_OBEY = False # Bu ayarı False yaparak robots.txt kısıtlamalarını es geçebiliriz.

# Playwright entegrasyonu
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30_000

PLAYWRIGHT_INCLUDE_PAGE = True

# Playwright'ın istekleri filtrelemesi için gerekli router
# Bu fonksiyonu, spider dosyasının içinde tanımlayacağız.
PLAYWRIGHT_PAGE_ROUTERS = [
    'sv_vestel.spiders.vestel_last.skip_unnecessary_requests',
]

DEFAULT_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
# sv_vestel/sv_vestel/settings.py
# ...
ITEM_PIPELINES = {
    'sv_vestel.pipelines.VestelPipeline': 300,
}
# ...
DOWNLOAD_DELAY = 1.0
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 8

FEEDS = {
    "out/vestel_last.jsonl": {"format": "jsonlines", "overwrite": True, "encoding": "utf8"},
    "out/vestel_last.csv": {"format": "csv", "overwrite": True, "encoding": "utf8"},
}