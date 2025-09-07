import scrapy
from scrapy.exceptions import CloseSpider
import datetime
from urllib.parse import urljoin

# Turkish month names dictionary
turkish_months = {
    'Ocak': 1, 'Şubat': 2, 'Mart': 3, 'Nisan': 4,
    'Mayıs': 5, 'Haziran': 6, 'Temmuz': 7, 'Ağustos': 8,
    'Eylül': 9, 'Ekim': 10, 'Kasım': 11, 'Aralık': 12
}

def parse_turkish_date(date_text):
    try:
        date_text = date_text.strip()
        parts = date_text.split()
        day = int(parts[0])
        month_str = parts[1]
        hour, minute = map(int, parts[2].split(':'))
        
        month = turkish_months.get(month_str)
        if not month:
            raise ValueError("Unknown month name")

        current_year = datetime.datetime.now().year
        return datetime.datetime(current_year, month, day, hour, minute)
    except Exception as e:
        return None

def abort_request(req):
    return req.resource_type != "document"

class VestelLastSpider(scrapy.Spider):
    name = "vestel_last"
    allowed_domains = ["www.sikayetvar.com", "sikayetvar.com"]

    custom_settings = {
        "LOG_LEVEL": "INFO",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "PLAYWRIGHT_INCLUDE_PAGE": True,
        "PLAYWRIGHT_ABORT_REQUEST": abort_request,
        # SIRALI İŞLEM İÇİN ÖNEMLİ AYARLAR
        "CONCURRENT_REQUESTS": 1,  # Tek seferde sadece 1 request
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,  # Domain başına 1 request
        "DOWNLOAD_DELAY": 0.5,  # Daha hızlı incremental için
    }

    def __init__(self, count=None, date_range=None, start_page=200, incremental=None, existing_refs_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = int(count) if count else None
        self.date_range = None
        self.start_page = int(start_page) if start_page else 60
        self.items_collected = 0
        self.should_stop = False
        self.current_page = self.start_page
        self.complaint_queue = []  # URL'leri sırayla saklamak için
        
        # Incremental mode ayarları
        self.incremental_mode = incremental == 'true'
        self.existing_refs = set()
        
        if self.incremental_mode:
            self.logger.info("🔄 INCREMENTAL MODE AKTIF - Page 1'den başlayıp duplicate bulunca duracak")
            self.start_page = 1
            self.current_page = 1
            
            # Existing refs dosyasını yükle
            if existing_refs_file:
                try:
                    import json
                    with open(existing_refs_file, 'r') as f:
                        existing_refs_list = json.load(f)
                        self.existing_refs = set(existing_refs_list)
                        self.logger.info(f"📊 {len(self.existing_refs)} existing ref_url yüklendi")
                except Exception as e:
                    self.logger.warning(f"Existing refs dosyası yüklenemedi: {e}")
        else:
            # Normal mode - database'den existing refs al
            try:
                from database_manager import DatabaseManager
                db_manager = DatabaseManager()
                existing_refs_list = db_manager.get_all_ref_urls()
                self.existing_refs = set(existing_refs_list)
                self.logger.info(f"📊 {len(self.existing_refs)} existing ref_url yüklendi (normal mode)")
            except Exception as e:
                self.logger.warning(f"Database'den existing refs alınamadı: {e}")

        # Parse date range if provided
        if date_range:
            try:
                start_str, end_str = date_range.split(',')
                self.date_range = (
                    datetime.datetime.strptime(start_str.strip(), "%Y-%m-%d"),
                    datetime.datetime.strptime(end_str.strip(), "%Y-%m-%d")
                )
                self.logger.info(f"Date range set: {self.date_range[0].date()} to {self.date_range[1].date()}")
            except ValueError:
                self.logger.error("Invalid date format. Use: 2025-08-01,2025-08-22")
                raise CloseSpider("Date range error")
        
        if self.count:
            self.logger.info(f"Target count: {self.count}")
        
        self.logger.info(f"Starting from page: {self.start_page}")

    def start_requests(self):
        """Start from specified page (default: 60)"""
        url = f"https://www.sikayetvar.com/vestel?page={self.start_page}"
        yield scrapy.Request(
            url,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "page_num": self.start_page
            },
            callback=self.parse_page,
            priority=1000  # En yüksek öncelik
        )

    def parse_page(self, response):
            """Parse complaint cards from listing page"""
            page_num = response.meta.get('page_num', 1)
            cards = response.css('article.card-v2.ga-v.ga-c')
            
            # --- DEĞİŞİKLİK BURADA BAŞLIYOR ---

            # Eğer kart bulunamazsa, sadece bir uyarı ver ama spider'ı durdurma.
            if not cards:
                self.logger.warning(f"SAYFA {page_num} ÜZERİNDE KART BULUNAMADI. Yine de bir sonraki sayfaya geçilmeye çalışılacak.")
            else:
                self.logger.info(f"Page {page_num}: Found {len(cards)} complaint cards")

                # Her kartı sırayla işle (Bu kısım aynı kalıyor)
                for idx, card in enumerate(cards, 1):
                    if self.count and not self.incremental_mode and self.items_collected >= self.count:
                        self.logger.info(f"Reached target count ({self.count}) - stopping")
                        self.should_stop = True
                        return # Count dolunca buradan çıkış yapmak doğru

                    complaint_url = card.css('h2.complaint-title a::attr(href)').get()
                    
                    if not complaint_url:
                        self.logger.warning(f"Page {page_num}, card {idx}: No URL found")
                        continue
                    
                    if not complaint_url.startswith('http'):
                        complaint_url = urljoin("https://www.sikayetvar.com", complaint_url)

                    if complaint_url in self.existing_refs:
                        if self.incremental_mode:
                            self.logger.info(f"🛑 INCREMENTAL: İlk duplicate bulundu - SPIDER DURDURULUYOR!")
                            raise CloseSpider(f'incremental_first_duplicate_found: {complaint_url}')
                        else:
                            self.logger.debug(f"Skipping duplicate: {complaint_url}")
                            continue

                    priority = (1000 - page_num) * 1000 + (1000 - idx)
                    
                    yield scrapy.Request(
                        url=complaint_url,
                        callback=self.parse_complaint,
                        meta={
                            'page_num': page_num,
                            'card_idx': idx,
                            'ref_url': complaint_url
                        },
                        priority=priority
                    )

            # --- SAYFA GEÇİŞ MANTIĞI ARTIK HER ZAMAN KONTROL EDİLECEK ---

            # Bir sonraki sayfaya geç (eğer gerekirse)
            if not self.should_stop:
                # Buradaki if/elif yapısı doğru çalışıyor, sorun ona ulaşamamaktı.
                if self.count and not self.incremental_mode and self.items_collected < self.count:
                    yield self.next_page_request(page_num + 1)
                elif self.date_range:
                    yield self.next_page_request(page_num + 1)
                elif self.incremental_mode:
                    self.logger.info(f"📄 INCREMENTAL: Sayfa {page_num} tamamlandı, sayfa {page_num + 1}'e geçiliyor")
                    yield self.next_page_request(page_num + 1)
                elif not self.count and not self.date_range:
                    yield self.next_page_request(page_num + 1)
                    
    def next_page_request(self, next_page):
        """Generate request for next page"""
        url = f"https://www.sikayetvar.com/vestel?page={next_page}"
        # Sonraki sayfa için priority düşür
        priority = (1000 - next_page) * 1000
        return scrapy.Request(
            url,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "page_num": next_page
            },
            callback=self.parse_page,
            priority=priority
        )

    def parse_complaint(self, response):
        """Parse individual complaint page"""
        ref_url = response.meta['ref_url']
        page_num = response.meta['page_num']
        card_idx = response.meta['card_idx']
        
        # Count kontrolü - incremental mode'da devre dışı
        if self.count and not self.incremental_mode and self.items_collected >= self.count:
            return

        # Extract date
        date_text = response.css('div.post-time div::text').get()
        if not date_text:
            self.logger.warning(f"No date found for: {ref_url}")
            return

        # Parse Turkish date
        parsed_date = parse_turkish_date(date_text.strip())
        if not parsed_date:
            self.logger.error(f"Could not parse date: {date_text}")
            return

        # TARIH ARALIĞI KONTROLÜ - DÜZELTME
        if self.date_range:
            # Eğer şikayetin tarihi aralığın başlangıcından eskiyse hemen dur
            if parsed_date.date() < self.date_range[0].date():
                self.logger.info(f"Reached end of date range: {parsed_date.date()} < {self.date_range[0].date()}")
                raise CloseSpider('date_range_completed')  # Spider'ı hemen durdur
            
            # Eğer şikayet tarih aralığının dışındaysa atla
            if not (self.date_range[0].date() <= parsed_date.date() <= self.date_range[1].date()):
                self.logger.debug(f"Skipping complaint outside date range: {parsed_date.date()}")
                return

        # Extract content
        title_parts = response.css('h1.complaint-detail-title ::text').getall()
        title = " ".join([t.strip() for t in title_parts if t.strip()])
        
        comment_parts = response.css('div.complaint-detail-description ::text').getall()
        full_comment = " ".join([part.strip() for part in comment_parts if part.strip()])

        # Create item
        item = {
            'ref_url': ref_url,
            'title': title if title else None,
            'full_comment': full_comment,
            'date': parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        }

        self.items_collected += 1
        self.logger.info(f"Collected complaint {self.items_collected} from page {page_num}, card {card_idx}: {parsed_date.strftime('%Y-%m-%d %H:%M')}")

        # Count kontrolü - incremental mode'da devre dışı
        if self.count and not self.incremental_mode and self.items_collected >= self.count:
            self.logger.info(f"Target count ({self.count}) reached!")
            self.should_stop = True

        yield item

    def closed(self, reason):
        """Called when spider is closed"""
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Total complaints collected: {self.items_collected}")