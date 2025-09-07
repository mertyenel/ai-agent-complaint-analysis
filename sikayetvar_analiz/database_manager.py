import sqlite3
from typing import List, Dict, Optional, Tuple
from config import Config

class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_database()  # Veritabanını başlangıçta oluştur
    
    def init_database(self):
        """Veritabanını ve tabloları oluştur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Tablo 1: Complaints (Şikayetler)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS complaints (
                        Complaint_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                        ref_url TEXT UNIQUE NOT NULL,
                        title TEXT,
                        full_comment TEXT,
                        date TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Tablo 2: Analysis (Analiz) - Complaint_ID UNIQUE olacak
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS Analysis (
                        ID INTEGER PRIMARY KEY AUTOINCREMENT,
                        Complaint_ID INTEGER UNIQUE NOT NULL,
                        Category TEXT,
                        Reason TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (Complaint_ID) REFERENCES complaints (Complaint_ID) ON DELETE CASCADE
                    )
                ''')
                
                # Indexler
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_complaints_date ON complaints (date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_complaint_id ON Analysis (Complaint_ID)')
                
                conn.commit()
                
        except Exception as e:
            raise
    
    
    def get_complaints_by_count(self, count: int) -> Tuple[List[Dict], List[int]]:
        """Son N şikayeti getir"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT Complaint_ID, full_comment, ref_url, title, date
                    FROM complaints
                    ORDER BY date DESC, Complaint_ID DESC
                    LIMIT ?
                ''', (count,))
                
                columns = ['Complaint_ID', 'full_comment', 'ref_url', 'title', 'date']
                complaints = [dict(zip(columns, row)) for row in cursor.fetchall()]
                complaint_ids = [c['Complaint_ID'] for c in complaints]
                
                return complaints, complaint_ids
                
        except Exception as e:
            return [], []
    
    def get_complaints_by_date_range(self, start_date: str, end_date: str) -> Tuple[List[Dict], List[int]]:
        """Tarih aralığındaki şikayetleri getir"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT Complaint_ID, full_comment, ref_url, title, date
                    FROM complaints
                    WHERE date >= ? AND date < date(?, '+1 day')
                    ORDER BY date DESC
                ''', (start_date, end_date))
                
                columns = ['Complaint_ID', 'full_comment', 'ref_url', 'title', 'date']
                complaints = [dict(zip(columns, row)) for row in cursor.fetchall()]
                complaint_ids = [c['Complaint_ID'] for c in complaints]
                
                return complaints, complaint_ids
                
        except Exception as e:
            return [], []
    
    def get_uncategorized_complaints(self, complaint_ids: List[int] = None) -> List[Dict]:
        """Analiz yapılmamış şikayetleri getir"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if complaint_ids:
                    # Sadece belirli ID'ler içinde analiz yapılmamış olanları bul
                    placeholders = ','.join(['?' for _ in complaint_ids])
                    query = f'''
                        SELECT c.Complaint_ID, c.full_comment, c.ref_url, c.title, c.date
                        FROM complaints c
                        LEFT JOIN Analysis a ON c.Complaint_ID = a.Complaint_ID  
                        WHERE c.Complaint_ID IN ({placeholders}) 
                        AND (a.Category IS NULL OR TRIM(a.Category) = '' OR a.Category = 'NULL')
                    '''
                    cursor.execute(query, complaint_ids)
                else:
                    # Tüm analiz yapılmamış şikayetleri getir
                    cursor.execute('''
                        SELECT c.Complaint_ID, c.full_comment, c.ref_url, c.title, c.date
                        FROM complaints c
                        LEFT JOIN Analysis a ON c.Complaint_ID = a.Complaint_ID
                        WHERE (a.Category IS NULL OR TRIM(a.Category) = '' OR a.Category = 'NULL')
                        ORDER BY c.date DESC
                    ''')
            
            columns = ['Complaint_ID', 'full_comment', 'ref_url', 'title', 'date']
            result = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return result
            
        except Exception as e:
            return []
    
    def insert_analysis(self, analysis_data: List[Dict]) -> int:
        """Analiz verilerini ekle/güncelle - Complaint_ID UNIQUE constraint ile"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                successful_updates = 0
                
                for item in analysis_data:
                    complaint_id = item['Complaint_ID']
                    category = item.get('category', item.get('Category'))  # Hem category hem Category destekle
                    reason = item.get('reason', item.get('Reason'))  # Hem reason hem Reason destekle
                    
                    try:
                        # UPSERT operation - INSERT OR REPLACE yerine UPDATE ya da INSERT
                        # Önce kontrol et
                        cursor.execute('SELECT ID FROM Analysis WHERE Complaint_ID = ?', (complaint_id,))
                        existing = cursor.fetchone()
                        
                        if existing:
                            # UPDATE
                            cursor.execute('''
                                UPDATE Analysis 
                                SET Category = ?, Reason = ?, created_at = CURRENT_TIMESTAMP 
                                WHERE Complaint_ID = ?
                            ''', (category, reason, complaint_id))
                        else:
                            # INSERT
                            cursor.execute('''
                                INSERT INTO Analysis (Complaint_ID, Category, Reason) 
                                VALUES (?, ?, ?)
                            ''', (complaint_id, category, reason))
                        
                        successful_updates += 1
                        
                    except sqlite3.IntegrityError as e:
                        continue
                    except Exception as e:
                        continue
            
            conn.commit()
            return successful_updates
            
        except Exception as e:
            raise
    
    def get_final_analysis_stats_for_complaints(self, complaint_ids: List[int]) -> Dict[str, Dict[str, int]]:
        """Belirli şikayetlerin analiz dağılımını getir (Category ve Reason)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                placeholders = ','.join(['?' for _ in complaint_ids])
                
                # Category dağılımı
                cursor.execute(f'''
                    SELECT a.Category, COUNT(*) as count
                    FROM Analysis a
                    WHERE a.Complaint_ID IN ({placeholders}) 
                    AND a.Category IS NOT NULL 
                    AND TRIM(a.Category) != ''
                    GROUP BY a.Category
                    ORDER BY count DESC
                ''', complaint_ids)
                
                category_stats = dict(cursor.fetchall())
                
                # Reason dağılımı
                cursor.execute(f'''
                    SELECT a.Reason, COUNT(*) as count
                    FROM Analysis a
                    WHERE a.Complaint_ID IN ({placeholders}) 
                    AND a.Reason IS NOT NULL 
                    AND TRIM(a.Reason) != ''
                    GROUP BY a.Reason
                    ORDER BY count DESC
                ''', complaint_ids)
                
                reason_stats = dict(cursor.fetchall())
                
                return {
                    "categories": category_stats,
                    "reasons": reason_stats
                }
                
        except Exception as e:
            return {"categories": {}, "reasons": {}}
    
    def get_all_ref_urls(self) -> set:
        """TÜM ref_url'leri al (tam karşılaştırma için)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT ref_url FROM complaints')
                
                ref_urls = set(row[0] for row in cursor.fetchall())
                return ref_urls
                
        except Exception as e:
            return set()
    
    def save_new_complaints_incremental(self, complaints: List[Dict]) -> Dict:
        """Yeni şikayetleri ekle (duplicate kontrolü ile)"""
        try:
            if not complaints:
                return {'success': True, 'new_count': 0, 'duplicate_count': 0}
            
            new_count = 0
            duplicate_count = 0
            new_complaint_ids = []
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for complaint in complaints:
                    ref_url = complaint.get('ref_url')
                    if not ref_url:
                        continue
                    
                    # Duplicate kontrolü
                    cursor.execute('SELECT 1 FROM complaints WHERE ref_url = ?', (ref_url,))
                    if cursor.fetchone():
                        duplicate_count += 1
                        continue
                    
                    # Yeni kayıt ekle
                    cursor.execute('''
                        INSERT INTO complaints (ref_url, title, full_comment, date)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        ref_url,
                        complaint.get('title', ''),
                        complaint.get('full_comment', ''),
                        complaint.get('date', '')
                    ))
                    
                    new_complaint_ids.append(cursor.lastrowid)
                    new_count += 1
                
                conn.commit()
                
                return {
                    'success': True,
                    'new_count': new_count,
                    'duplicate_count': duplicate_count,
                    'new_complaint_ids': new_complaint_ids
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'new_count': 0,
                'duplicate_count': 0
            }

    def get_complaint_by_id(self, complaint_id: int) -> Optional[Dict]:
        """Belirli ID'ye göre şikayet getir"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT Complaint_ID, full_comment, ref_url, title, date
                    FROM complaints
                    WHERE Complaint_ID = ?
                ''', (complaint_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = ['Complaint_ID', 'full_comment', 'ref_url', 'title', 'date']
                    return dict(zip(columns, row))
                else:
                    return None
                    
        except Exception as e:
            return None
        
    def get_data_date_range(self) -> Dict[str, str]:
        """Database'deki en eski ve en yeni şikayet tarihlerini al"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT MIN(date) as earliest, MAX(date) as latest
                    FROM complaints
                    WHERE date IS NOT NULL
                ''')
                
                row = cursor.fetchone()
                if row and row[0] and row[1]:
                    return {
                        "earliest": row[0],
                        "latest": row[1]
                    }
                else:
                    return {
                        "earliest": None,
                        "latest": None
                    }
                    
        except Exception as e:
            return {
                "earliest": None,
                "latest": None
            }