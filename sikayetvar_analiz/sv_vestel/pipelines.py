import sqlite3
import os
from scrapy.exceptions import CloseSpider

class VestelPipeline:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.processed_count = 0
        # Ana dizindeki veritabanını kullan (sv_vestel/sikayetvar.db)
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sikayetvar.db')

    def open_spider(self, spider):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Complaints tablosunu oluştur - ref_url UNIQUE ile
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                Complaint_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ref_url TEXT UNIQUE NOT NULL,
                title TEXT,
                full_comment TEXT,
                date TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index oluştur
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_complaints_date ON complaints (date)')
        
        self.conn.commit()
        spider.logger.info(f"Pipeline initialized with database: {self.db_path}")

    def process_item(self, item, spider):
        try:
            # Önce kontrol et, varsa durdur
            self.cursor.execute("SELECT Complaint_ID FROM complaints WHERE ref_url = ?", (item['ref_url'],))
            existing = self.cursor.fetchone()
            
            if existing:
                spider.logger.info(f"Mevcut şikayet bulundu: {item['ref_url']}. Tarama durduruluyor...")
                raise CloseSpider(f"Duplicate found: {item['ref_url']}")
            else:
                # Yeni kayıt ekle
                self.cursor.execute("""
                    INSERT INTO complaints (ref_url, title, full_comment, date) 
                    VALUES (?, ?, ?, ?)
                """, (item['ref_url'], item['title'], item['full_comment'], item['date']))
                
                # Yeni eklenen kaydın ID'sini al
                complaint_id = self.cursor.lastrowid
                
                # Analiz henüz yapılmadı, sadece şikayet kaydedildi
                # Analysis agent daha sonra Category ve Reason ekleyecek
                spider.logger.info(f"Yeni şikayet eklendi - ID: {complaint_id} (analiz henüz yapılmayacak)")
                
                self.conn.commit()
                self.processed_count += 1

        except CloseSpider:
            raise
        except Exception as e:
            spider.logger.error(f"Veritabanı hatası: {e}")
    
    def close_spider(self, spider):
        if self.conn:
            spider.logger.info(f"Toplam {self.processed_count} yeni şikayet eklendi")
            self.conn.close()